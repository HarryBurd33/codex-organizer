import errno
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('guarded_update', Path(__file__).resolve().parents[1]/'scripts/update.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.target = self.root/'skills/codex-organizer'; self.target.mkdir(parents=True)
        (self.target/'SKILL.md').write_text('---\nname: codex-organizer\nmetadata:\n  version: "0.1.0"\n---\nold release\n')
        (self.target/'LICENSE').write_text('fixture notice')
        self.target.chmod(0o750); (self.target/'SKILL.md').chmod(0o640)
        self.old = m.snapshot(self.target); self.known = {'fixture-old':self.old['files']}
        self.source = self.root/'source'; shutil.copytree(self.target,self.source)
        (self.source/'SKILL.md').write_text('---\nname: codex-organizer\nmetadata:\n  version: "0.2.0"\n---\nnew release\n')
        (self.source/'new.txt').write_text('new resource')
        self.backups = self.root/'backups'; self.backups.mkdir()

    def preview(self): return m.update(self.source,self.target,self.backups,self.known)

    def apply(self):
        preview = self.preview()
        return m.update(self.source,self.target,self.backups,self.known,True,preview['preview_sha256'])

    def test_preview_is_read_only(self):
        before = m.snapshot(self.target)
        result = self.preview()
        self.assertEqual(result['action'],'update')
        self.assertEqual(m.snapshot(self.target),before)
        self.assertEqual(list(self.backups.iterdir()),[])
        self.assertFalse((self.target.parent/'.codex-organizer-update.lock').exists())

    def test_upgrade_and_restore_preserve_original_inodes_owner_and_modes(self):
        result = self.apply(); original = Path(result['backup'])
        self.assertEqual(m.snapshot(original),self.old)
        current = m.snapshot(self.target)
        for name,row in self.old['rows'].items():
            self.assertEqual([current['rows'][name][k] for k in ['mode','uid','gid']],
                             [row[k] for k in ['mode','uid','gid']])
        self.assertEqual(current['files'],m.snapshot(self.source)['files'])
        receipt = Path(result['receipt']); preview = m.restore(self.target,receipt)
        restored = m.restore(self.target,receipt,True,preview['preview_sha256'])
        self.assertEqual(m.snapshot(self.target),self.old)
        self.assertTrue(Path(restored['updated_copy']).is_dir())

    def test_custom_content_refuses_without_writes(self):
        (self.target/'SKILL.md').write_text('my customized skill')
        before = {p:p.read_bytes() for p in self.target.iterdir()}
        with self.assertRaises(ValueError): self.preview()
        self.assertEqual(before,{p:p.read_bytes() for p in self.target.iterdir()})
        self.assertEqual(list(self.backups.iterdir()),[])

    def test_unknown_release_and_extra_file_refuse(self):
        with self.assertRaises(ValueError): m.update(self.source,self.target,self.backups,{})
        (self.target/'notes.md').write_text('keep')
        with self.assertRaises(ValueError): self.preview()
        self.assertEqual((self.target/'notes.md').read_text(),'keep')

    def test_custom_empty_directory_refuses(self):
        (self.target/'personal-empty-folder').mkdir()
        with self.assertRaises(ValueError): self.preview()
        self.assertTrue((self.target/'personal-empty-folder').is_dir())

    def test_stale_source_preview_refuses(self):
        preview = self.preview(); (self.source/'new.txt').write_text('changed after review')
        with self.assertRaises(ValueError):
            m.update(self.source,self.target,self.backups,self.known,True,preview['preview_sha256'])
        self.assertEqual(m.snapshot(self.target),self.old)

    def test_installed_edit_after_preview_refuses(self):
        preview = self.preview(); (self.target/'LICENSE').write_text('personal notice')
        with self.assertRaises(ValueError):
            m.update(self.source,self.target,self.backups,self.known,True,preview['preview_sha256'])
        self.assertEqual((self.target/'LICENSE').read_text(),'personal notice')

    def test_foreign_operation_lock_is_untouched(self):
        lock=self.target.parent/'.codex-organizer-update.lock'; lock.write_text('someone else')
        with self.assertRaises(FileExistsError): self.apply()
        self.assertEqual(lock.read_text(),'someone else')
        self.assertEqual(m.snapshot(self.target),self.old)

    def test_symlink_and_traversal_refuse(self):
        link=self.root/'link'; link.symlink_to(self.source)
        with self.assertRaises(ValueError):m.update(link,self.target,self.backups,self.known)
        with self.assertRaises(ValueError):m.checked(self.root/'source/../skills')
        (self.source/'linked').symlink_to(self.target/'LICENSE')
        with self.assertRaises(ValueError):self.preview()

    def test_activation_failure_rolls_back_original(self):
        rename=os.rename; calls=[]
        def fail_second(source,target):
            calls.append((source,target))
            if len(calls)==2:raise OSError(errno.EXDEV,'injected activation failure')
            return rename(source,target)
        with patch.object(m.os,'rename',side_effect=fail_second),self.assertRaises(RuntimeError):self.apply()
        self.assertEqual(m.snapshot(self.target),self.old)
        receipt=next(self.backups.glob('*/receipt.json'))
        self.assertEqual(json.loads(receipt.read_text())['status'],'failed-rolled-back')

    def test_activation_collision_preserves_both_copies(self):
        rename=os.rename; calls=[]
        def collide(source,target):
            calls.append((source,target))
            if len(calls)==2:
                Path(target).mkdir(); (Path(target)/'concurrent.txt').write_text('keep concurrent work')
                raise FileExistsError('injected concurrent destination')
            return rename(source,target)
        with patch.object(m.os,'rename',side_effect=collide),self.assertRaises(RuntimeError):self.apply()
        self.assertEqual((self.target/'concurrent.txt').read_text(),'keep concurrent work')
        original=next(self.backups.glob('*/original'))
        self.assertEqual(m.snapshot(original),self.old)

    def test_restore_refuses_post_upgrade_edit(self):
        result=self.apply(); (self.target/'new.txt').write_text('new personal edit')
        with self.assertRaises(ValueError):m.restore(self.target,Path(result['receipt']))
        self.assertEqual((self.target/'new.txt').read_text(),'new personal edit')
        self.assertEqual(m.snapshot(Path(result['backup'])),self.old)

    def test_already_equal_apply_creates_no_backup_or_lock(self):
        shutil.rmtree(self.source); shutil.copytree(self.target,self.source)
        preview=self.preview(); before=m.snapshot(self.target)
        result=m.update(self.source,self.target,self.backups,self.known,True,preview['preview_sha256'])
        self.assertEqual(result['action'],'already-current');self.assertEqual(m.snapshot(self.target),before)
        self.assertEqual(list(self.backups.iterdir()),[])

    def test_foreign_owner_context_refuses_actual_replacement(self):
        with patch.object(m.os,'getuid',return_value=os.getuid()+1),self.assertRaises(ValueError):self.preview()
        self.assertEqual(m.snapshot(self.target),self.old)

    def test_extended_attributes_are_preserved_through_update_and_restore(self):
        try:
            if sys.platform == 'darwin':
                subprocess.run(['/usr/bin/xattr','-wx','user.codex-test',b'keep'.hex(),str(self.target/'LICENSE')],check=True,capture_output=True)
            else:
                os.setxattr(self.target/'LICENSE','user.codex-test',b'keep')
        except (OSError,subprocess.CalledProcessError):self.skipTest('Filesystem does not support fixture xattrs')
        before=m.snapshot(self.target); result=self.apply()
        self.assertIn('user.codex-test',m.attributes(self.target/'LICENSE'))
        self.assertEqual(m.snapshot(Path(result['backup'])),before)
        receipt=Path(result['receipt']); preview=m.restore(self.target,receipt)
        m.restore(self.target,receipt,True,preview['preview_sha256'])
        self.assertEqual(m.snapshot(self.target),before)

    def test_unpreservable_metadata_fails_before_activation(self):
        with patch.object(m,'transfer_metadata',side_effect=OSError('injected metadata failure')):
            with self.assertRaises(OSError):self.apply()
        self.assertEqual(m.snapshot(self.target),self.old)

    def test_nested_resource_replacement_retains_original_backup(self):
        (self.target/'old').mkdir();(self.target/'old/resource.md').write_text('old resource')
        self.old=m.snapshot(self.target);self.known={'fixture-old':self.old['files']}
        shutil.rmtree(self.source);shutil.copytree(self.target,self.source)
        (self.source/'SKILL.md').write_text((self.source/'SKILL.md').read_text().replace('0.1.0','0.2.0'))
        (self.source/'old/resource.md').unlink();(self.source/'old').rmdir()
        (self.source/'new/deep').mkdir(parents=True);(self.source/'new/deep/resource.md').write_text('new resource')
        result=self.apply()
        self.assertEqual(m.snapshot(Path(result['backup'])),self.old)
        self.assertEqual((self.target/'new/deep/resource.md').read_text(),'new resource')
        self.assertFalse((self.target/'old').exists())

    def test_backup_inside_skill_is_refused(self):
        with self.assertRaises(ValueError):m.update(self.source,self.target,self.target,self.known)
        self.assertEqual(m.snapshot(self.target),self.old)

    def test_replaced_operation_lock_is_not_deleted(self):
        lock=self.target.parent/'.codex-organizer-update.lock'
        with m.operation_lock(self.target):
            lock.unlink();lock.write_text('different writer')
        self.assertEqual(lock.read_text(),'different writer')

    def test_restore_failure_keeps_updated_installation_and_original_backup(self):
        result=self.apply();receipt=Path(result['receipt']);preview=m.restore(self.target,receipt)
        updated=m.snapshot(self.target);rename=os.rename;calls=[]
        def fail_second(source,target):
            calls.append((source,target))
            if len(calls)==2:raise OSError('injected restore activation failure')
            return rename(source,target)
        with patch.object(m.os,'rename',side_effect=fail_second),self.assertRaises(RuntimeError):
            m.restore(self.target,receipt,True,preview['preview_sha256'])
        self.assertEqual(m.snapshot(self.target),updated)
        self.assertEqual(m.snapshot(Path(result['backup'])),self.old)

    def test_macos_acl_preserved(self):
        if sys.platform!='darwin':self.skipTest('macOS-specific ACL evidence')
        subprocess.run(['/bin/chmod','+a','everyone allow read',str(self.target/'LICENSE')],check=True,capture_output=True)
        before=m.snapshot(self.target);result=self.apply()
        self.assertEqual(m.snapshot(self.target)['rows']['LICENSE']['acl'],before['rows']['LICENSE']['acl'])
        self.assertEqual(m.snapshot(Path(result['backup'])),before)

    def test_older_source_release_is_not_a_downgrade_target(self):
        (self.source/'SKILL.md').write_text((self.source/'SKILL.md').read_text().replace('0.2.0','0.0.9'))
        with self.assertRaises(ValueError):self.preview()
        self.assertEqual(m.snapshot(self.target),self.old)

    def test_changed_same_version_source_is_refused(self):
        (self.source/'SKILL.md').write_text((self.source/'SKILL.md').read_text().replace('0.2.0','0.1.0'))
        with self.assertRaises(ValueError):self.preview()
        self.assertEqual(m.snapshot(self.target),self.old)

    def test_source_bytecode_is_excluded_like_the_installer(self):
        (self.source/'code/__pycache__').mkdir(parents=True)
        (self.source/'code/helper.py').write_text('pass\n')
        (self.source/'code/__pycache__/helper.pyc').write_bytes(b'generated')
        result=self.apply()
        self.assertFalse((self.target/'code/__pycache__').exists())
        self.assertTrue((self.source/'code/__pycache__/helper.pyc').exists())
        self.assertEqual(m.snapshot(Path(result['backup'])),self.old)

    def test_installed_bytecode_is_not_silently_removed(self):
        (self.target/'__pycache__').mkdir();(self.target/'__pycache__/old.pyc').write_bytes(b'keep')
        with self.assertRaises(ValueError):self.preview()
        self.assertEqual((self.target/'__pycache__/old.pyc').read_bytes(),b'keep')

    def test_generated_source_link_is_not_followed(self):
        outside=self.root/'outside';outside.mkdir();(outside/'private.txt').write_text('outside content')
        (self.source/'code').mkdir();(self.source/'code/helper.py').write_text('pass\n')
        (self.source/'code/__pycache__').symlink_to(outside,target_is_directory=True)
        self.apply()
        self.assertFalse((self.target/'code/__pycache__').exists())
        self.assertEqual((outside/'private.txt').read_text(),'outside content')

    def test_git_checkout_destination_is_review_only(self):
        (self.root/'.git').mkdir()
        with self.assertRaises(ValueError):self.preview()
        self.assertEqual(m.snapshot(self.target),self.old)

    def test_checkpoint_bound_destination_is_review_only(self):
        (self.root/'.checkpoint').mkdir()
        with self.assertRaises(ValueError):self.preview()
        self.assertEqual(m.snapshot(self.target),self.old)

    def test_shared_writable_backup_parent_is_refused(self):
        self.backups.chmod(0o777)
        with self.assertRaises(ValueError):self.preview()
        self.assertEqual(m.snapshot(self.target),self.old)

    def test_backup_parent_acl_requires_privacy_review(self):
        if sys.platform!='darwin':self.skipTest('macOS-specific backup ACL evidence')
        subprocess.run(['/bin/chmod','+a','everyone allow read',str(self.backups)],check=True,capture_output=True)
        with self.assertRaises(ValueError):self.preview()
        self.assertEqual(m.snapshot(self.target),self.old)

    def test_private_source_resources_are_refused(self):
        (self.source/'.env').write_text('fixture secret')
        with self.assertRaises(ValueError):self.preview()
        self.assertEqual(m.snapshot(self.target),self.old)
        self.assertEqual(list(self.backups.iterdir()),[])

    def test_receipt_failure_reports_recovery_path_and_keeps_both_payloads(self):
        write=m.write_receipt
        def fail_after_preparation(path,value):
            if value['status']!='preparing':raise OSError(errno.ENOSPC,'injected receipt failure')
            return write(path,value)
        with patch.object(m,'write_receipt',side_effect=fail_after_preparation),self.assertRaises(RuntimeError) as failure:
            self.apply()
        self.assertIn(str(self.backups),str(failure.exception))
        original=next(self.backups.glob('*/original'))
        self.assertEqual(m.snapshot(original),self.old)
        self.assertEqual(m.snapshot(self.target)['files'],m.snapshot(self.source)['files'])
