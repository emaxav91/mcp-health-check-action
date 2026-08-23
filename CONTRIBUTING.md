# Contributing to MCP Trust Score

Thanks for considering a contribution — this project is small and
young, and every bit of help matters.

## Ways to contribute

- **Add your server to the leaderboard**: open a Pull Request adding
  your entry to `leaderboard/entries.json` (see format in the file).
- **Report a bug**: open an issue using the bug report template.
- **Suggest a new check**: propose a new technical signal for
  `nist_score.py`, `owasp_score.py`, or `axiom_score.py` — as long as
  it's a proxy that can be verified automatically from an MCP server
  connection (see the honesty notes at the top of each file for what
  qualifies).
- **Improve translations**: `README.md` (English) and `README.fr.md`
  (French) should stay in sync.

## Development setup

```bash
git clone https://github.com/mcp-trust-score-org/mcp-trust-score.git
cd mcp-trust-score
pip install -r requirements.txt
python3 checker.py python3 test_server.py
```

## Before submitting a Pull Request

- Test your change against `test_server.py` (the minimal MCP server
  included for this purpose)
- If you add a new check, document its limitations honestly — this
  project prioritizes accurate scoping over impressive-sounding claims
- Keep score modules (`nist_score.py`, `owasp_score.py`,
  `axiom_score.py`) focused on what's genuinely verifiable via a
  protocol-level check, not runtime traffic inspection (out of scope)

## Code of conduct

Be respectful, assume good faith, keep discussions technical and
constructive.
