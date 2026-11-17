---
name: rule-change-scope
description: "When the owner asks to change a rule, change the rule's text only — never remove or restructure the things it governs (agents, skills, files) unasked."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 4ce5bcc3-263d-4de5-beaf-5c4d42317fda
  modified: 2026-09-25T12:05:17.898Z
---

On 2026-09-25 the owner asked to lower the effort floor ("allow High … we don't need Max"). I also
deleted the four max-effort agents. The owner: "No, don't remove any agents. I was referring to the
instructions in CLAUDE.md that said that effort must be on Max for certain tasks." They were restored
from the Recycle Bin.

**Why:** the owner curates the roster and the setup deliberately; a rule change is not a licence to
prune what the rule mentions.
**How to apply:** when a request could mean the rule or the things it governs, take the narrower
reading (CLAUDE.md §0: "take the smaller reading and state the assumption"). Removing an agent, skill
or file needs its own explicit ask. See [setup-architecture](../reference/setup-architecture.md).
