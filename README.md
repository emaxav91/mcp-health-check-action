# MCP Trust Score

[🇫🇷 Version française](./README.fr.md)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)
![GitHub Action](https://img.shields.io/badge/GitHub%20Action-available-brightgreen.svg)

GitHub Action for compliance and availability checks on MCP (Model
Context Protocol) servers. It connects to an MCP server, verifies it
behaves correctly, and computes three complementary technical scores to
give a fast trust signal inside a developer's CI/CD flow.

## What it checks

On every run, the tool:
1. Connects to the given MCP server and verifies it responds correctly
   to the protocol (handshake, tool listing, resource listing)
2. Computes a **NIST score** — a heuristic self-assessment aligned with
   the 4 functions of the NIST AI RMF (Govern, Map, Measure, Manage)
3. Computes an **OWASP score** — technical signals inspired by 2 out of
   the 10 categories of the OWASP MCP Top 10 (MCP03: Tool Poisoning,
   MCP08: Lack of Audit and Telemetry)
4. Computes an **AXIOM score** — technical signals inspired by Domains 4
   and 5 ("Fiability/Security" and "Data & AI Technical Integrity") of a
   proprietary AI maturity framework
5. Can fail the CI job if the score falls below a configurable threshold

## ⚠️ What these scores are — and are not

None of these three scores are an official certification. They are
**heuristic self-assessments**, based on technical checks that can be
verified automatically (presence of descriptions, metadata, correct
protocol responses). They give a fast, useful signal — not a full
compliance audit. Neither the NIST AI RMF, the OWASP MCP Top 10, nor
AXIOM reduce to what a script can observe from outside an MCP server.

**OWASP coverage is intentionally limited.** The OWASP MCP Top 10 has 10
risk categories; this tool only covers 2 (MCP03, MCP08) — the ones a
one-off protocol check can meaningfully observe. The other 8 (token
mismanagement, privilege escalation, supply chain attacks, command
injection, intent flow subversion, auth/authz, shadow servers, context
oversharing) require real-time traffic inspection or deeper analysis —
out of scope for this tool. For that, see dedicated runtime security
scanners built specifically for the OWASP MCP Top 10.

This is also **not** a penetration-testing tool.

## Install in your own repo

Add this file at `.github/workflows/mcp-trust-score.yml`:

```yaml
name: MCP Trust Score

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  mcp-trust-score:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: pip install -r requirements.txt   # adapt to your project

      - name: Check MCP compliance
        uses: YOUR-USERNAME/mcp-trust-score@v1
        with:
          server-command: 'python3 my_server.py'
          min-score: '70'
```

## Inputs

| Name | Description | Default |
|---|---|---|
| `server-command` | Command to launch your MCP server | required |
| `min-score` | Minimum NIST score (%) required for the job to pass | `70` |
| `enable-blockchain-anchor` | Anchors a report hash on OpenTimestamps (Bitcoin) | `false` |
| `submit-to-leaderboard` | Automatically submits the score to the public leaderboard | `false` |
| `leaderboard-api-url` | Leaderboard API URL (required if `submit-to-leaderboard=true`) | `''` |

## Outputs

| Name | Description |
|---|---|
| `score` | NIST score (%) |
| `axiom_score` | AXIOM score (%) |
| `owasp_score` | OWASP score (%) — 2 out of 10 categories |
| `blockchain_proof` | Path to the `.ots` proof file, empty if disabled or failed |
| `passed` | `true`/`false` based on the `min-score` threshold |
| `reachable` | `true`/`false` based on whether the server responded |

## Traceability via OpenTimestamps anchoring

Set `enable-blockchain-anchor: true` in your workflow so that each run
computes a SHA-256 hash of the report (NIST + AXIOM scores, server name,
date) and anchors it on the Bitcoin blockchain via the open OpenTimestamps
protocol — free, no crypto wallet required.

✅ **Tested end to end**: verified working on a real GitHub Actions run
(network access to OpenTimestamps calendar servers, which local dev
sandboxes may lack, worked correctly on the GitHub-hosted runner). This
feature is designed to fail **silently** (never affects `passed`/job
success) if network anchoring fails — only `blockchain_proof` stays empty.

A freshly created proof is not immediately verifiable — it typically
needs a Bitcoin block confirmation (up to a few hours). Use
`ots upgrade <file>.ots` then `ots verify <file>.ots` later to confirm it.

## Public leaderboard

A public leaderboard of MCP servers by score, in `LEADERBOARD.md` and as
a static site at `docs/index.html` (free, hosted via GitHub Pages — no
server to maintain).

**To add your server**: open a Pull Request adding your entry to
`leaderboard/entries.json` (format shown in the file), with a score
obtained via this Action.

An **optional** automatic submission path also exists
(`submit-to-leaderboard` input) via a small hostable API
(`leaderboard/api.py`) — requires hosting it yourself (Render, Railway,
or a small VPS). Tested end to end locally: real HTTP submission, with
basic abuse protection (score bounds, hash consistency check, per-repo
rate limiting).

⚠️ Scores on the leaderboard are self-reported by developers, not
audited by a third party. The blockchain proof (when present) only
guarantees the report wasn't modified after submission — not that the
initial score is accurate.

## Enable the static leaderboard site (GitHub Pages, free)

1. Repo → Settings → Pages
2. "Source" → "Deploy from a branch"
3. Branch `main`, folder `/docs`
4. Save

Your site will be live within a few minutes at
`https://YOUR-USERNAME.github.io/mcp-trust-score/`.

## Project structure

```
mcp-health-check/
├── action.yml                # GitHub Action manifest
├── run_action.py             # Entry point, orchestrates all checks
├── checker.py                 # MCP server connection + base checks
├── nist_score.py              # NIST AI RMF-aligned score
├── owasp_score.py             # OWASP MCP Top 10-aligned score (partial)
├── axiom_score.py             # AXIOM-inspired score (Domains 4 & 5)
├── blockchain_anchor.py       # Hash-based traceability (optional)
├── test_server.py             # Minimal MCP server for testing the Action
├── leaderboard/
│   ├── entries.json           # Public leaderboard submissions
│   ├── generate_leaderboard.py # Generates LEADERBOARD.md + docs/index.html
│   └── api.py                  # Optional hostable API for auto-submission
├── docs/
│   └── index.html             # Static leaderboard site (GitHub Pages)
└── action-package/
    ├── example-workflow.yml    # Example workflow to copy into a target repo
    └── update-leaderboard-workflow.yml  # Auto-regenerates the leaderboard
```

## Discoverability (Repo Topics)

For GitHub search visibility, add these Topics to the repo (Settings →
General → Topics, or the gear icon next to "About" on the main page):

`mcp` `model-context-protocol` `ai-agents` `compliance` `security`
`ci-cd` `github-action` `nist` `owasp` `ai-governance`

## License

MIT — see the `LICENSE` file. Free to reuse, modify, and redistribute,
including commercially, as long as the copyright notice is kept.
