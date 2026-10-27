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

Chat/sidebar/worktree operations require the receiving host's native tools and current access. They are not bundled desktop integrations. A native project-assignment tool accepted an approved action during authoring, but its immediate and subsequent listing did not confirm membership; that action was kept accepted-but-unverified and was not repeated. No claim is made that all native mutations are tested.

File operations support local POSIX regular files within one filesystem. Windows, directory moves, cross-filesystem moves, network filesystems, malicious concurrent path replacement and genuine power-loss durability were not verified. Fault injection is narrower evidence than real power loss. Single cooperating writer and stable roots are preconditions. There is no OS Trash or permanent-delete implementation.

Native user-scope skill discovery, installed-source identity and public CI are checked separately after publication; their receipts/CI are distribution evidence, not guarantees of future model decisions. The workflow instructs the agent to respect decisions; authored/model scenarios do not prove it will do so in every context.

Only sanitized source, synthetic tests, documentation and notices are published. Private checkpoints, native object IDs, user chat contents and actual cleanup records stay outside public history.
