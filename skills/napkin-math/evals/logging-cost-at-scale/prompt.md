---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

We're planning observability for our order API. It does about 100k requests/sec at peak and maybe 40k/sec on average, and every request writes one structured JSON log line of roughly 1 KB. The plan is to ship everything to a Datadog-style log management product and also archive the raw logs to S3 for a year for compliance. Give me a ballpark monthly cost for both and tell me what dominates.
