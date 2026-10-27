#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Preview, move, reconcile, and restore ordinary same-filesystem files.

Only an explicit --apply mutates data. A move to a user-selected archive directory
is recoverable through its receipt; this is neither permanent deletion nor OS Trash.
Receipts are evidence, never authorization. Single active writer and cooperating,
stable directory roots are required. These checks do not fence malicious concurrent
renames or writers. No operation retries, removes an uncertain destination, moves a
directory, or crosses filesystems. Inspect `status` after any interrupted operation.
"""

import argparse
import datetime
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile


class SafetyError(ValueError):
    """A requested action is outside the helper's deliberately narrow scope."""


class ActionError(RuntimeError):
    """An attempted action needs read-only reconciliation before further action."""


PROTECTED = {
    ".git", ".checkpoint", ".checkpoints", ".private", ".aws", ".ssh",
    ".codex", ".agents", ".gnupg", ".azure", ".kube", "node_modules",
    ".venv", "__pycache__", "credentials", "auth.json", "credentials.json",
    "sessions", "archived_sessions", "automations", "plugins", "worktrees",
    "checkpoint-handoff", "codex", "auth", "secrets", "tokens",
}
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".sqlite", ".sqlite3", ".db")
IDENTITY_FIELDS = ("device", "inode", "mode", "size", "mtime_ns")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _path(value, receipt=False):
    raw = os.fspath(value)
    if not raw or "\x00" in raw or ".." in Path(raw).parts:
        raise SafetyError("Empty, NUL, and parent-traversal paths are refused")
    path = Path(os.path.abspath(os.path.expanduser(raw)))
    for part in path.parts:
        lower = part.casefold()
        protected = PROTECTED - ({".private"} if receipt else set())
        if (lower in protected or lower == ".env" or lower.startswith(".env.")
                or lower.endswith(SECRET_SUFFIXES)
                or lower.endswith(("-wal", "-shm"))):
            raise SafetyError("Protected state or credential path: {}".format(path))
    # Walk from the filesystem root without resolving away a symlink.
    chain = list(reversed(path.parents)) + [path]
    for item in chain:
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise SafetyError("Symlink path or ancestor: {}".format(item))
    for parent in path.parents:
        marker = parent / ".git"
        try:
            marker_info = marker.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(marker_info.st_mode):
            raise SafetyError("Managed worktree/submodule ancestor: {}".format(parent))
    return path


def _parent(path):
    try:
        info = path.parent.lstat()
    except FileNotFoundError as exc:
        raise SafetyError("Parent directory must already exist: {}".format(path.parent)) from exc
    if not stat.S_ISDIR(info.st_mode):
        raise SafetyError("Parent must be a directory: {}".format(path.parent))
    return info


