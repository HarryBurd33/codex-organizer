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

## Checkpoint reconciliation and native handoff — 2026-10-29

A later maintenance request found a valid Organizer checkpoint in a shared parent
workspace that had gained unrelated files and three independent nested Git
repositories. Task Checkpoint 0.8.3 reported changed context and refused to flatten
those repositories into its ordinary file snapshot. This was a preservation
boundary, not a persistent quota pause or a defect requiring weaker checks.

The authorized repair first created a private archive of the unrelated workspace
areas, including nested Git history and ignored files. Archive members and original
files were compared by content hash, mode and link target; all three repository
heads and working-tree states were preserved. Only then were the exact unrelated
paths added to the parent repository's local exclude file. Its prior contents,
the tracked ignore file, the Organizer binding and earlier checkpoints were retained.
No original work was moved or deleted. A fresh checkpoint verified and its context
inspection cleared the earlier repository and nested-boundary conflicts.

For a similar repair, inspect the actual boundaries and preserve them separately
before considering exact parent exclusions. Do not use a broad ignore rule to hide
unsaved work, rebind the parent to another task, or take an occupied lease. Retain
the separate export and its manifest alongside the checkpoint for recovery; a
normal task snapshot does not automatically include an external preservation archive.

The maintenance chat then exercised the optional Model Switcher 0.5.0 native
integration: a verified checkpoint preceded a configured selection change from
Sol Medium to Astra Extra High for preservation review. Native evidence showed
the origin completed and a distinct heartbeat turn received the handoff. That
receiver rechecked source, authority, quota, checkpoint and the retained task lease,
claimed the intent once, and deleted its exact finite schedule before running the
review and continuing the authorized documentation work. The guard provides
at-most-once task admission; configured model metadata is not per-turn inference
telemetry. This observed maintenance handoff does not guarantee delivery in every
chat or make Organizer a background service.

The receiving review confirmed the original work, profile settings, permissions
and all seven installed Organizer skill files were unchanged. Organizer's existing
58-test suite and package validator remained the acceptance checks. This update
records the reconciliation procedure and observed integration; it changes no
Organizer runtime or installation behavior.

## Update verification and remaining work — 2026-10-30

Organizer remains version **0.2.2**. This documentation update does not change its
runtime or overwrite installed customizations. All seven global skill files were
compared with the public source and were identical. The package validator and all
58 Organizer tests passed again on local Python 3.15. The existing CI workflow
continues to test Ubuntu/macOS with Python 3.11/3.13; a local pass does not establish
the outcome of a new hosted run.

The authoring machine's desktop updater reported its configured production channel
up to date. Its separate Homebrew Codex CLI was upgraded from 0.165.0 to the
[latest stable 0.166.0 release](https://github.com/openai/codex/releases/tag/rust-v0.166.0).
These observations describe that machine and date; they are not minimum Organizer
requirements or a claim that every user has the same available release.

An optional local Codex Maintenance 0.1.1 adapter also passed its 25 tests and a
real initialize/list/two-tool MCP stdio roundtrip after the CLI update. Its proxy
readback used the existing daemon without starting a new server. Checkpoint
verification and inspection succeeded, with no pending jobs. The configured
model/effort, existing profile settings, permissions, task binding and completed
job history were preserved. This adapter uses installed Model Switcher 0.5.2 and
Task Checkpoint 0.8.3; none of those three packages is required by Organizer.

The adapter is a machine/chat-bound local package, not part of this public skill.
Selecting its installed plugin did not expose the two tools directly to the chat;
the actual calls used its installed MCP stdio interface. Direct host attachment
therefore remains unverified. Configuration readback is not per-turn inference
telemetry. Disk health is measured directly; cached account allowance is labelled
stale/unknown when appropriate, and fresh account readings remain on demand.

### Plan and acceptance gates

These are proposed follow-up packages, not completed capabilities or scheduled work.
Each package needs current scope, permissions and an unoccupied matching task lease
before execution. A successful native action must never be repeated merely because
its listing is stale.

| Order | Remaining limitation | Next work | Completion gate |
|---|---|---|---|
| 1 | Local maintenance tools are absent from the chat's native tool catalogue. | At a convenient user-controlled app reload, select the existing local plugin and inspect native discovery. If still absent, use supported MCP diagnostics and retain the working stdio fallback. | Both exact tools are exposed and called through the host, or the remaining host defect is documented with reproducible evidence. No completed task is resumed. |
| 2 | There is no customization-aware update command for an existing Organizer installation. | Design an opt-in updater using an installed-version manifest, preview, changed-file detection, backup and refusal on conflicts. Keep the existing installer safe by default. | Tests cover a clean upgrade, locally edited files, partial failure, symlinks, rollback and byte-identical preservation on refusal. |
| 3 | The optional maintenance adapter has a local root/chat binding and pinned inspector. | If distributing it is requested, create a separate portable package with explicit binding setup and version compatibility checks. Do not copy local manifests or private checkpoint data into this repository. | Clean-machine installation and two-tool discovery work with synthetic bindings; wrong roots/chats, changed inspector hashes and permission denial refuse safely. |
| 4 | Native chat/sidebar readback can lag an accepted write. | Prefer a supported authoritative membership readback when the host provides it. Until then retain the accepted-but-unverified state and reconcile through independent evidence. | An integration scenario records before/after identity and membership without retrying an uncertain mutation. |
| 5 | File actions cover local POSIX regular files on one filesystem. | Assess directory moves, cross-filesystem recovery and Windows as separate extensions, starting with reference/path/metadata preservation requirements. | Platform-specific tests and failure/recovery checks pass before any new capability is advertised. Existing refusal boundaries remain. |
| 6 | Nested Git repositories require separate preservation. | Document and test a reusable export-and-manifest procedure before considering additional automation. | Each nested repository's history, ignored files, edits and ownership are independently recoverable; parent exclusions cannot hide unsaved work. |

Routine bounded implementation can be assigned to Sol Medium, with consequential
preservation and publication review assigned to Astra Extra High when authorized
and available. These are future routing recommendations, not claims that a model
was changed. Fresh allowance must be checked before substantial follow-up work;
this plan creates no collector, background schedule or paid API budget.
