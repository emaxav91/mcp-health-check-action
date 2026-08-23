"""
Génère un classement public (LEADERBOARD.md) à partir des scores soumis
par les développeurs dans entries.json.

Principe volontairement simple, façon "Awesome List" GitHub : les
développeurs ajoutent leur entrée via Pull Request, ce script trie et
régénère le tableau — pas de base de données, pas de serveur, pas de coût.

Usage :
    python3 generate_leaderboard.py
"""

import json
from pathlib import Path

ENTRIES_PATH = Path(__file__).parent / "entries.json"
OUTPUT_PATH = Path(__file__).parent.parent / "LEADERBOARD.md"


def load_entries() -> list[dict]:
    with open(ENTRIES_PATH) as f:
        return json.load(f)


def validate_entry(entry: dict) -> list[str]:
    """Vérifie qu'une entrée a bien tous les champs requis — évite un
    classement corrompu si un PR mal formé est mergé par erreur."""
    required = ["server_name", "repo_url", "nist_score", "axiom_score", "verified_at"]
    missing = [f for f in required if f not in entry]
    errors = []
    if missing:
        errors.append(f"Champs manquants : {missing}")
    if "nist_score" in entry and not (0 <= entry["nist_score"] <= 100):
        errors.append(f"nist_score hors limites : {entry['nist_score']}")
    return errors


def score_badge(score: float) -> str:
    if score >= 90:
        return "🟢"
    elif score >= 70:
        return "🟡"
    else:
        return "🔴"


def generate_markdown(entries: list[dict]) -> str:
    # Tri par score NIST décroissant (score principal du classement)
    sorted_entries = sorted(entries, key=lambda e: e["nist_score"], reverse=True)

    lines = [
        "# 🏆 MCP Trust Score — Classement public",
        "",
        "Classement des serveurs MCP par score de conformité vérifié.",
        "Pour y ajouter le tien, ouvre une Pull Request ajoutant ton entrée",
        "dans `leaderboard/entries.json`, avec un score obtenu via",
        "[MCP Trust Score](../README.md).",
        "",
        "| Rang | Serveur | Score NIST | Score AXIOM | Vérifié le | Preuve |",
        "|---|---|---|---|---|---|",
    ]

    for i, entry in enumerate(sorted_entries, start=1):
        badge = score_badge(entry["nist_score"])
        proof = f"`{entry['proof_hash'][:12]}...`" if entry.get("proof_hash") else "—"
        lines.append(
            f"| {i} | [{entry['server_name']}]({entry['repo_url']}) | "
            f"{badge} {entry['nist_score']}% | {entry['axiom_score']}% | "
            f"{entry['verified_at']} | {proof} |"
        )

    lines += [
        "",
        "---",
        "",
        "⚠️ Ces scores sont des auto-évaluations soumises par les développeurs",
        "eux-mêmes, pas audités par un tiers indépendant. La colonne 'Preuve'",
        "indique un hash ancré sur OpenTimestamps (Bitcoin) quand disponible —",
        "vérifiable, mais ne garantit pas l'exactitude du score lui-même,",
        "seulement qu'il n'a pas été modifié après coup.",
    ]

    return "\n".join(lines)


def generate_html(entries: list[dict]) -> str:
    """Generates a static HTML page for GitHub Pages — zero server,
    zero cost, hosted for free directly from the repo."""
    sorted_entries = sorted(entries, key=lambda e: e["nist_score"], reverse=True)

    rows_html = []
    for i, entry in enumerate(sorted_entries, start=1):
        badge = score_badge(entry["nist_score"])
        proof = f"<code>{entry['proof_hash'][:12]}...</code>" if entry.get("proof_hash") else "—"
        rows_html.append(f"""
        <tr>
          <td>{i}</td>
          <td><a href="{entry['repo_url']}" target="_blank">{entry['server_name']}</a></td>
          <td>{badge} {entry['nist_score']}%</td>
          <td>{entry['axiom_score']}%</td>
          <td>{entry['verified_at']}</td>
          <td>{proof}</td>
        </tr>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MCP Trust Score — Public Leaderboard</title>
  <style>
    body {{
      font-family: -apple-system, "Segoe UI", Arial, sans-serif;
      max-width: 900px; margin: 40px auto; padding: 0 20px; color: #1e293b;
      background: #f8fafc;
    }}
    h1 {{ color: #0f172a; }}
    .subtitle {{ color: #64748b; margin-bottom: 24px; }}
    table {{
      width: 100%; border-collapse: collapse; background: white;
      border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
    th {{ background: #0f172a; color: white; font-weight: 600; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover {{ background: #f1f5f9; }}
    a {{ color: #2563eb; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .disclaimer {{
      margin-top: 24px; padding: 16px; background: #fefce8;
      border: 1px solid #fde047; border-radius: 8px; font-size: 14px; color: #713f12;
    }}
    .cta {{
      margin-top: 24px; padding: 16px; background: #eff6ff;
      border-radius: 8px; font-size: 14px;
    }}
    code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>🏆 MCP Trust Score</h1>
  <p class="subtitle">Public leaderboard of MCP servers by verified compliance score — NIST AI RMF, OWASP MCP Top 10 & AXIOM.</p>

  <table>
    <tr><th>Rank</th><th>Server</th><th>NIST Score</th><th>AXIOM Score</th><th>Verified on</th><th>Proof</th></tr>
    {"".join(rows_html)}
  </table>

  <div class="cta">
    <strong>Add your MCP server:</strong> open a
    <a href="https://github.com/mcp-trust-score-org/mcp-trust-score/blob/main/leaderboard/entries.json" target="_blank">Pull Request</a>
    adding your entry, with a score obtained via
    <a href="https://github.com/mcp-trust-score-org/mcp-trust-score" target="_blank">MCP Trust Score</a>.
  </div>

  <div class="disclaimer">
    ⚠️ These scores are self-reported by developers themselves, not audited by an
    independent third party. The "Proof" column shows a hash anchored on
    OpenTimestamps (Bitcoin) when available — verifiable, but it does not
    guarantee the accuracy of the score itself, only that it wasn't modified
    after the fact.
  </div>
</body>
</html>"""


def main():
    entries = load_entries()

    all_errors = {}
    valid_entries = []
    for entry in entries:
        errors = validate_entry(entry)
        if errors:
            all_errors[entry.get("server_name", "inconnu")] = errors
        else:
            valid_entries.append(entry)

    if all_errors:
        print("⚠️  Entrées invalides ignorées :")
        for name, errors in all_errors.items():
            print(f"  - {name} : {errors}")

    markdown = generate_markdown(valid_entries)

    with open(OUTPUT_PATH, "w") as f:
        f.write(markdown)

    print(f"✅ Classement Markdown généré : {OUTPUT_PATH} ({len(valid_entries)} entrée(s) valide(s))")

    html = generate_html(valid_entries)
    html_path = Path(__file__).parent.parent / "docs" / "index.html"
    html_path.parent.mkdir(exist_ok=True)
    with open(html_path, "w") as f:
        f.write(html)

    print(f"✅ Page HTML générée : {html_path}")


if __name__ == "__main__":
    main()
