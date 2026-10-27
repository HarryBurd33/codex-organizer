# Native Codex actions

Discover tools before claiming support. Standard Codex CLI/IDE skill discovery does not itself supply desktop project/chat tools. Without them, inspect selected filesystem paths only and label chats/sidebar/worktrees review-only.

Supported desktop host adapters may expose these operations (exact prefixes/contracts vary):

| Operation | Discoverable native action | Verify |
|---|---|---|
| Inventory | list_projects, list_threads, list_artifacts | Actual IDs, source, host, unavailable sources and limits |
| Inspect activity | read_thread or wait_threads | Read only needed recent context; no prompting other chats |
| Assign/group | move_thread_to_project, move_thread_to_sidebar_section, move_project_to_sidebar_section | Re-list project/section membership; preserve kind and host |
| Rename/order | set_thread_title, reorder_section, reorder_sidebar_sections, reorder_sidebar_projects | Exact proposed title/order and complete required membership |
| Sections | create_sidebar_section, rename_sidebar_section, delete_sidebar_section | Current IDs and approved affected objects |
| Chat archive/undo | set_thread_archived, list_archived_threads | Current approval, coupled worktree effects, archived-list readback |
| Managed worktree archive/undo | archive_worktree, restore_worktree | Exact attachment identity, supported eligibility, snapshot and recovery |

A recent list may cap non-pinned results (the construction host accepts at most 50). Do not present it as complete history. Some tools list only artifacts attached to the calling chat: an unattached worktree is review-only until the user opens its owning chat and attachment can be verified. Never attach/move another chat's checkout solely to gain cleanup access.

Archiving chats can also remove associated managed worktrees. Worktree snapshots may omit ignored files. Check needed ignored data and preserve it under an approved plan first. Never infer completion from idle/old alone. Do not remove primary/shared/pinned or uncertain-active worktrees. Native refusal is a stop, not an invitation to raw filesystem removal/prune.

For a project-assignment success receipt followed by an unchanged listing, record accepted-but-unverified, inspect the relevant native view and do not blindly retry. Do not claim verified completion from a success response alone.

Use [official worktree documentation](https://learn.chatgpt.com/docs/environments/git-worktrees) and current host contracts when assessing archive/recovery semantics. No native APIs, credentials or desktop automation tools are installed by this skill.
