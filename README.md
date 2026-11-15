# napkin-math skill

A Claude skill (and Claude Code plugin) for back-of-the-envelope estimates of
latency, throughput, capacity and cloud cost. It packages the measured reference
numbers from [sirupsen/napkin-math](https://github.com/sirupsen/napkin-math) with
a method for using them and a unit-aware calculator, so system design reviews,
capacity planning and performance subagents get numbers with visible working
instead of guesses.

## Layout

```
.claude-plugin/plugin.json      plugin manifest
skills/napkin-math/             the skill
  SKILL.md                      workflow, caveats that flip answers, output format
  references/numbers.md         latency/throughput   (generated, do not edit)
  references/costs.md           cloud prices, $/TiB   (generated, do not edit)
  references/compression.md     compression ratios    (generated, do not edit)
  references/local.md           your own measurements (edit freely)
  scripts/calc.py               unit-aware calculator, standard library only
  evals/                        test cases (claude plugin eval layout)
agents/capacity-estimator.md    subagent that estimates and ranks perf risks with the skill
tools/sync_references.py        regenerates references/ from an upstream checkout
tests/test_calc.py              calculator tests
```

## Install

- **Personal skill**: copy or symlink `skills/napkin-math` to `~/.claude/skills/napkin-math`
  (the `evals/` folder isn't needed at runtime; `package_skill.py` leaves it out).
- **Project skill**: copy it to `<repo>/.claude/skills/napkin-math`.
- **Plugin** (skill + `capacity-estimator` subagent): for local development run
  `claude --plugin-dir <path-to-this-repo>`, or publish this repo through a plugin marketplace.
- **claude.ai**: package with skill-creator's `package_skill.py` and upload the `.skill` file.

The calculator needs Python 3.10+ and nothing else.

## Use

The skill triggers on estimation questions ("how long will this copy take", "what
will logging cost at 100k RPS", "is p99 < 150 ms realistic"). The calculator also
works on its own:

```bash
python3 skills/napkin-math/scripts/calc.py "1 TiB / 5 GiB/s"
python3 skills/napkin-math/scripts/calc.py "rps = 100k/s" "line = 1 KiB" "rps * line * 30 day * \$0.5/GB to \$"
python3 skills/napkin-math/scripts/calc.py --help
```

Record measurements from your own systems in `references/local.md`; the skill
checks it before the generic tables.

## Refresh the reference numbers

The generated files name the upstream commit they came from. To update:

```bash
git -C <napkin-math checkout> pull
python3 tools/sync_references.py <napkin-math checkout>
python3 tools/sync_references.py <napkin-math checkout> --check   # exit 1 if stale (for CI)
```

## Test

```bash
python3 -m unittest discover tests
```

Behavioral evals live in `skills/napkin-math/evals/` in the layout
`claude plugin eval` reads; from `skills/napkin-math/`:
`claude plugin eval . --allow-tools Write,Edit,Bash` (real, billed model runs).

## License

MIT. The reference numbers are Copyright (c) 2019 Simon Eskildsen, from
sirupsen/napkin-math; see [LICENSE](LICENSE).
