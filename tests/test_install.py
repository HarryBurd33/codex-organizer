import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / 'source'; self.source.mkdir()
        (self.source / 'SKILL.md').write_text('---\nname: codex-organizer\ndescription: Fixture\n---\n')
        (self.source / 'LICENSE').write_text('fixture notice')
        self.dest = self.root / 'skills'

    def test_installs_matching_files_and_preserves_source(self):
        expected = installer.manifest(self.source)
        result = installer.install(self.source, self.dest)
        self.assertEqual(result['sha256'], expected)
        self.assertEqual(installer.manifest(self.dest / 'codex-organizer'), expected)
        self.assertEqual(installer.manifest(self.source), expected)

    def test_existing_custom_skill_is_unchanged(self):
        prior = self.dest / 'codex-organizer'; prior.mkdir(parents=True)
        sentinel = prior / 'mine.txt'; sentinel.write_text('customized')
        with self.assertRaises(FileExistsError): installer.install(self.source, self.dest)
        self.assertEqual(sentinel.read_text(), 'customized')
        self.assertEqual(list(prior.iterdir()), [sentinel])

    def test_symlink_destination_parent_refused(self):
        real = self.root / 'real'; real.mkdir()
        alias = self.root / 'alias'; alias.symlink_to(real, target_is_directory=True)
        with self.assertRaises(ValueError): installer.install(self.source, alias)
        self.assertEqual(list(real.iterdir()), [])

    def test_symlink_source_file_refused(self):
        outside = self.root / 'outside'; outside.write_text('untouched')
        (self.source / 'link.md').symlink_to(outside)
        with self.assertRaises(ValueError): installer.install(self.source, self.dest)
        self.assertFalse(self.dest.exists())

    def test_license_is_required(self):
        (self.source / 'LICENSE').unlink()
        with self.assertRaises(ValueError): installer.install(self.source, self.dest)
        self.assertFalse(self.dest.exists())

    def test_generated_caches_are_not_installed(self):
        cache = self.source / '__pycache__'; cache.mkdir()
        (cache / 'x.pyc').write_bytes(b'generated')
        installer.install(self.source, self.dest)
        self.assertFalse((self.dest / 'codex-organizer' / '__pycache__').exists())

    def test_nested_destination_refused_before_creation(self):
        with self.assertRaises(ValueError): installer.install(self.source, self.source / 'nested')
        self.assertFalse((self.source / 'nested').exists())

    def test_disguised_nested_destination_with_traversal_is_refused(self):
        outside = self.root / 'outside'; outside.mkdir()
        disguised = outside / '..' / 'source' / 'nested'
        before = installer.manifest(self.source)
        with self.assertRaises(ValueError): installer.install(self.source, disguised)
        self.assertEqual(installer.manifest(self.source), before)
        self.assertFalse((self.source / 'nested').exists())
