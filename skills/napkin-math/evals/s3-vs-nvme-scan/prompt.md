---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

We run a nightly batch job that scans 50 TB of Parquet (files are ~256 MB each and the reader issues 8 MB range GETs). Options: (a) read straight from S3 in the same region, (b) keep a copy on local NVMe on storage-optimized instances, (c) keep it on EBS gp3 volumes. For each, roughly how long does one full scan take on a single 48-vCPU instance, and what does a scan cost? Which would you pick?
