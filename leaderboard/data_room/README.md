# Data Room — AI-assisted organizational audit

Drop company documents here (AI policies, charters, RSE/sustainability
reports, governance meeting notes, etc.) to have Claude propose a DRAFT
score for each of the 11 organizational audit questions.

## Structure

```
data_room/
└── <company-name>/
    └── documents/
        ├── ai-charter.txt
        ├── rse-report.pdf
        └── governance-notes.md
```

Supported formats: `.txt`, `.md`, `.pdf`.

## Usage

```bash
pip install anthropic pypdf
export ANTHROPIC_API_KEY="your-key"
python3 ai_audit_assist.py data_room/<company-name>/documents
```

This produces `draft_audit_result.json` in that folder — a **draft**,
not a final audit.

## ⚠️ Critical: this is AI-assisted, not AI-decided

- The AI is instructed to score ONLY what's explicitly present in the
  documents — no inference of "plausible" good practices.
- Any question not covered by the documents gets `confidence:
  "aucune_preuve"` (no evidence) and a score of 0 by default.
- **A human must review every proposed score** before entering it into
  the official audit form (`org_audit_form.py`). This tool accelerates
  document review — it does not replace the auditor's judgment.
- Untested in this dev environment: the real Claude API call itself
  (no API key available here). Document loading, PDF parsing, and
  prompt construction were verified — the API call logic follows the
  same pattern already validated in other parts of this project.

## Example

The `exemple-entreprise/documents/` folder contains sample documents
you can use to test the pipeline once you have an API key.