def _absent(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return
    raise SafetyError("Will not overwrite existing path: {}".format(path))


def _identity(info):
    return {"device": info.st_dev, "inode": info.st_ino, "mode": info.st_mode,
            "size": info.st_size, "mtime_ns": info.st_mtime_ns,
            "ctime_ns": info.st_ctime_ns, "links": info.st_nlink}


def _same(first, second):
    # Creating a hardlink changes ctime and link count, so they are audit data only.
    return all(first[key] == second[key] for key in IDENTITY_FIELDS)


def _inspect(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(str(path), flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise SafetyError("Only regular files are supported: {}".format(path))
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(fd)
        final = path.lstat()
        if (not _same(_identity(before), _identity(after))
                or not _same(_identity(after), _identity(final))):
            raise SafetyError("File changed during inspection: {}".format(path))
        return {"identity": _identity(after), "sha256": digest.hexdigest()}
    finally:
        os.close(fd)


def _hash(value):
    if (not isinstance(value, str) or len(value) != 64
            or any(ch not in "0123456789abcdefABCDEF" for ch in value)):
        raise SafetyError("An expected SHA-256 with 64 hexadecimal characters is required")
    return value.lower()


def preview_move(source, destination, expected_sha256=None, record=None):
    source = _path(source)
    destination = _path(destination)
    if source == destination:
        raise SafetyError("Source and destination must differ")
    facts = _inspect(source)
    parent = _parent(destination)
    _absent(destination)
    if facts["identity"]["device"] != parent.st_dev:
        raise SafetyError("Cross-filesystem moves are refused (EXDEV)")
    if expected_sha256 is not None and facts["sha256"] != _hash(expected_sha256):
        raise SafetyError("Source does not match expected SHA-256")
    receipt = None
    if record is not None:
        receipt = _path(record, receipt=True)
        _parent(receipt)
        _absent(receipt)
        if receipt in (source, destination):
            raise SafetyError("Receipt must differ from source and destination")
    return {"operation": "preview", "writes": False, "source": str(source),
            "destination": str(destination), "sha256": facts["sha256"],
            "before_identity": facts["identity"],
            "record": str(receipt) if receipt else None,
            "precondition": "Single active writer; cooperating stable directory roots"}


def _fsync_dir(path):
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        try:
            os.fsync(fd)
        except OSError as exc:
            unsupported = {errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}
            if exc.errno not in unsupported:
                raise
    finally:
        os.close(fd)


def _fsync_file(path, expected_identity):
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not _same(_identity(info), expected_identity):
            raise SafetyError("Destination identity changed before data fsync")
        os.fsync(fd)
    finally:
        os.close(fd)


def _encode(record):
    return (json.dumps(record, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _write_fd(fd, data):
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _create_record(path, record):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL
                 | getattr(os, "O_NOFOLLOW", 0), 0o600)
    _write_fd(fd, _encode(record))
    _fsync_dir(path.parent)


def _save_record(path, record):
    _path(path, receipt=True)
    fd, temporary = tempfile.mkstemp(prefix=".{}-".format(path.name), dir=str(path.parent))
    try:
        _write_fd(fd, _encode(record))
        os.replace(temporary, str(path))
        _fsync_dir(path.parent)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def move_file(source, destination, expected_sha256=None, record=None, apply=False,
              action="move", inverse_of=None):
    if not apply:
        return preview_move(source, destination, expected_sha256, record)
    expected_sha256 = _hash(expected_sha256)
    if record is None:
        raise SafetyError("--record is required with --apply")
    plan = preview_move(source, destination, expected_sha256, record)
    source, destination, receipt = map(Path, (plan["source"], plan["destination"], plan["record"]))
    audit = {"schema": "codex-organizer-file-action-v1", "action": action,
             "original_path": str(source), "destination_path": str(destination),
             "expected_sha256": expected_sha256, "before_identity": plan["before_identity"],
             "created_at": _now(), "state": "prepared", "outcome": "uncertain",
             "recovery": "Inspect status; never retry automatically or remove either copy",
             "authorization": "Receipt is evidence only and grants no permission"}
    if inverse_of is not None:
        audit["inverse_of"] = str(inverse_of)
    # Persist an exclusive receipt before any link. Failure here cannot move data.
    _create_record(receipt, audit)
    try:
        # The link itself provides atomic no-overwrite; no exists()+rename race.
        os.link(str(source), str(destination), follow_symlinks=False)
        _fsync_file(destination, plan["before_identity"])
        _fsync_dir(destination.parent)
        audit.update(state="linked", updated_at=_now())
        _save_record(receipt, audit)  # Durable linked/uncertain state before unlink.
        current_source = _inspect(source)
        current_destination = _inspect(destination)
        for facts in (current_source, current_destination):
            if (not _same(facts["identity"], plan["before_identity"])
                    or facts["sha256"] != expected_sha256):
                raise SafetyError("Identity or content changed after linking; both paths retained")
        # Directory guards are checked again within the cooperating-roots contract.
        _path(source)
        _path(destination)
        os.unlink(str(source))
        _fsync_dir(source.parent)
        audit.update(state="moved", outcome="completed", completed_at=_now(),
                     recovery="Use explicit restore with a new inverse receipt")
        _save_record(receipt, audit)
        return audit
    except BaseException as exc:
        audit.update(state="uncertain", outcome="uncertain", updated_at=_now(),
                     error="{}: {}".format(type(exc).__name__, exc),
                     recovery="Inspect status; no automatic retry or deletion; preserve all surviving copies")
        try:
            _save_record(receipt, audit)
        except BaseException:
            # Earlier prepared/linked receipt already says the outcome is uncertain.
            pass
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise ActionError("Action uncertain; inspect status --record {}: {}".format(receipt, exc)) from exc


def _read_record(value):
    path = _path(value, receipt=True)
    facts = _inspect(path)
    if facts["identity"]["size"] > 1024 * 1024:
        raise SafetyError("Receipt exceeds 1 MiB")
    with path.open("r", encoding="utf-8") as stream:
        record = json.load(stream)
    if (not isinstance(record, dict) or record.get("schema") != "codex-organizer-file-action-v1"
            or not isinstance(record.get("before_identity"), dict)
            or not all(key in record["before_identity"] for key in IDENTITY_FIELDS)):
        raise SafetyError("Unsupported or malformed receipt")
    _hash(record.get("expected_sha256"))
    for key in ("original_path", "destination_path"):
        if not isinstance(record.get(key), str) or not Path(record[key]).is_absolute():
            raise SafetyError("Receipt paths must be absolute")
        _path(record[key])
    return path, record


def _facts(value, expected):
    path = _path(value)
    try:
        info = _inspect(path)
    except FileNotFoundError:
        return {"path": str(path), "present": False}
    return dict(info, path=str(path), present=True, matches_expected=info["sha256"] == expected)


def status(record):
    receipt, audit = _read_record(record)
    expected = audit["expected_sha256"].lower()
    source = _facts(audit["original_path"], expected)
    destination = _facts(audit["destination_path"], expected)
    if source["present"] and destination["present"]:
        observation = "both_paths_present"
    elif destination["present"]:
        observation = "destination_only"
    elif source["present"]:
        observation = "source_only"
    else:
        observation = "neither_path_present"
    return {"operation": "status", "writes": False, "record": str(receipt),
            "recorded_state": audit.get("state"), "recorded_outcome": audit.get("outcome"),
            "expected_sha256": expected, "observation": observation,
            "source": source, "destination": destination,
            "recovery": "Read-only facts; no retry, authorization, or deletion inferred"}


def restore(record, undo_record=None, apply=False):
    receipt, audit = _read_record(record)
    if audit.get("state") != "moved" or audit.get("outcome") != "completed":
        raise SafetyError("Restore requires a completed original receipt; reconcile uncertain actions first")
    facts = _inspect(_path(audit["destination_path"]))
    if (facts["sha256"] != audit["expected_sha256"].lower()
            or not _same(facts["identity"], audit["before_identity"])):
        raise SafetyError("Moved destination has changed; restore refused")
    if apply and undo_record is None:
        raise SafetyError("--undo-record is required with --apply")
    result = move_file(audit["destination_path"], audit["original_path"],
                       audit["expected_sha256"], undo_record, apply,
                       action="restore", inverse_of=receipt)
    if not apply:
        result["operation"] = "restore_preview"
        result["inverse_of"] = str(receipt)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "move"):
        command = commands.add_parser(name)
        command.add_argument("--source", required=True)
        command.add_argument("--destination", required=True)
        if name == "move":
            command.add_argument("--expected-sha256")
            command.add_argument("--record")
            command.add_argument("--apply", action="store_true")
    command = commands.add_parser("restore")
    command.add_argument("--record", required=True)
    command.add_argument("--undo-record")
    command.add_argument("--apply", action="store_true")
    command = commands.add_parser("status")
    command.add_argument("--record", required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        result = {"preview": preview_move, "move": move_file,
                  "restore": restore, "status": status}[command](**args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc), "writes_may_have_occurred": bool(args.get("apply"))}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
