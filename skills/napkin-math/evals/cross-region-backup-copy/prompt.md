---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Every night we need to copy a 10 TB database backup from a VM in us-east-1 to a VM in ap-southeast-1 (Singapore) for DR. The current script does a single `scp` of the tarball. Both VMs are 48 vCPU boxes with default Ubuntu network settings. Roughly how long will that take, and if it's too slow, what would you change?
