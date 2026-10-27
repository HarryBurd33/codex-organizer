# Validation and claims

Version 0.2.2. Observations from release preparation on 2026-10-26 (America/Denver).

## Executed checks

- **58 automated tests passed** on local Python 3.9 and 3.15: 15 metadata survey boundary checks, 35 file-action checks and 8 installation checks.
- Actual synthetic archive/restore preserves content hash, inode, mode and modification time. Collision, stale-source, symlink, protected state, managed-worktree, receipt, injected EXDEV, fsync/update/unlink failure and interruption cases are covered. These do not simulate every crash or filesystem.
- Explain/review and ambiguous approval scenarios were run by an independent agent using fresh fixtures. File hashes and archive/receipt directories stayed unchanged. The reviewer separately performed five actual CLI calls: preview, applied archive, status, inverse restore and inverse status.
- The independent review found two defects, both saved and rechecked: scanner exclusions now cover credential/recovery stores and database sidecars; installer traversal paths that disguise a destination inside the source are refused before copying.
- The dependency-free 18-file package validator and Codex Skill Creator's metadata validator passed. The latter used PyYAML only in temporary authoring tools, not as a package dependency.
- A clean temporary installation copied all seven skill files with identical hashes and full MIT notice. Existing skill and symlink/traversal refusal tests passed.

## Conditional and untested behavior

Chat/sidebar/worktree operations require the receiving host's native tools and current access. They are not bundled desktop integrations. A native project-assignment tool accepted an approved action during authoring, but listings did not confirm membership. The operation was not repeated; the user subsequently confirmed the native sidebar showed the intended project assignment. This establishes that one project assignment, not every native action.

File operations support local POSIX regular files within one filesystem. Windows, directory moves, cross-filesystem moves, network filesystems, malicious concurrent path replacement and genuine power-loss durability were not verified. Fault injection is narrower evidence than real power loss. Single cooperating writer and stable roots are preconditions. There is no OS Trash or permanent-delete implementation.

The official Skill Installer installed immutable revision `dba0e78456c1b9e3f5b4af87c630180632e8c481`. All seven installed skill files matched the reviewed source hashes. A real local Codex app-server `skills/list` with forced reload found exactly one enabled `codex-organizer` at **user** scope from two unrelated working directories, with no load errors and no model turn. The [initial public CI run](https://github.com/HarryBurd33/codex-organizer/actions/runs/40456126147) passed on Ubuntu and macOS with Python 3.11 and 3.13. These are distribution facts, not guarantees of future model decisions. The workflow instructs the agent to respect decisions; authored/model scenarios do not prove it will do so in every context.

Only sanitized source, synthetic tests, documentation and notices are published. Private checkpoints, native object IDs, user chat contents and actual cleanup records stay outside public history.
