import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('inventory', Path(__file__).resolve().parents[1] / 'skills/codex-organizer/scripts/inventory.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class SurveyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / 'project'
        self.root.mkdir()

    def test_metadata_does_not_modify_files(self):
        f = self.root / 'notes.txt'; f.write_text('valuable original')
        before = (hashlib.sha256(f.read_bytes()).hexdigest(), f.stat().st_mtime_ns)
        result = inventory.survey(self.root)
        self.assertEqual(result['entries'][0]['path'], 'notes.txt')
        self.assertEqual(result['entries'][0]['size_bytes'], len('valuable original'))
        self.assertEqual(before, (hashlib.sha256(f.read_bytes()).hexdigest(), f.stat().st_mtime_ns))
        self.assertEqual(list(self.root.iterdir()), [f])

    def test_protected_content_not_entered(self):
        for name in ['.git', '.checkpoint', '.codex', 'node_modules']:
            d = self.root / name; d.mkdir(); (d / 'hidden.txt').write_text('untouched')
        (self.root / '.env.local').write_text('private')
        result = inventory.survey(self.root)
        self.assertEqual(result['entries'], [])
        self.assertEqual(len(result['skipped']), 5)
        self.assertFalse(result['complete_for_selected_root'])

    def test_credential_and_recovery_stores_are_not_candidates(self):
        for name in ['.checkpoints', '.gnupg', '.azure', '.kube', 'secrets', 'tokens', 'auth']:
            d = self.root / name; d.mkdir(); (d / 'state.txt').write_text('private synthetic state')
        result = inventory.survey(self.root)
        self.assertEqual(result['entries'], [])
        self.assertEqual(len(result['skipped']), 7)
        self.assertFalse(result['complete_for_selected_root'])

    def test_database_sidecars_are_not_candidates(self):
        for name in ['state.sqlite3-wal', 'state.sqlite3-shm', 'state.db-wal']:
            (self.root / name).write_text('synthetic sidecar')
        result = inventory.survey(self.root)
        self.assertEqual(result['entries'], [])
        self.assertEqual(len(result['skipped']), 3)

    def test_symlink_not_followed(self):
        target = Path(self.tmp.name) / 'outside'; target.mkdir()
        (target / 'keep.txt').write_text('unique')
        (self.root / 'link').symlink_to(target, target_is_directory=True)
        result = inventory.survey(self.root)
        self.assertEqual(result['entries'], [])
        self.assertEqual(result['skipped'][0]['reason'], 'symlink')
        self.assertEqual((target / 'keep.txt').read_text(), 'unique')

    def test_root_or_ancestor_symlink_rejected(self):
        alias = Path(self.tmp.name) / 'alias'; alias.symlink_to(self.root, target_is_directory=True)
        child = self.root / 'child'; child.mkdir()
        for root in [alias, alias / 'child']:
            with self.assertRaises(ValueError): inventory.survey(root)

    def test_entry_limit_marks_partial(self):
        for n in range(5): (self.root / str(n)).write_text(str(n))
        result = inventory.survey(self.root, max_entries=2)
        self.assertEqual(result['visited_entries'], 2)
        self.assertTrue(result['truncated'])

    def test_depth_limit_marks_partial(self):
        nested = self.root / 'a'; nested.mkdir(); (nested / 'unique.txt').write_text('important')
        result = inventory.survey(self.root, max_depth=1)
        self.assertEqual([e['path'] for e in result['entries']], ['a'])
        self.assertTrue(result['truncated'])
        self.assertIn({'path': 'a', 'reason': 'depth-limit'}, result['skipped'])

    def test_valid_empty_not_missing(self):
        self.assertTrue(inventory.survey(self.root)['complete_for_selected_root'])
        with self.assertRaises(ValueError): inventory.survey(self.root / 'absent')

    def test_invalid_limits_rejected(self):
        for kwargs in [{'max_entries': 0}, {'max_entries': 5001}, {'max_depth': 0}, {'max_seconds': 31}]:
            with self.assertRaises(ValueError): inventory.survey(self.root, **kwargs)

    def test_protected_root_rejected(self):
        p = self.root / '.checkpoint'; p.mkdir()
        with self.assertRaises(ValueError): inventory.survey(p)

    def test_protected_descendant_root_rejected(self):
        p = self.root / '.checkpoint' / 'runs'; p.mkdir(parents=True)
        with self.assertRaises(ValueError): inventory.survey(p)

    def test_explicit_user_project_beneath_codex_is_allowed(self):
        p = self.root / '.codex' / '.chatgpt-projects' / 'g-project'; p.mkdir(parents=True)
        (p / 'notes.txt').write_text('user work')
        self.assertEqual(inventory.survey(p)['entries'][0]['path'], 'notes.txt')

    def test_timeout_is_reported(self):
        with patch.object(inventory.time, 'monotonic', side_effect=[0, 100]):
            result = inventory.survey(self.root)
        self.assertTrue(result['truncated'])

    def test_access_error_is_not_empty_success(self):
        with patch.object(inventory.os, 'scandir', side_effect=PermissionError('denied')):
            result = inventory.survey(self.root)
        self.assertFalse(result['complete_for_selected_root'])
        self.assertEqual(result['errors'][0]['error'], 'PermissionError')


if __name__ == '__main__': unittest.main()
