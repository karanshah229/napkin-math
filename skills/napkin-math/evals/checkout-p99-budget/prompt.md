---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Our checkout service runs in us-east-1. For each checkout request it does: one Redis GET for the session, three Postgres primary-key lookups one after another, then a synchronous HTTPS call to a fraud-scoring service that only runs in eu-west-1 (Ireland). Product wants p99 under 150 ms end to end. What's the p99 floor for this path, where does the time go, and is the target realistic?
