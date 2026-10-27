# Ordinary file actions

The helper requires Python 3.9+ and POSIX hard-link support (tested platforms and actual results are in the repository validation document). It handles regular files on one filesystem; it refuses directories, symlinks, managed worktrees and protected application/credential/Git/checkpoint state. Windows, cross-filesystem, network filesystems and files being changed by another writer need a separate reviewed tool or remain review-only.

A cleanup request is not consent to mutate. Show an exact source/destination and recoverability, obtain the current item decision, and check content/references before calling an apply command. User-approved archive and receipt directories must already exist. Do not store run records inside the installed skill. Commands below use synthetic absolute paths; replace them with the approved paths.

The survey excludes credential/recovery stores such as .gnupg, secrets and .checkpoints as well as database sidecars. Skipped metadata remains unknown. The action helper is deliberately stricter for all paths beneath .codex; the survey's explicit user-project exception does not permit file mutations there through this helper.

```sh
python3 scripts/file_actions.py preview --source /project/notes-copy.md --destination /project/Archive/notes-copy.md
python3 scripts/file_actions.py move --source /project/notes-copy.md --destination /project/Archive/notes-copy.md --expected-sha256 SHA256_FROM_PREVIEW --record /project/organizer-records/action-01.json --apply
python3 scripts/file_actions.py status --record /project/organizer-records/action-01.json
python3 scripts/file_actions.py restore --record /project/organizer-records/action-01.json --undo-record /project/organizer-records/undo-01.json --apply
```

Resolve scripts relative to this skill's folder, not the user's working directory. Without `--apply`, move/restore remain previews. The expected hash must match the inspected current source. Changing a destination or source revision changes the decision.

Archive uses the same move command to an exact approved archive path. It does not use OS Trash, empty a bin or permanently delete data. The helper creates the destination without replacement via a hard link, writes a receipt, revalidates source/content, then removes the old directory entry. This preserves the file inode/metadata on supported local filesystems. There can briefly be two names for the same file. A link or receipt failure must never cause deletion of the destination as an automatic cleanup step.

Receipts record stages and original/destination identity. Stop after uncertain/interrupted outcomes, inspect `status` and reconcile before any new mutation. Both copies or a completed destination may remain. Restore is a separately requested inverse move with a new receipt; it refuses an occupied original path or changed archived content. Receipts are recovery evidence, not authority.

Use a single active writer with stable roots and files. The helper is not an OS sandbox or a transactional filesystem and does not defend against malicious concurrent path replacement. Do not claim universal crash/metadata durability, network-filesystem behavior or recovery testing beyond recorded tests.
