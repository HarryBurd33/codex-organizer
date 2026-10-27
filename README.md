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

```sh
python3 scripts/validate.py
python3 -B -m unittest discover -s tests -v
```

No third-party Python packages, API key, background service or paid model calls are required by the helpers. The conversational skill uses your normal Codex access. Detailed observed results and untested boundaries are in [validation](docs/validation.md). User run logs belong outside the installed skill and are not uploaded by these helpers.

## License

[MIT](LICENSE). A full license notice is also included in the installed skill. This is an independent community skill, not an official OpenAI product. [Provenance](docs/provenance.md).
