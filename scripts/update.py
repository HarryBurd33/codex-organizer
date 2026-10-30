#!/usr/bin/env python3
"""Preview or recoverably update a known, unmodified Organizer installation."""
import argparse
from contextlib import contextmanager
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def attributes(path):
    if hasattr(os, 'listxattr'):
        return {name: hashlib.sha256(os.getxattr(path, name)).hexdigest()
                for name in os.listxattr(path)}
    if sys.platform == 'darwin':
        names = subprocess.check_output(['/usr/bin/xattr', str(path)], text=True).splitlines()
        result = {}
        for name in names:
            value = subprocess.check_output(['/usr/bin/xattr', '-px', name, str(path)], text=True)
            result[name] = hashlib.sha256(bytes.fromhex(value)).hexdigest()
        return result
    raise ValueError('Extended metadata inspection is unavailable')


def checked(path, directory=True):
    path = Path(path).absolute()
    if '..' in path.parts or '\n' in str(path) or '\r' in str(path):
        raise ValueError('Unsafe path')
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('Linked paths are refused')
    if directory and not path.is_dir():
        raise ValueError('Expected an existing directory')
    return path


def snapshot(root, ignore_generated=False):
    root = checked(root)
    rows, files, total = {}, {}, 0
    for count, path in enumerate(itertools.chain([root], root.rglob('*'))):
        if count >= 2048:
            raise ValueError('Entry limit')
        relative = path.relative_to(root)
        if path.name.lower().startswith('.env') or path.name.lower() in {'.git','.checkpoint','.private','auth.json','credentials.json'}:
            raise ValueError('Private state or credential-like files are not skill resources')
        generated = ignore_generated and ('__pycache__' in relative.parts or path.suffix == '.pyc')
        if path.is_symlink() and generated:
            continue
        if path.is_symlink():
            raise ValueError('Linked skill content')
        s = path.stat()
        if not stat.S_ISDIR(s.st_mode) and not stat.S_ISREG(s.st_mode):
            raise ValueError('Nonregular skill content')
        if stat.S_ISREG(s.st_mode):
            total += s.st_size
            if total > 64 * 1024 * 1024: raise ValueError('Byte limit')
        if generated: continue
        key = path.relative_to(root).as_posix()
        row = {'mode': stat.S_IMODE(s.st_mode), 'uid': s.st_uid, 'gid': s.st_gid,
               'inode': s.st_ino, 'device': s.st_dev, 'mtime': s.st_mtime_ns,
               'kind': 'dir' if path.is_dir() else 'file', 'links': s.st_nlink,
               'flags': getattr(s, 'st_flags', 0)}
        if row['kind'] == 'file':
            content = path.read_bytes(); after = path.stat()
            if (s.st_ino, s.st_size, s.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError('Content changed during inspection')
            files[key] = hashlib.sha256(content).hexdigest()
        row['xattrs'] = attributes(path)
        if sys.platform == 'darwin':
            acl = subprocess.check_output(['/bin/ls', '-lde', str(path)], text=True).splitlines()[1:]
            row['acl'] = digest(acl)
        else:
            row['acl'] = None  # Linux access ACLs are included in xattrs.
        rows[key] = row
    if not {'SKILL.md', 'LICENSE'} <= files.keys():
        raise ValueError('Expected a complete skill and license')
    skill = (root/'SKILL.md').read_text()
    if not skill.startswith('---\n') or len(skill.split('---', 2)) != 3:
        raise ValueError('Missing skill frontmatter')
    header = skill.split('---', 2)[1]
    if not re.search(r'^name: codex-organizer$', header, re.M):
        raise ValueError('Wrong skill identity')
    version = re.search(r'^\s+version:\s*["\']?(\d+\.\d+\.\d+)(?=["\'\s]|$)', header, re.M)
    if not version: raise ValueError('Expected a stable three-part skill version')
    return {'rows': rows, 'files': files, 'version': version.group(1)}


def plain_metadata(root, state):
    if os.name != 'posix':
        raise ValueError('Replacement supports local POSIX filesystems only')
    for name, row in state['rows'].items():
        if row['uid'] != os.getuid() or row['mode'] & 0o7000 or row['flags']:
            raise ValueError('Foreign ownership, special mode or file flags require review')
        if row['kind'] == 'file' and row['links'] != 1:
            raise ValueError('Hard-linked files require separate review')


def plan(source, target, backup_parent, known):
    source, target = checked(source), checked(target)
    if target.name != 'codex-organizer' or source == target or source in target.parents or target in source.parents:
        raise ValueError('Source and installed skill must be independent')
    old, new = snapshot(target), snapshot(source, ignore_generated=True)
    old_dirs = {k for k,v in old['rows'].items() if v['kind'] == 'dir'}
    new_dirs = {k for k,v in new['rows'].items() if v['kind'] == 'dir'}
    action = 'already-current' if old['files'] == new['files'] and old_dirs == new_dirs else 'update'
    if action == 'update' and old['files'] not in known.values():
        raise ValueError('Unknown or customized installation; no overwrite')
    if action == 'update' and tuple(map(int,new['version'].split('.'))) <= tuple(map(int,old['version'].split('.'))):
        raise ValueError('Refusing a downgrade or changed same-version payload')
    if action == 'update' and any((p/'.git').exists() or (p/'.checkpoint').exists() for p in [target,*target.parents]):
        raise ValueError('Project/checkpoint installations need separate ownership review')
    expected_dirs = {'.'}
    for filename in old['files']:
        expected_dirs.update(str(p) for p in Path(filename).parents)
    if action == 'update' and old_dirs != expected_dirs:
        raise ValueError('Customized directory layout; no overwrite')
    if any(old['rows'][k]['kind'] != new['rows'][k]['kind'] for k in old['rows'].keys() & new['rows'].keys()):
        raise ValueError('File/directory type changes need separate review')
    backup = checked(backup_parent) if backup_parent is not None else None
    if action == 'update':
        if backup is None or source == backup or source in backup.parents or target == backup or target in backup.parents:
            raise ValueError('Select an existing backup parent outside both skills')
        if backup.stat().st_uid != os.getuid() or stat.S_IMODE(backup.stat().st_mode) & 0o022:
            raise ValueError('Backup parent must be owned by you and not writable by others')
        if {'system.posix_acl_access','system.posix_acl_default'} & attributes(backup).keys():
            raise ValueError('Backup parent ACL requires separate privacy review')
        if sys.platform == 'darwin' and len(subprocess.check_output(['/bin/ls','-lde',str(backup)],text=True).splitlines()) != 1:
            raise ValueError('Backup parent ACL requires separate privacy review')
        if not backup.stat().st_dev == target.parent.stat().st_dev == target.stat().st_dev:
            raise ValueError('Backup must be on the same filesystem')
        plain_metadata(source, new); plain_metadata(target, old)
    identity = {'source': str(source), 'target': str(target), 'backup': str(backup) if backup else None,
                'before': old, 'source_snapshot': new}
    return {'action': action, 'preview_sha256': digest(identity), **identity,
            'added': sorted(new['rows'].keys()-old['rows'].keys()),
            'removed': sorted(old['rows'].keys()-new['rows'].keys()),
            'changed': sorted(k for k in old['files'].keys() & new['files'].keys()
                              if old['files'][k] != new['files'][k])}


@contextmanager
def operation_lock(target):
    lock = target.parent/'.codex-organizer-update.lock'
    token = uuid.uuid4().hex
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    own = os.fstat(fd)
    try:
        os.write(fd, token.encode()); os.fsync(fd); os.close(fd); fd = None
        yield
    finally:
        if fd is not None: os.close(fd)
        if lock.exists() and lock.stat().st_ino == own.st_ino and lock.stat().st_dev == own.st_dev:
            if lock.read_text() == token: lock.unlink()


def write_receipt(path, value):
    encoded = json.dumps(value, indent=2)+'\n'
    if len(encoded.encode()) > 4 * 1024 * 1024:
        raise ValueError('Receipt metadata exceeds the supported bound')
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(encoded); output.flush(); os.fsync(output.fileno())
    os.replace(temporary, path)


def transfer_metadata(staged, before):
    for name, row in before['rows'].items():
        path = staged/name
        if not path.exists(): continue
        if path.stat().st_uid != row['uid'] or path.stat().st_gid != row['gid']:
            os.chown(path, row['uid'], row['gid'])
        if stat.S_IMODE(path.stat().st_mode) != row['mode']:
            os.chmod(path, row['mode'])


def copy_preserving(source, destination):
    if sys.platform == 'darwin':
        subprocess.run(['/bin/cp', '-pRP', str(source), str(destination)], check=True,
                       capture_output=True, text=True)
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination)


