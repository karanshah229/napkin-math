---
name: napkin-math
description: Back-of-the-envelope estimates of latency, throughput, capacity and cloud cost from first principles, using measured reference numbers (CPU, memory, SSD, HDD, network disks, network, blob storage, Redis/Postgres/proxies, compression, cloud prices) and a unit-aware calculator. Use this whenever a question needs a rough number before building, buying or load-testing anything - system design and architecture reviews, capacity planning, "will this be fast enough", "how many machines/shards", latency budgets and p99 floors, storage, logging, egress or $ per TB costs, S3 vs local NVMe vs EBS, transfer or backup times, batch job sizing, or sanity-checking a benchmark, a vendor claim or a design doc - even if the user never says "napkin math" or "estimate".
---

# Napkin math

The goal is an answer within an order of magnitude, reached quickly, with the work
shown so someone else can check it, and with the one assumption that could flip it
named. A precise-looking number from bad units is worse than a rough one with
visible reasoning, so the method below cares more about units and caveats than
about digits.

## Workflow

1. **Turn the question into a number with units.** "Is S3 OK for this?" becomes
   "what is the p99 of one request, what throughput do we need, and what does it
   cost per month?" If the user gave no load, pick a plausible one, say so, and
   show how the answer scales with it.

2. **Decompose (Fermi).** List what you'd need to know, and label each input:
   *given* (from the user), *table* (a row from the references, named), or *guess*
   (yours, with a reason). More than ~6 assumptions usually means the model is
   more complicated than the question.

