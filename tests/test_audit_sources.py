import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('audit_sources', Path(__file__).resolve().parents[1]/'scripts/audit_sources.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.installed = self.root/'installed'; self.installed.mkdir()
        self.source = self.root/'source'; self.source.mkdir()
        for root in [self.installed, self.source]:
            (root/'SKILL.md').write_text('---\nname: example\nmetadata:\n  version: "1.0.0"\n---\n')

    def comparison(self):
        return m.compare(m.manifest(self.installed), m.manifest(self.source))

    def test_identical_bytes_do_not_establish_source_authority_or_latest(self):
        result = self.comparison()
        self.assertEqual(result['status'], 'identical-candidate')
        self.assertEqual(result['source_authority'], 'unverified')
        self.assertEqual(result['upstream_freshness'], 'unknown')

    def test_same_version_custom_edit_is_different(self):
        (self.installed/'SKILL.md').write_text((self.installed/'SKILL.md').read_text()+'custom edit')
        self.assertEqual(self.comparison()['changed'], ['SKILL.md'])

    def test_additional_source_files_are_reported(self):
        (self.source/'new-resource.md').write_text('new')
        self.assertEqual(self.comparison()['status'], 'installed-subset-matches')

    def test_symlink_root_and_descendant_cannot_establish_equality(self):
        link = self.root/'link'; link.symlink_to(self.source)
        with self.assertRaises(ValueError): m.manifest(link)
        (self.source/'linked').symlink_to(self.installed/'SKILL.md')
        self.assertEqual(self.comparison()['status'], 'incomplete')

    def test_traversal_refused(self):
        with self.assertRaises(ValueError): m.manifest(self.root/'source/../installed')

    def test_receipts_and_caches_are_explicitly_ignored_without_removal(self):
        receipt=self.installed/'.install-receipt.json'; receipt.write_text('{}')
        (self.installed/'.skill-forge-managed.json').write_text('{}')
        self.assertEqual(self.comparison()['status'], 'identical-candidate')
        self.assertEqual(receipt.read_text(), '{}')

    def test_limits_are_partial_not_equal(self):
        with patch.object(m, 'MAX_FILES', 0):
            self.assertEqual(self.comparison()['status'], 'incomplete')

    def test_registry_with_unknown_source_is_read_only(self):
        before = {p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = m.audit({'skills':[{'name':'example','installed':str(self.installed)}]})
        self.assertEqual(result['skills'][0]['status'], 'source-unknown')
        self.assertEqual(before, {p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
