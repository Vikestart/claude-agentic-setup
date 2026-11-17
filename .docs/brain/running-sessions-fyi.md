---
name: running-sessions-fyi
description: "After changing a skill or ~/.claude/agents (CLAUDE.md edits now reach running chats by themselves), give the owner a short paste-able FYI for chats already running — they keep the old rules and cannot see new agents."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 4ce5bcc3-263d-4de5-beaf-5c4d42317fda
  modified: 2026-10-28T12:14:44.963Z
---

A running session loads `CLAUDE.md` and the agent list once, at start. It keeps following the old text,
cannot spawn a definition added later ("Agent type '…' not found"), and hands its subagents the OLD
CLAUDE.md. On 2026-09-25 the owner asked for a short summary to paste into their working chats, and
asked for it again each time the setup changed that session.

**Why:** the owner runs several chats in parallel and does not want to restart them all for a rule
change.
Since 2026-10-28 the asdev mod's rule-change notes tell a running main chat an edited CLAUDE.md rule
on its next prompt, so the FYI is needed only for skill and agent-definition changes (and subagents
still get the old CLAUDE.md).
**How to apply:** whenever a skill or agent-definition change lands, end with a fenced, paste-ready FYI that
states the new rules plainly (information, not a task list), including what a session that cannot see
new definitions should do instead. Replace it rather than stacking a second one when the setup changes
again in the same session. See [setup-architecture](../reference/setup-architecture.md), [[global-claude-setup]].