3. **Look up the numbers**, in this order:
   - `references/local.md`: measurements from the user's own systems. These beat
     generic numbers; say when you use one.
   - `references/numbers.md`: latency and throughput per operation.
   - `references/costs.md`: unit prices, blob request fees, instance shapes, $ per TiB read.
   - `references/compression.md`: compression ratios by data type and encoding.

   Grep for the row you need rather than reading everything
   (`grep -i "random read" references/numbers.md`). But when the estimate involves
   network, disks, blob storage or many threads, read the footnotes and the prose
   under the numbers table once: they change answers by 10x (the next section
   lists the common ones). If a row and its footnote disagree, show both and say
   which you used.

   The tables hold generic hardware and prices, not every mechanism. When you know
   a specific limit that applies (a protocol's window, a provider quota, a volume
   size limit, an instance's published bandwidth), use it and label it as such: a
   known cap left out costs more accuracy than an unsourced one put in.

4. **Compute with `scripts/calc.py`** (in this skill's directory), not in your head.
   Unit slips (GB vs GiB, bits vs bytes, per second vs per month) are the most
   common napkin-math error and are invisible in prose. Run it with `python3`
   (or `python`, `py -3`, or `uv run` where `python3` isn't on PATH):

   ```bash
   python3 scripts/calc.py "rps = 100k/s" "line = 1 KiB" "rps * line * 30 day" \
     "rps * line * 30 day * \$0.5/GB to \$"
   ```

   A number followed by a unit is a quantity (`5 GiB`, `250 us`, `3 GiB/s`,
   `$0.02/GB/month`); a compound unit has no spaces around its `/`, and spaced
   operators are arithmetic, so `1 TiB / 5 GiB/s` is a duration. `to <unit>`
   converts; `name = expr` defines a variable. `--help` lists every unit. Copy the
   lines you ran into the answer so readers can rerun them.

5. **Sanity-check.** First check that it fits: data per disk, volume and
   instance, memory, connection counts. Then work out each resource's limit (CPU,
   memory bandwidth, disk, network, a single connection, a single thread, request
   fees) and see which one binds; the smallest wins, and once you fix it the next
   one appears, so name that too. When comparing options, cost each one on the
   same basis (compute, standing storage, the durable copy, request and transfer
   fees). Cross-check one result by a second route (per request vs aggregate, per
   machine vs fleet). If the user said what the system does
   today, compare: a 10x gap means a wrong assumption or a real inefficiency, and
   either is worth saying.

6. **Answer** in the format below.

## Caveats that flip answers

The reference tables state these, but they are easy to miss:

- **Latency is one request at a time; throughput needs many in flight.** A
  synchronous loop gets size / latency: 8 KiB reads at 200 μs p99 give ~40 MiB/s
  from one thread, not the SSD's 5 GiB/s. Ask how much concurrency the design
  really has.
- **Tail vs mean.** Disk, network, blob storage and service latencies are p99;
  CPU and memory rows are means. Summing p99s of sequential calls gives a
  pessimistic upper bound for the path's p99, which is the right thing for a
  budget; say that's what it is.
- **"+1 RTT" rows leave out the network.** Cache gets, DB primary-key queries,
  proxies and TCP connects need the round trip added (same zone ~250 μs p99,
  cross zone ~1 ms, cross region 50-200 ms). A proxy adds a hop to its backend. A
  new TLS connection adds a handshake (~300 μs CPU plus round trips), which is why
  connection reuse matters across regions.
- **One TCP connection across regions is slow by default.** Linux's default
  buffers move ~3 MiB per round trip: ~30 MiB/s at 100 ms, ~15 MiB/s at 200 ms. A
  single-stream copy of terabytes across an ocean takes days. Fixes: raise the
  buffers (to 256 MiB) and run parallel streams. On AWS one flow also caps at
  5 Gbit/s outside a placement group; a 48 vCPU VM has ~30 Gbit/s in total, and
  AWS allows instances with 32+ vCPUs only half of their bandwidth for traffic
  leaving the region or going to the internet. Tools add their own windows on
  top (SSH's channel window limits `scp` below what TCP allows).
- **Threads and cores.** "1 thread" rows scale with cores until memory bandwidth
  (~200 GiB/s per VM) runs out. An x86 vCPU is half a physical core.
- **Big inputs are slower than small ones.** Sort is ~300 MiB/s on large data
  (1.3 GiB/s only for data in cache); xxh3 does 20 GiB/s from memory, 70 from cache.
- **Blob storage.** One connection gets ~100 MiB/s; reaching GiB/s takes dozens
  in parallel. Small objects are dominated by per-request fees ($0.4 per 1M
  regional GETs, $5 per 1M PUTs), so batching objects into larger files is often
  the biggest cost lever.
- **Network disks have two caps.** A volume has its own throughput and size
  limits, and the instance caps the total across all its volumes; striping more
  volumes stops helping at the instance's limit.
- **Writes.** Regional (replicated) network disks add ~1 ms to every write. A
  durable write (fsync) on an HDD costs ~30 ms at p99; on cloud SSDs and network
  disks it costs about as much as a plain write.
- **Units.** Bits vs bytes is 8x (network links are in bits). GB vs GiB is 7%,
  TB vs TiB 10%: small for napkin math, but prices are per GB and tables use GiB,
  so let the calculator convert. Cloud months are 730 hours.

## Output format

Use this structure, keeping prose short and the arithmetic visible:

```markdown
**Answer:** <the number with units, a range if the inputs are uncertain, and what dominates>

**Assumptions**
- <input>: <value> (given | table: <row name> | guess: <why>)

**Math**
<the calc.py lines you ran, with their results>

**Bottleneck:** <the resource that binds, and the runner-up>

**What would change this:** <the assumption the answer is most sensitive to, and how to measure it>
```

When the estimate feeds a design decision, end with what it implies, for example:
"the cross-region call is 95% of the budget, so caching it or moving the
dependency matters more than tuning the database." For a design-doc review, list
the risks ranked by how far each is from its limit.

## Measuring instead of estimating

Estimates say where to look; measurements decide. When an answer is within ~3x of
a limit, or will drive real spend, recommend the measurement that would confirm it:
`fio` for disks, TCP round trips (not ping) and `iperf3` with several streams for
networks, `wrk`/`hey` for HTTP, `pgbench`/`sysbench` for databases,
`redis-benchmark`/`memtier_benchmark` for caches, or the production metric that
already exists. The reference numbers come from the benchmarks in
[sirupsen/napkin-math](https://github.com/sirupsen/napkin-math)
(BENCHMARKING.md says how to rerun each one on a cloud VM).

When the user shares a measurement from their own systems, offer to record it in
`references/local.md` so later estimates use it.

## About the reference numbers

`numbers.md`, `costs.md` and `compression.md` are generated from the napkin-math
README (the header of each names the commit) and measured in late 2026 on 48 vCPU
x86 and Graviton4 VMs on AWS and GCP. They are rounded for memorization, so trust
the order of magnitude more than the digit, and expect newer hardware and price
changes to move them. Don't edit them by hand; `local.md` is for local numbers.
