#!/usr/bin/env python3
"""Install this repository's Codex Organizer skill without overwriting a skill."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat


def no_symlinks(path):
    if '..' in path.parts:
        raise ValueError('parent-traversal paths are not supported: ' + str(path))
    path = path.absolute()
    for item in [*reversed(path.parents), path]:
        if item.is_symlink():
            raise ValueError('symlink paths are not supported: ' + str(item))
    return path


def manifest(source):
    no_symlinks(source)
    result = {}
    for p in sorted(source.rglob('*')):
        if '__pycache__' in p.parts or p.suffix == '.pyc':
            continue
        if p.is_symlink():
            raise ValueError('skill contains a symlink: ' + str(p))
        if p.is_dir():
            continue
        if not stat.S_ISREG(p.stat().st_mode):
            raise ValueError('skill contains a non-regular file: ' + str(p))
        if p.name.startswith('.env') or p.name in {'auth.json', 'credentials.json'}:
            raise ValueError('credential-like file in skill')
        result[p.relative_to(source).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    if 'SKILL.md' not in result or 'LICENSE' not in result:
        raise ValueError('source requires SKILL.md and LICENSE')
    return result


def install(source, destination_parent):
    source = no_symlinks(Path(source))
    parent = no_symlinks(Path(destination_parent))
    expected = manifest(source)
    destination = parent / 'codex-organizer'
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('existing skill preserved: ' + str(destination))
    if parent == source or source in parent.parents:
        raise ValueError('installation destination must be outside the source skill')
    parent.mkdir(parents=True, exist_ok=True)
    # copytree creates destination exclusively; an existing directory is never merged.
    # On a partial failure preserve it for inspection rather than deleting user data.
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    observed = manifest(destination)
    if expected != observed or expected != manifest(source):
        raise RuntimeError('source changed or installed hashes differ; inspect partial installation before retry')
    return {'installed': str(destination), 'files': len(observed), 'sha256': observed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, default=Path.home() / '.agents' / 'skills', help='parent skills directory')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / 'skills' / 'codex-organizer'
    try:
        print(json.dumps(install(source, args.dest), indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({'error': str(exc), 'note': 'Existing or partial installations are preserved. Inspect before retrying.'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