def stage_payload(source, target, staged, before, wanted):
    # Clone existing metadata first. Never truncate a file in the real install.
    copy_preserving(target, staged)
    for name in before['files'].keys()-wanted['files'].keys():
        (staged/name).unlink()
    old_dirs = {k for k,v in before['rows'].items() if v['kind'] == 'dir'}
    new_dirs = {k for k,v in wanted['rows'].items() if v['kind'] == 'dir'}
    for name in sorted(old_dirs-new_dirs, key=lambda p: len(Path(p).parts), reverse=True):
        (staged/name).rmdir()
    for name in sorted(new_dirs, key=lambda p: len(Path(p).parts)):
        if not (staged/name).exists(): copy_preserving(source/name, staged/name)
    for name in wanted['files']:
        if name in before['files']:
            # Truncation retains the staged clone's ACLs and extended attributes.
            with (staged/name).open('wb') as output: output.write((source/name).read_bytes())
        elif not (staged/name).exists():
            copy_preserving(source/name, staged/name)
    # Only operation-owned staging copies are pruned. Installed generated files
    # remain part of the strict baseline check and are never silently discarded.
    for path in sorted(staged.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        name = path.relative_to(staged).as_posix()
        if name in before['rows']: continue
        if path.name == '__pycache__' or path.suffix == '.pyc':
            if path.is_symlink() or path.is_file(): path.unlink()
            elif path.is_dir(): shutil.rmtree(path)
    transfer_metadata(staged, before)
    observed = snapshot(staged)
    if observed['files'] != wanted['files']:
        raise RuntimeError('Staged payload mismatch')
    for name in before['rows'].keys() & observed['rows'].keys():
        for field in ['mode', 'uid', 'gid', 'xattrs', 'acl', 'flags']:
            if before['rows'][name][field] != observed['rows'][name][field]:
                raise RuntimeError('Metadata could not be preserved: '+name+' '+field)


def update(source, target, backup_parent, known, apply=False, expected=None):
    prepared = plan(source, target, backup_parent, known)
    if not apply: return prepared
    if expected != prepared['preview_sha256']:
        raise ValueError('Preview changed or was not acknowledged')
    if prepared['action'] == 'already-current': return prepared
    source, target, backup = checked(source), checked(target), checked(backup_parent)
    with operation_lock(target):
        if plan(source, target, backup, known)['preview_sha256'] != expected:
            raise ValueError('State changed before operation')
        operation = Path(tempfile.mkdtemp(prefix='codex-organizer-update-', dir=backup))
        receipt = operation/'receipt.json'; original = operation/'original'; staged = operation/'staged'
        record = {'schema_version': 1, 'target': str(target), 'before': prepared['before'],
                  'status': 'preparing', 'original': str(original)}
        write_receipt(receipt, record)
        stage_payload(source, target, staged, prepared['before'], prepared['source_snapshot'])
        if snapshot(staged)['files'] != prepared['source_snapshot']['files']:
            raise RuntimeError('Staging changed; original installation is intact: '+str(receipt))
        if snapshot(source, ignore_generated=True) != prepared['source_snapshot'] or snapshot(target) != prepared['before']:
            raise RuntimeError('Source/install drift; original installation is intact: '+str(receipt))
        projected = dict(record, status='installed', after=snapshot(staged))
        if len((json.dumps(projected, indent=2)+'\n').encode()) > 4 * 1024 * 1024:
            raise ValueError('Activation receipt would exceed the supported bound; original intact')
        try:
            os.rename(target, original)
            if snapshot(original) != prepared['before'] or target.exists():
                raise RuntimeError('State changed during backup')
            os.rename(staged, target)
            after = snapshot(target)
            if after['files'] != prepared['source_snapshot']['files']:
                raise RuntimeError('Activated payload changed')
            record.update(status='installed', after=after)
            write_receipt(receipt, record)
        except BaseException as error:
            record['status'] = 'uncertain-preserved'
            try:
                if original.exists() and not target.exists():
                    os.rename(original, target); record['status'] = 'failed-rolled-back'
            except OSError as rollback_error:
                record['rollback_error'] = str(rollback_error)
            try:
                write_receipt(receipt, record)
            except (OSError,ValueError) as receipt_error:
                record['receipt_error'] = str(receipt_error)
            raise RuntimeError('Update failed; inspect retained copies and receipt: '+str(receipt)) from error
    return {'action': 'updated', 'receipt': str(receipt), 'backup': str(original)}


def restore(target, receipt, apply=False, expected=None):
    target = checked(target); receipt = checked(receipt, directory=False)
    if receipt.name != 'receipt.json' or not receipt.is_file():
        raise ValueError('Expected an operation receipt')
    if receipt.stat().st_size > 4 * 1024 * 1024 or receipt.stat().st_uid != os.getuid() or receipt.stat().st_nlink != 1:
        raise ValueError('Receipt size or ownership is unsafe')
    record = json.loads(receipt.read_text())
    if not isinstance(record, dict) or record.get('schema_version') != 1:
        raise ValueError('Unsupported receipt schema')
    original = checked(receipt.parent/'original')
    if record.get('status') != 'installed' or record.get('target') != str(target) or record.get('original') != str(original):
        raise ValueError('Receipt identity/state mismatch')
    before, current = snapshot(original), snapshot(target)
    if before != record.get('before') or current != record.get('after'):
        raise ValueError('Backup or installed content/metadata changed; preserve both')
    if target.parent.stat().st_dev != original.stat().st_dev:
        raise ValueError('Restore requires one filesystem')
    plain_metadata(target, current); plain_metadata(original, before)
    token = digest({'receipt': str(receipt), 'record': record, 'current': current})
    result = {'action': 'restore', 'preview_sha256': token, 'receipt': str(receipt)}
    if not apply: return result
    if expected != token: raise ValueError('Restore preview changed or not acknowledged')
    displaced = receipt.parent/'updated-before-restore'
    with operation_lock(target):
        if snapshot(target) != current or snapshot(original) != before or displaced.exists():
            raise ValueError('State changed before restore')
        try:
            os.rename(target, displaced); os.rename(original, target)
            if snapshot(target) != before: raise RuntimeError('Restore verification failed')
            record['status'] = 'restored'; write_receipt(receipt, record)
        except BaseException as error:
            record['status'] = 'restore-uncertain-preserved'
            try:
                if displaced.exists() and not target.exists(): os.rename(displaced, target)
            except OSError as rollback_error:
                record['rollback_error'] = str(rollback_error)
            try:
                write_receipt(receipt, record)
            except (OSError,ValueError) as receipt_error:
                record['receipt_error'] = str(receipt_error)
            raise RuntimeError('Restore failed; inspect retained copies: '+str(receipt)) from error
    return {'action': 'restored', 'receipt': str(receipt), 'updated_copy': str(displaced)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, default=Path.home()/'.agents/skills', help='existing skills parent')
    parser.add_argument('--backup-parent', type=Path)
    parser.add_argument('--restore-receipt', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expect-preview')
    args = parser.parse_args()
    try:
        parent = checked(args.dest); target = parent/'codex-organizer'
        if args.restore_receipt:
            result = restore(target, args.restore_receipt, args.apply, args.expect_preview)
        else:
            known = json.loads((ROOT/'scripts/release-manifests.json').read_text())['releases']
            result = update(ROOT/'skills/codex-organizer', target, args.backup_parent,
                            known, args.apply, args.expect_preview)
        if 'before' in result and 'source_snapshot' in result:
            result = {k:result[k] for k in ['action','preview_sha256','source','target','backup','added','removed','changed']} | {
                'installed_version':result['before']['version'], 'source_version':result['source_snapshot']['version']}
        print(json.dumps(result, indent=2)); return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({'error': str(error), 'action': 'inspect-before-retry'})); return 2


if __name__ == '__main__':
    raise SystemExit(main())
