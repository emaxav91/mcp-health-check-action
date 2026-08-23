"""
API de soumission automatique au classement MCP Trust Score.

L'Action GitHub, quand `submit-to-leaderboard: true` est activé, envoie
directement son résultat ici via une requête POST — plus besoin de Pull
Request manuelle.

⚠️ Limite honnête à garder en tête : cette API fait confiance au score
envoyé. Elle vérifie que le format est correct et que le hash correspond
bien aux données envoyées (cohérence interne), mais ne peut PAS vérifier
que le serveur MCP testé était authentique ou que le checker n'a pas été
modifié avant l'envoi. La preuve blockchain (si fournie) garantit
seulement que CE rapport précis n'a pas changé depuis sa création — pas
qu'il reflète un serveur MCP réel et honnête.

Protection anti-abus basique incluse :
- Limite de fréquence par repo (1 soumission / 10 minutes)
- Le hash doit correspondre aux données envoyées (cohérence)
- Score entre 0 et 100 uniquement

Prérequis : pip install flask
"""

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
DB_PATH = "leaderboard.db"

RATE_LIMIT_MINUTES = 10


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    with conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_name TEXT NOT NULL,
            repo_url TEXT NOT NULL UNIQUE,
            nist_score REAL NOT NULL,
            axiom_score REAL NOT NULL,
            proof_hash TEXT,
            submitted_at TEXT DEFAULT (datetime('now'))
        )
        """)
    conn.close()


def verify_hash_consistency(payload: dict) -> bool:
    """Vérifie que le hash fourni correspond bien aux données envoyées —
    détecte une incohérence évidente, pas une fraude sophistiquée."""
    if not payload.get("proof_hash"):
        return True  # Hash optionnel, pas d'incohérence à vérifier

    report_summary = {
        "server_name": payload.get("server_name"),
        "checked_at": payload.get("checked_at"),
        "nist_score": payload.get("nist_score"),
        "axiom_score": payload.get("axiom_score"),
    }
    canonical = json.dumps(report_summary, sort_keys=True, separators=(",", ":"))
    computed_hash = hashlib.sha256(canonical.encode()).hexdigest()

    return computed_hash == payload["proof_hash"]


def check_rate_limit(repo_url: str) -> bool:
    """Retourne True si la soumission est autorisée (pas trop récente)."""
    conn = get_db()
    row = conn.execute(
        "SELECT submitted_at FROM submissions WHERE repo_url = ?", (repo_url,)
    ).fetchone()
    conn.close()

    if not row:
        return True

    last_submitted = datetime.fromisoformat(row["submitted_at"])
    return datetime.now() - last_submitted > timedelta(minutes=RATE_LIMIT_MINUTES)


@app.route("/submit", methods=["POST"])
def submit():
    payload = request.get_json()

    required = ["server_name", "repo_url", "nist_score", "axiom_score"]
    missing = [f for f in required if f not in payload]
    if missing:
        return jsonify({"error": f"Champs manquants : {missing}"}), 400

    if not (0 <= payload["nist_score"] <= 100) or not (0 <= payload["axiom_score"] <= 100):
        return jsonify({"error": "Les scores doivent être entre 0 et 100"}), 400

    if not verify_hash_consistency(payload):
        return jsonify({"error": "Le hash fourni ne correspond pas aux données envoyées"}), 400

    if not check_rate_limit(payload["repo_url"]):
        return jsonify({
            "error": f"Trop de soumissions récentes pour ce repo. "
                     f"Réessaie dans {RATE_LIMIT_MINUTES} minutes."
        }), 429

    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO submissions (server_name, repo_url, nist_score, axiom_score, proof_hash, submitted_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(repo_url) DO UPDATE SET
                server_name = excluded.server_name,
                nist_score = excluded.nist_score,
                axiom_score = excluded.axiom_score,
                proof_hash = excluded.proof_hash,
                submitted_at = excluded.submitted_at
        """, (
            payload["server_name"], payload["repo_url"],
            payload["nist_score"], payload["axiom_score"],
            payload.get("proof_hash"),
        ))
    conn.close()

    return jsonify({"ok": True}), 200


@app.route("/leaderboard.json")
def leaderboard_json():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM submissions ORDER BY nist_score DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


LEADERBOARD_PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>MCP Trust Score — Classement</title>
  <style>
    body { font-family: -apple-system, Arial, sans-serif; max-width: 800px; margin: 40px auto; color: #1e293b; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 10px; text-align: left; border-bottom: 1px solid #e2e8f0; }
    th { background: #f8fafc; }
    .score-high { color: #16a34a; font-weight: bold; }
    .score-mid { color: #ca8a04; font-weight: bold; }
    .score-low { color: #dc2626; font-weight: bold; }
  </style>
</head>
<body>
  <h1>🏆 MCP Trust Score — Classement</h1>
  <table>
    <tr><th>Rang</th><th>Serveur</th><th>Score NIST</th><th>Score AXIOM</th><th>Soumis le</th></tr>
    {% for e in entries %}
    <tr>
      <td>{{ loop.index }}</td>
      <td><a href="{{ e.repo_url }}">{{ e.server_name }}</a></td>
      <td class="{{ 'score-high' if e.nist_score >= 90 else ('score-mid' if e.nist_score >= 70 else 'score-low') }}">{{ e.nist_score }}%</td>
      <td>{{ e.axiom_score }}%</td>
      <td>{{ e.submitted_at }}</td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
"""


@app.route("/")
def leaderboard_page():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM submissions ORDER BY nist_score DESC"
    ).fetchall()
    conn.close()
    return render_template_string(LEADERBOARD_PAGE, entries=[dict(r) for r in rows])


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
