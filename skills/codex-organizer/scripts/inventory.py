#!/usr/bin/env python3
"""Bounded read-only metadata survey. No content reads or cleanup operations."""
import argparse
import json
import os
from pathlib import Path
import stat
import time


PROTECTED = {'.git', '.checkpoint', '.checkpoints', '.private', '.aws', '.ssh', '.codex',
             '.agents', '.gnupg', '.azure', '.kube', 'node_modules', '.venv', '__pycache__', 'credentials',
             'auth.json', 'credentials.json', 'sessions', 'archived_sessions',
             'automations', 'plugins', 'worktrees', 'checkpoint-handoff',
             'codex', 'auth', 'secrets', 'tokens'}


def protected(name):
    n = name.casefold()
    return (n in PROTECTED or n == '.env' or n.startswith('.env.')
            or n.endswith(('.pem', '.key', '.p12', '.pfx', '.sqlite', '.sqlite3', '.db'))
            or '.sqlite-' in n or n.endswith(('-wal', '-shm')))


def checked_root(value):
    path = Path(os.path.abspath(value))
    for ancestor in [*reversed(path.parents), path]:
        if ancestor.is_symlink():
            raise ValueError('root or ancestor is a symlink')
    for i, part in enumerate(path.parts):
        if protected(part):
            user_project_parent = (part == '.codex' and i + 2 < len(path.parts)
                                   and path.parts[i + 1] == '.chatgpt-projects')
            if not user_project_parent:
                raise ValueError('root is inside protected or generated state')
    if not path.is_dir() or path == Path(path.anchor):
        raise ValueError('root must be an ordinary explicit project directory')
    return path


def survey(root, max_entries=500, max_depth=3, max_seconds=10):
    if not (1 <= max_entries <= 5000 and 1 <= max_depth <= 8 and 0 < max_seconds <= 30):
        raise ValueError('bounds: entries 1..5000, depth 1..8, seconds >0..30')
    root = checked_root(root)
    deadline = time.monotonic() + max_seconds
    result = {'root': str(root), 'entries': [], 'skipped': [], 'errors': [],
              'limits': {'entries': max_entries, 'depth': max_depth, 'seconds': max_seconds},
              'truncated': False, 'visited_entries': 0, 'scope': 'metadata only; usefulness unknown'}
    stack = [(root, 0)]
    while stack:
        folder, depth = stack.pop()
        if time.monotonic() >= deadline or result['visited_entries'] >= max_entries:
            result['truncated'] = True
            break
        if folder.is_symlink():
            result['skipped'].append({'path': str(folder.relative_to(root)), 'reason': 'symlink'})
            continue
        try:
            with os.scandir(folder) as items:
                for item in items:
                    if time.monotonic() >= deadline or result['visited_entries'] >= max_entries:
                        result['truncated'] = True
                        break
                    result['visited_entries'] += 1
                    rel = str(Path(item.path).relative_to(root))
                    try:
                        info = item.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode) or protected(item.name):
                            result['skipped'].append({'path': rel, 'reason': 'symlink' if stat.S_ISLNK(info.st_mode) else 'protected-or-generated'})
                            continue
                        is_dir = stat.S_ISDIR(info.st_mode)
                        kind = 'directory' if is_dir else 'file' if stat.S_ISREG(info.st_mode) else 'special'
                        result['entries'].append({'path': rel, 'type': kind,
                            'size_bytes': info.st_size if kind == 'file' else None,
                            'mtime_ns': info.st_mtime_ns})
                        if is_dir:
                            if depth + 1 < max_depth:
                                stack.append((Path(item.path), depth + 1))
                            else:
                                result['skipped'].append({'path': rel, 'reason': 'depth-limit'})
                                result['truncated'] = True
                    except OSError as exc:
                        result['errors'].append({'path': rel, 'error': type(exc).__name__})
        except OSError as exc:
            result['errors'].append({'path': str(folder.relative_to(root)), 'error': type(exc).__name__})
    result['complete_for_selected_root'] = not (result['truncated'] or result['errors'] or result['skipped'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--max-entries', type=int, default=500)
    parser.add_argument('--max-depth', type=int, default=3)
    parser.add_argument('--max-seconds', type=float, default=10)
    args = parser.parse_args()
    try:
        print(json.dumps(survey(args.root, args.max_entries, args.max_depth, args.max_seconds), indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': str(exc), 'complete_for_selected_root': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
