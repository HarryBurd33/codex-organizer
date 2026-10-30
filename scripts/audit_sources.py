#!/usr/bin/env python3
"""Compare explicitly selected skill installations and candidate sources; no writes."""
import argparse
import hashlib
import json
from pathlib import Path
import re


MAX_FILES = 5000
MAX_BYTES = 64 * 1024 * 1024
IGNORED = {'.git', '__pycache__', '.install-receipt.json', '.skill-forge-managed.json'}


def checked_root(value):
    root = Path(value).absolute()
    if '..' in root.parts or any(p.is_symlink() for p in [root, *root.parents]):
        raise ValueError('Linked or traversing roots are refused')
    if not root.is_dir():
        raise ValueError('Expected an existing directory')
    return root


def manifest(value):
    root = checked_root(value)
    files, errors, ignored = {}, [], []
    total = 0
    stack = [root]
    entries = 0
    while stack:
        directory = stack.pop()
        try:
            children = sorted(directory.iterdir())
        except OSError:
            errors.append('unreadable-directory:' + str(directory.relative_to(root)))
            continue
        for path in children:
            relative = path.relative_to(root).as_posix()
            entries += 1
            if entries > MAX_FILES:
                errors.append('entry-limit')
                stack.clear()
                break
            if path.name in IGNORED or path.suffix == '.pyc':
                ignored.append(relative)
                continue
            if path.is_symlink():
                errors.append('symlink:' + relative)
                continue
            try:
                if path.is_dir():
                    stack.append(path)
                    continue
                before = path.stat()
                import stat
                if not stat.S_ISREG(before.st_mode):
                    errors.append('nonregular:' + relative)
                    continue
                if total + before.st_size > MAX_BYTES:
                    errors.append('byte-limit:' + relative)
                    continue
                content = path.read_bytes()
                after = path.stat()
                if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                    errors.append('changed-during-read:' + relative)
                    continue
                total += len(content)
                files[relative] = hashlib.sha256(content).hexdigest()
            except OSError:
                errors.append('unreadable-file:' + relative)
    version = None
    if 'SKILL.md' in files:
        match = re.search(r'^\s+version:\s*["\']?([^"\'\n]+)', (root/'SKILL.md').read_text(), re.M)
        version = match.group(1) if match else None
    return {'root': str(root), 'version': version, 'files': files,
            'complete': not errors, 'errors': errors, 'ignored': ignored}


def compare(installed, candidate):
    missing = sorted(set(installed['files']) - set(candidate['files']))
    additional = sorted(set(candidate['files']) - set(installed['files']))
    changed = sorted(p for p in installed['files'].keys() & candidate['files'].keys()
                     if installed['files'][p] != candidate['files'][p])
    complete = installed['complete'] and candidate['complete']
    status = ('incomplete' if not complete else 'different' if missing or changed else
              'installed-subset-matches' if additional else 'identical-candidate')
    return {'status': status, 'missing': missing, 'additional': additional,
            'changed': changed, 'source_authority': 'unverified', 'upstream_freshness': 'unknown'}


def audit(registry):
    result = []
    for item in registry['skills']:
        installed = manifest(item['installed'])
        sources = []
        for path in item.get('candidates', []):
            candidate = manifest(path)
            sources.append({'candidate': candidate, 'comparison': compare(installed, candidate)})
        result.append({'name': item['name'], 'installed': installed, 'sources': sources,
                       'status': 'observed' if sources else 'source-unknown'})
    return {'schema_version': 1, 'read_only': True, 'skills': result,
            'limits': {'entries_per_root': MAX_FILES, 'bytes_per_root': MAX_BYTES},
            'claim': 'Byte comparisons only. Caller must verify canonical source, release, owner and current authority.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(args.registry.read_text())), indent=2))
