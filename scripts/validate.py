#!/usr/bin/env python3
"""Dependency-free package checks; behavioral/file-action tests run separately."""
import ast
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'codex-organizer'
REQUIRED = {
    'README.md', 'LICENSE', '.gitignore', '.github/workflows/tests.yml',
    'docs/validation.md', 'docs/provenance.md', 'scripts/install.py', 'scripts/validate.py',
    'tests/test_inventory.py', 'tests/test_file_actions.py', 'tests/test_install.py',
    'scripts/audit_sources.py', 'tests/test_audit_sources.py',
    'scripts/update.py', 'scripts/release-manifests.json', 'tests/test_update.py',
    'skills/codex-organizer/SKILL.md', 'skills/codex-organizer/LICENSE',
    'skills/codex-organizer/agents/openai.yaml',
    'skills/codex-organizer/scripts/inventory.py', 'skills/codex-organizer/scripts/file_actions.py',
    'skills/codex-organizer/references/codex.md', 'skills/codex-organizer/references/file-actions.md',
}


def validate(root=ROOT):
    errors = []
    for relative in sorted(REQUIRED):
        path = root / relative
        if not path.is_file() or path.is_symlink():
            errors.append('missing or linked required file: ' + relative)
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if any(p in {'.git', '__pycache__'} for p in relative.parts) or path.suffix == '.pyc':
            continue
        if path.is_symlink():
            errors.append('symlink: ' + str(relative))
            continue
        if path.is_dir():
            continue
        if relative.as_posix() not in REQUIRED:
            errors.append('unexpected public file: ' + str(relative))
        if any(p in {'.checkpoint', '.private', '.env', 'auth.json', 'credentials.json'} for p in relative.parts):
            errors.append('private state included: ' + str(relative))
        try:
            content = path.read_text(encoding='utf-8')
            if re.search(r'/(?:Users|home)/[A-Za-z0-9_]', content):
                errors.append('personal absolute path: ' + str(relative))
            if path.suffix == '.py':
                ast.parse(content, filename=str(relative))
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append(str(relative) + ': ' + str(exc))
    if not errors:
        skill = (root / 'skills/codex-organizer/SKILL.md').read_text()
        if not skill.startswith('---\n') or '\n---\n' not in skill[4:]:
            errors.append('missing skill frontmatter')
        else:
            header = skill.split('---', 2)[1]
            if not re.search(r'^name: codex-organizer$', header, re.M):
                errors.append('skill name differs from folder')
            if not re.search(r'^description: .{1,1024}$', header, re.M):
                errors.append('missing/oversized description')
        for target in re.findall(r'\]\(([^)]+)\)', skill):
            if '://' not in target and not (root / 'skills/codex-organizer' / target).is_file():
                errors.append('broken skill reference: ' + target)
        license_text = (root / 'LICENSE').read_text()
        if license_text != (root / 'skills/codex-organizer/LICENSE').read_text():
            errors.append('installed license differs from root license')
        if not all(part in license_text for part in ['MIT License', 'Permission is hereby granted', 'THE SOFTWARE IS PROVIDED "AS IS"']):
            errors.append('incomplete MIT notice')
    return {'ok': not errors, 'errors': errors, 'checked_public_files': len(REQUIRED),
            'scope': 'Package layout, Python syntax, notice and targeted privacy checks; not a behavioral or security proof.'}


if __name__ == '__main__':
    result = validate()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['ok'] else 1)
