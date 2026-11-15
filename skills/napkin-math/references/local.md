# Local numbers

Measurements from your own systems: your services, databases, queues, networks
and bills. Check this file before the generic tables; when a row here disagrees
with `numbers.md` or `costs.md`, use this one and say that you did.

Add a row whenever someone measures something. Keep the same conventions as the
generic tables: round for memorability (`200 MiB/s`, `30 ms`), say whether
latency is p99 or mean, and record where the number came from so it can be
re-measured when it goes stale.

| Operation | Latency | Throughput | Measured on | Date | Source |
| --------- | ------- | ---------- | ----------- | ---- | ------ |

<!--
Example rows (delete these once you have real ones):

| Postgres primary-key read, app VM to RDS, same zone (p99) | 2 ms   |            | db.r6g.2xlarge  | 2026-11 | Grafana: query latency dashboard |
| Kafka produce, acks=all, 1 KiB (p99)                       | 15 ms  | 200 MiB/s  | 3-broker, gp3   | 2026-11 | kafka-producer-perf-test         |
| Internal REST call via service mesh, same zone (p99)       | 5 ms   |            | Istio sidecar   | 2026-11 | load test, 500 RPS               |
| Monthly object storage bill per TB-month (blended)         |        |            | prod account    | 2026-10 | cost explorer: $23 / TB-month    |
-->
