---
name: bio-manuscript-common
description: Shared scripts and templates used by the bio-manuscript-* skill family (bio-manuscript-pipeline, bio-manuscript-refine, bio-manuscript-text). Do not invoke this skill directly — it is a resource container. Other bio-manuscript-* skills reference files here.
version: 1.0.0
author: BioClaw
license: MIT
metadata:
  bioclaw:
    tool_type: resource
    primary_tool: shared-templates-and-scripts
---

# bio-manuscript-common (shared resources)

This is not an invokable skill. It's a resource directory used by:

- `bio-manuscript-pipeline`
- `bio-manuscript-refine`
- `bio-manuscript-text`

Those skills reference files in `scripts/` and `templates/` here.

If you (the agent) arrived at this SKILL.md directly, you probably wanted one of the
`bio-manuscript-*` skills above — load that instead.
