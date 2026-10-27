# SPDX-License-Identifier: MIT
"""Synthetic, local-only move/recovery tests; no real user cleanup candidates."""

import contextlib
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


MODULE = Path(__file__).resolve().parents[1] / "skills/codex-organizer/scripts/file_actions.py"
SPEC = importlib.util.spec_from_file_location("file_actions_under_test", MODULE)
actions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(actions)


class FileActionsTests(unittest.TestCase):
    def setUp(self):
        # /private/tmp avoids macOS's /var and /tmp symlink ancestors.
        parent = "/private/tmp" if Path("/private/tmp").is_dir() else "/tmp"
        self.temporary = tempfile.TemporaryDirectory(prefix="organizer-actions-", dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "report.txt"
        self.source.write_bytes(b"synthetic report\n")
        self.source.chmod(0o640)
        self.archive = self.root / "archive"
        self.archive.mkdir()
        self.destination = self.archive / "report.txt"
        self.receipt = self.root / "move.json"
        self.undo = self.root / "undo.json"
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def move(self, **kwargs):
        options = dict(source=self.source, destination=self.destination,
                       expected_sha256=self.digest, record=self.receipt, apply=True)
        options.update(kwargs)
        return actions.move_file(**options)

    def saved(self):
        return json.loads(self.receipt.read_text())

    def test_preview_and_default_move_do_not_write(self):
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        self.assertFalse(actions.preview_move(self.source, self.destination)["writes"])
        self.assertFalse(actions.move_file(self.source, self.destination, record=self.receipt)["writes"])
        self.assertEqual(before, sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*")))

    def test_actual_archive_and_restore_preserve_inode_metadata_and_receipts(self):
        original = self.source.stat()
        audit = self.move()
        self.assertEqual("moved", audit["state"])
        self.assertFalse(self.source.exists())
        archived = self.destination.stat()
        self.assertEqual((original.st_ino, original.st_mode, original.st_mtime_ns),
                         (archived.st_ino, archived.st_mode, archived.st_mtime_ns))
        original_receipt = self.receipt.read_bytes()
        restored = actions.restore(self.receipt, self.undo, apply=True)
        self.assertEqual("restore", restored["action"])
        self.assertEqual(str(self.receipt), restored["inverse_of"])
        self.assertEqual(original_receipt, self.receipt.read_bytes())
        self.assertEqual(original.st_ino, self.source.stat().st_ino)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.digest, hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_private_receipt_is_allowed(self):
        folder = self.root / ".private"
        folder.mkdir()
        self.move(record=folder / "move.json")
        self.assertTrue((folder / "move.json").is_file())

    def test_destination_collision_keeps_sentinel(self):
        self.destination.write_bytes(b"sentinel")
        with self.assertRaises(actions.SafetyError):
            self.move()
        self.assertEqual(b"sentinel", self.destination.read_bytes())
        self.assertTrue(self.source.exists())
        self.assertFalse(self.receipt.exists())

    def test_collision_after_preview_is_atomically_refused(self):
        real_link = os.link
        def collide(source, destination, **kwargs):
            Path(destination).write_bytes(b"racing sentinel")
            return real_link(source, destination, **kwargs)
        with mock.patch.object(actions.os, "link", side_effect=collide):
            with self.assertRaises(actions.ActionError):
                self.move()
        self.assertEqual(b"racing sentinel", self.destination.read_bytes())
        self.assertTrue(self.source.exists())
        self.assertEqual("uncertain", self.saved()["outcome"])

    def test_stale_hash_refused_before_writes(self):
        with self.assertRaises(actions.SafetyError):
            self.move(expected_sha256="0" * 64)
        self.assertTrue(self.source.exists())
        self.assertFalse(self.receipt.exists())
        self.assertFalse(self.destination.exists())

    def test_apply_requires_hash_and_record(self):
        for options in ({"expected_sha256": None}, {"record": None}, {"expected_sha256": "garbage"}):
            with self.subTest(options=options), self.assertRaises(actions.SafetyError):
                self.move(**options)
        self.assertFalse(self.destination.exists())

    def test_receipt_collision_keeps_sentinel(self):
        self.receipt.write_text("sentinel")
        with self.assertRaises(actions.SafetyError):
            self.move()
        self.assertEqual("sentinel", self.receipt.read_text())
        self.assertFalse(self.destination.exists())

    def test_receipt_create_exclusive_even_after_preview(self):
        real_create = actions._create_record
        def collide(path, record):
            path.write_text("receipt sentinel")
            return real_create(path, record)
        with mock.patch.object(actions, "_create_record", side_effect=collide):
            with self.assertRaises(FileExistsError):
                self.move()
        self.assertEqual("receipt sentinel", self.receipt.read_text())
        self.assertFalse(self.destination.exists())

    def test_directories_and_filesystem_root_refused(self):
        for source in (self.archive, Path("/")):
            with self.subTest(source=source), self.assertRaises(actions.SafetyError):
                self.move(source=source)
        with self.assertRaises(actions.SafetyError):
            self.move(destination=Path("/"))

    def test_nonregular_fifo_refused_without_blocking(self):
        fifo = self.root / "pipe"
        os.mkfifo(fifo)
        with self.assertRaises(actions.SafetyError):
            self.move(source=fifo)

    def test_missing_destination_or_receipt_parent_refused(self):
        for options in ({"destination": self.root / "missing" / "out.txt"},
                        {"record": self.root / "missing" / "record.json"}):
            with self.subTest(options=options), self.assertRaises(actions.SafetyError):
                self.move(**options)
        self.assertFalse((self.root / "missing").exists())

    def test_symlink_source_destination_and_receipt_ancestors_refused(self):
        alias = self.root / "alias"
        alias.symlink_to(self.archive, target_is_directory=True)
        source_link = self.root / "source-link"
        source_link.symlink_to(self.source)
        destination_link = self.archive / "destination-link"
        destination_link.symlink_to(self.source)
        options = ({"source": source_link}, {"destination": alias / "out"},
                   {"record": alias / "receipt.json"}, {"destination": destination_link})
        for item in options:
            with self.subTest(item=item), self.assertRaises(actions.SafetyError):
                self.move(**item)
        self.assertTrue(self.source.is_file())
        self.assertFalse(self.receipt.exists())

    def test_parent_traversal_refused(self):
        with self.assertRaises(actions.SafetyError):
            self.move(destination=str(self.archive / ".." / "out.txt"))

    def test_protected_source_destination_and_record_refused(self):
        for name in (".git", ".codex", ".checkpoint", ".agents", ".ssh", ".aws",
                     "sessions", "archived_sessions", "automations", "plugins", "worktrees",
                     "node_modules", ".venv", "__pycache__", "checkpoint-handoff", "credentials"):
            folder = self.root / name
            folder.mkdir()
            candidate = folder / "report.txt"
            candidate.write_bytes(self.source.read_bytes())
            for item in ({"source": candidate}, {"destination": folder / "out.txt"},
                         {"record": folder / "record.json"}):
                with self.subTest(name=name, item=item), self.assertRaises(actions.SafetyError):
                    self.move(**item)
        private = self.root / ".private"
        private.mkdir()
        with self.assertRaises(actions.SafetyError):
            self.move(destination=private / "out.txt")

    def test_credentials_and_database_filenames_refused(self):
        for name in ("auth.json", "credentials.json", ".env", ".env.local", "key.pem",
                     "secret.key", "cert.p12", "cert.pfx", "state.db", "state.sqlite",
                     "state.sqlite3", "state.db-wal", "state.db-shm"):
            for item in ({"destination": self.archive / name}, {"record": self.root / name}):
                with self.subTest(name=name, item=item), self.assertRaises(actions.SafetyError):
                    self.move(**item)

    def test_managed_worktree_ancestor_refused_for_all_paths(self):
        managed = self.root / "managed"
        managed.mkdir()
        (managed / ".git").write_text("gitdir: somewhere")
        candidate = managed / "report.txt"
        candidate.write_bytes(self.source.read_bytes())
        for item in ({"source": candidate}, {"destination": managed / "out.txt"},
                     {"record": managed / "record.json"}):
            with self.subTest(item=item), self.assertRaises(actions.SafetyError):
                self.move(**item)

    def test_ordinary_repository_ancestor_allowed(self):
        (self.root / ".git").mkdir()
        self.move()
        self.assertTrue(self.destination.exists())

    def test_cross_device_preflight_refused(self):
        with mock.patch.object(actions, "_parent", return_value=types.SimpleNamespace(st_dev=-1)):
            with self.assertRaisesRegex(actions.SafetyError, "EXDEV"):
                self.move()
        self.assertFalse(self.receipt.exists())

    def test_exdev_from_link_leaves_source_and_uncertain_receipt(self):
        with mock.patch.object(actions.os, "link", side_effect=OSError(errno.EXDEV, "cross device")):
            with self.assertRaises(actions.ActionError):
                self.move()
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())
        self.assertEqual("source_only", actions.status(self.receipt)["observation"])
        self.assertEqual("uncertain", self.saved()["state"])

    def test_unlink_failure_retains_both_copies(self):
        real_unlink = os.unlink
        def fail_source(path, *args, **kwargs):
            if Path(path) == self.source:
                raise PermissionError("synthetic source unlink failure")
            return real_unlink(path, *args, **kwargs)
        with mock.patch.object(actions.os, "unlink", side_effect=fail_source):
            with self.assertRaises(actions.ActionError):
                self.move()
        result = actions.status(self.receipt)
        self.assertEqual("both_paths_present", result["observation"])
        self.assertTrue(result["source"]["matches_expected"])
        self.assertTrue(result["destination"]["matches_expected"])
        self.assertEqual("uncertain", self.saved()["state"])

    def test_data_fsync_failure_keeps_both_and_uncertain_receipt(self):
        with mock.patch.object(actions, "_fsync_file", side_effect=OSError("synthetic data sync failure")):
            with self.assertRaises(actions.ActionError):
                self.move()
        self.assertTrue(self.source.exists())
        self.assertTrue(self.destination.exists())
        self.assertEqual("uncertain", self.saved()["outcome"])

    def test_interrupt_after_link_keeps_both_and_uncertain_receipt(self):
        real_save = actions._save_record
        calls = []
        def interrupt_once(path, record):
            calls.append(record["state"])
            if len(calls) == 1:
                raise KeyboardInterrupt()
            return real_save(path, record)
        with mock.patch.object(actions, "_save_record", side_effect=interrupt_once):
            with self.assertRaises(KeyboardInterrupt):
                self.move()
        self.assertTrue(self.source.exists())
        self.assertTrue(self.destination.exists())
        self.assertEqual("uncertain", self.saved()["outcome"])

    def test_failed_all_receipt_updates_keeps_initial_uncertain_receipt_and_both(self):
        with mock.patch.object(actions, "_save_record", side_effect=OSError("synthetic disk error")):
            with self.assertRaises(actions.ActionError):
                self.move()
        self.assertTrue(self.source.exists())
        self.assertTrue(self.destination.exists())
        self.assertEqual("prepared", self.saved()["state"])
        self.assertEqual("uncertain", self.saved()["outcome"])

    def test_failure_finalizing_after_unlink_keeps_destination_recoverable(self):
        real_save = actions._save_record
        def fail_completed(path, record):
            if record["state"] == "moved":
                raise OSError("synthetic final receipt failure")
            return real_save(path, record)
        with mock.patch.object(actions, "_save_record", side_effect=fail_completed):
            with self.assertRaises(actions.ActionError):
                self.move()
        self.assertFalse(self.source.exists())
        self.assertEqual(self.digest, hashlib.sha256(self.destination.read_bytes()).hexdigest())
        self.assertEqual("uncertain", self.saved()["state"])
        self.assertEqual("destination_only", actions.status(self.receipt)["observation"])
        with self.assertRaises(actions.SafetyError):
            actions.restore(self.receipt, self.undo, apply=True)

    def test_source_change_after_link_refuses_unlink(self):
        real_link = os.link
        def change(source, destination, **kwargs):
            real_link(source, destination, **kwargs)
            Path(source).write_bytes(b"changed by cooperating test")
        with mock.patch.object(actions.os, "link", side_effect=change):
            with self.assertRaises(actions.ActionError):
                self.move()
        self.assertTrue(self.source.exists())
        self.assertTrue(self.destination.exists())
        self.assertEqual("uncertain", self.saved()["outcome"])

    def test_restore_preview_and_status_do_not_write(self):
        self.move()
        before = self.receipt.read_bytes()
        result = actions.restore(self.receipt, self.undo)
        self.assertFalse(result["writes"])
        state = actions.status(self.receipt)
        self.assertEqual("destination_only", state["observation"])
        self.assertFalse(state["writes"])
        self.assertEqual(before, self.receipt.read_bytes())
        self.assertFalse(self.undo.exists())
        self.assertFalse(self.source.exists())

    def test_changed_destination_refuses_restore(self):
        self.move()
        self.destination.write_bytes(b"edited after archive")
        with self.assertRaises(actions.SafetyError):
            actions.restore(self.receipt, self.undo, apply=True)
        self.assertFalse(self.undo.exists())
        self.assertFalse(actions.status(self.receipt)["destination"]["matches_expected"])

    def test_replaced_destination_same_bytes_refuses_restore(self):
        self.move()
        data = self.destination.read_bytes()
        replacement = self.root / "replacement"
        replacement.write_bytes(data)
        os.replace(replacement, self.destination)
        with self.assertRaises(actions.SafetyError):
            actions.restore(self.receipt, self.undo, apply=True)

    def test_restore_collision_keeps_both_sentinels_and_receipt(self):
        self.move()
        self.source.write_bytes(b"new original occupant")
        before = self.receipt.read_bytes()
        with self.assertRaises(actions.SafetyError):
            actions.restore(self.receipt, self.undo, apply=True)
        self.assertEqual(b"new original occupant", self.source.read_bytes())
        self.assertTrue(self.destination.exists())
        self.assertEqual(before, self.receipt.read_bytes())
        self.assertFalse(self.undo.exists())

    def test_restore_needs_new_receipt_and_does_not_reuse_original(self):
        self.move()
        for record in (None, self.receipt):
            with self.subTest(record=record), self.assertRaises(actions.SafetyError):
                actions.restore(self.receipt, record, apply=True)
        self.assertTrue(self.destination.exists())

    def test_status_missing_paths_is_read_only_and_does_not_retry(self):
        self.move()
        self.destination.unlink()
        before = self.receipt.read_bytes()
        self.assertEqual("neither_path_present", actions.status(self.receipt)["observation"])
        self.assertEqual(before, self.receipt.read_bytes())

    def test_untrusted_receipt_cannot_target_protected_path(self):
        self.move()
        record = self.saved()
        record["original_path"] = str(self.root / ".codex" / "state")
        self.receipt.write_text(json.dumps(record))
        with self.assertRaises(actions.SafetyError):
            actions.restore(self.receipt, self.undo, apply=True)
        self.assertTrue(self.destination.exists())

    def test_cli_default_preview_apply_status_and_restore(self):
        def run(*args):
            result = subprocess.run([sys.executable, "-B", str(MODULE), *map(str, args)],
                                    text=True, capture_output=True)
            self.assertEqual(0, result.returncode, result.stderr)
            return json.loads(result.stdout)
        common = ("--source", self.source, "--destination", self.destination)
        self.assertFalse(run("preview", *common)["writes"])
        self.assertFalse(run("move", *common, "--record", self.receipt)["writes"])
        self.assertFalse(self.receipt.exists())
        self.assertEqual("moved", run("move", *common, "--expected-sha256", self.digest,
                                     "--record", self.receipt, "--apply")["state"])
        self.assertEqual("destination_only", run("status", "--record", self.receipt)["observation"])
        self.assertFalse(run("restore", "--record", self.receipt, "--undo-record", self.undo)["writes"])
        self.assertEqual("moved", run("restore", "--record", self.receipt,
                                     "--undo-record", self.undo, "--apply")["state"])

    def test_cli_missing_expected_hash_exits_two_without_data_changes(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            code = actions.main(["move", "--source", str(self.source), "--destination",
                                 str(self.destination), "--record", str(self.receipt), "--apply"])
        self.assertEqual(2, code)
        self.assertIn("SHA-256", errors.getvalue())
        self.assertTrue(self.source.exists())
        self.assertFalse(self.receipt.exists())


if __name__ == "__main__":
    unittest.main()
