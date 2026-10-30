# Codex Organizer

A manual, decision-led Codex skill for reviewing clutter across project files, Git worktrees, chats and sidebar organization. It explains what each candidate is worth before asking you to **keep, move, archive, explain, or skip**.

## Install globally

Clone this repository and run its dependency-free installer (Python 3.9+):

```sh
git clone https://github.com/HarryBurd33/codex-organizer.git
cd codex-organizer
python3 scripts/install.py
```

This copies only `skills/codex-organizer/` into `~/.agents/skills/codex-organizer`, the user-global skill directory. It refuses an existing skill rather than overwriting customizations. Symlink and parent-traversal destinations are refused, including paths that disguise a destination inside the source. Review an existing copy before replacing it. For a custom skills parent use `python3 scripts/install.py --dest /absolute/skills-directory`.

Alternatively, ask Codex:

```text
Use $skill-installer to install the codex-organizer skill from
https://github.com/HarryBurd33/codex-organizer/tree/main/skills/codex-organizer
into my user-global ~/.agents/skills directory.
```

It should be available on the next turn. If it does not appear, start a fresh chat or restart Codex. A local installation applies to this account/computer's Codex setup; it does not install on other computers, accounts or cloud environments. See [official skill documentation](https://learn.chatgpt.com/docs/build-skills).

## Use it

### Update an existing installation

The optional updater previews by default. It accepts an unmodified installation
matching a shipped release manifest, and applies only a newer stable skill
version. Unknown/customized payloads, extra installed files or folders, stale
previews, project/checkpoint-owned targets and occupied updater locks require
review. A source matching the current installation returns `already-current`
without creating a lock, backup or replacement.

From a reviewed checkout, choose an existing private backup parent on the same
filesystem as the installation, owned by you and not writable by others:

```sh
python3 scripts/update.py --backup-parent /path/to/private-backups
python3 scripts/update.py --backup-parent /path/to/private-backups --apply --expect-preview REVIEWED_PREVIEW_SHA256
```

Use `--dest /path/to/skills` on both commands for a custom independent skills
parent. The updater preserves the original directory in a recovery folder and
verifies existing paths' ownership, permission bits, attributes and ACLs in the
staged replacement before activation. It refuses metadata it cannot preserve.
New resources come from the reviewed source. Source Python caches are excluded;
extra files in the installed skill are preserved by refusing the update.

To preview and apply recovery, use the receipt returned by the successful update:

```sh
python3 scripts/update.py --restore-receipt /path/to/operation/receipt.json
python3 scripts/update.py --restore-receipt /path/to/operation/receipt.json --apply --expect-preview REVIEWED_RESTORE_SHA256
```

Restore refuses if the backup or updated installation changed. Both old and new
copies are retained after a successful restore. No force-overwrite option is
provided. Keep actual receipts private; they include local paths and metadata.

Replacement supports local POSIX filesystems and stable paths with one cooperating
writer. macOS uses its built-in `cp`, `ls` and `xattr` utilities; Linux uses Python's
filesystem APIs. The updater lock does not lock other editors. Keep the skill idle
while applying: switching uses two directory renames, and an interruption or a
competing destination can require manual reconciliation. Windows, network
filesystem behavior and power-loss durability are not qualified by these tests.

### Run the organizer

In a local Codex chat:

```text
Use $codex-organizer. Review my projects and recent chats.
Explain each candidate's value and ask before changing anything.
```

Or: `Use $codex-organizer on this project only.`

Answer naturally: **Keep that**, **Move it instead**, **What would I lose?**, **Archive F-02**, or **Stop here**. A missing destination is resolved before moving. A bare yes after several proposals is clarified. Your decision applies to the described unchanged item; it is not standing permission for future deletions.

## What it supports

| Capability | Behavior and verification boundary |
|---|---|
| Project file review | Bounded metadata survey plus agent content/reference assessment. Scanner tests cover no writes, symlinks, protected paths, errors and limits. |
| Ordinary file move/archive/restore | Included Python helper, regular files on one local POSIX filesystem, no overwrite, current source hash and recovery receipts. 35 synthetic file-action tests pass, including actual archive/restore, collision and injected-failure cases. |
| Chats and sidebar | Uses the receiving host's available native Codex tools. No desktop tools are bundled; CLI-only hosts remain filesystem-only. A success receipt without readback stays unverified. |
| Managed worktrees | Uses supported native archive/restore tools and exact attachments, when available. Never raw directory deletion/prune. |
| Explain/keep/skip | Assessment or no-op, with no item mutation. The skill instructs this interaction; tests do not guarantee every future model decision. |

Archive means moving a file to a chosen archive directory, or a native recoverable chat/worktree archive. It is **not OS Trash** and does not empty a bin or permanently delete data. Folder moves, root project path changes, Windows/cross-filesystem file-helper moves and missing native integrations need a separate reviewed tool/plan or stay review-only. Another chat's unattached worktree cannot automatically be archived from the current chat. A chat archive can affect its managed worktree; the agent must disclose that first.

The helper expects a single cooperating writer and stable files/roots; it is not a sandbox or transactional filesystem. It makes no universal crash/network-filesystem durability claim. Read [file-action details](skills/codex-organizer/references/file-actions.md) and [native-tool limits](skills/codex-organizer/references/codex.md).

Global installation was verified through native Codex discovery in two unrelated working directories. All seven installed skill files matched the tested public source. The 58 automated checks passed in [public CI](https://github.com/HarryBurd33/codex-organizer/actions/runs/40456126147) on Ubuntu/macOS with Python 3.11/3.13.

## Verify the package

To inventory existing installations and candidate update sources without changing
them, create a **private** registry containing explicit local paths:

```json
{"skills":[{"name":"example","installed":"/path/to/installed/example","candidates":["/path/to/reviewed/source/example"]}]}
```

```sh
python3 scripts/audit_sources.py --registry /path/to/private-registry.json
```

The report contains versions, per-file hashes, differences and coverage limits.
It ignores listed installation receipts and Python/Git caches without removing
them. It refuses linked/traversing roots and reports skipped linked files or
limits as incomplete. Use stable files and roots; this is not a sandbox against
concurrent path replacement. Byte equality alone does not prove canonical source,
current upstream release, ownership or update permission. Verify those separately.
The command does not fetch, install, overwrite, acquire leases or upload results.
Its JSON includes local paths; keep actual registries and reports private.

```sh
python3 scripts/validate.py
python3 -B -m unittest discover -s tests -v
```

No third-party Python packages, API key, background service or paid model calls are required by the helpers. The conversational skill uses your normal Codex access. Detailed observed results and untested boundaries are in [validation](docs/validation.md). User run logs belong outside the installed skill and are not uploaded by these helpers.

The [current verification and remaining-work plan](docs/validation.md#update-verification-and-remaining-work--2026-10-30) distinguishes the shipped Organizer skill from optional local maintenance tools. Existing installations should be compared with the current skill files before replacement; the installer continues to protect an existing copy and its customizations.

## License

[MIT](LICENSE). A full license notice is also included in the installed skill. This is an independent community skill, not an official OpenAI product. [Provenance](docs/provenance.md).
