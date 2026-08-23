"""
Interface d'audit organisationnel — formulaire web pour qu'un auditeur
humain remplisse le questionnaire AXIOM (Domaines 1,2,3,6,7,8) pour une
entreprise, et détermine son éligibilité aux paliers Gold/Platinum.

⚠️ Seuils, justifiés :
- Gold : moyenne ≥ 75% sur les 11 questions (≈ 3/4 en moyenne — une
  organisation globalement mature, pas parfaite sur chaque point).
- Platinum : critères Gold ET l'entreprise a AU MOINS un agent/serveur
  publié qui détient le palier technique Silver (cohérence : une
  entreprise "Platinum" doit prouver la maturité organisationnelle ET
  la maturité technique réelle d'au moins un de ses produits, pas
  seulement des intentions sur le papier).

Prérequis : pip install flask
"""

import hashlib
import json
import sqlite3
from datetime import datetime

from flask import Flask, request, jsonify, render_template_string

from organizational_audit import AUDIT_QUESTIONNAIRE
import badge_tier

app = Flask(__name__)
DB_PATH = "org_audits.db"

GOLD_MIN_PERCENTAGE = 75.0


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    with conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS org_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            linked_repo_url TEXT,
            answers_json TEXT NOT NULL,
            percentage REAL NOT NULL,
            tier TEXT NOT NULL,
            audited_at TEXT DEFAULT (datetime('now'))
        )
        """)
    conn.close()


def compute_org_tier(percentage: float, linked_repo_url: str, leaderboard_db_path: str) -> tuple:
    """Détermine Gold/Platinum/none, avec vérification croisée du palier
    technique pour Platinum."""
    if percentage < GOLD_MIN_PERCENTAGE:
        return "none", f"Score organisationnel ({percentage}%) sous le seuil Gold ({GOLD_MIN_PERCENTAGE}%)."

    if not linked_repo_url:
        return "Gold", f"Score organisationnel {percentage}% ≥ {GOLD_MIN_PERCENTAGE}% — Gold atteint. " \
                        f"Aucun repo lié fourni pour vérifier l'éligibilité Platinum."

    try:
        history = badge_tier.get_submission_history(leaderboard_db_path, linked_repo_url)
        tech_result = badge_tier.compute_badge_tier(history)
    except Exception:
        tech_result = None

    if tech_result and tech_result.tier == "Silver":
        return "Platinum", f"Score organisationnel {percentage}% ≥ {GOLD_MIN_PERCENTAGE}% ET " \
                            f"le repo lié détient le palier technique Silver — Platinum atteint."

    return "Gold", f"Score organisationnel {percentage}% ≥ {GOLD_MIN_PERCENTAGE}% — Gold atteint, " \
                   f"mais le repo lié n'a pas (encore) le palier technique Silver requis pour Platinum."


AUDIT_FORM_PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Audit organisationnel AXIOM</title>
  <style>
    body { font-family: -apple-system, Arial, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; color: #1e293b; }
    h1 { color: #0f172a; }
    .domain-header { font-weight: bold; margin-top: 24px; color: #334155; }
    .question { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
    .question p { margin: 4px 0; font-size: 14px; }
    .good-practice { color: #64748b; font-size: 13px; font-style: italic; }
    select { width: 100%; padding: 8px; margin-top: 8px; border-radius: 6px; border: 1px solid #cbd5e1; }
    input[type=text] { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; box-sizing: border-box; margin-bottom: 16px; }
    button { background: #0f172a; color: white; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; margin-top: 16px; }
    #result { margin-top: 20px; padding: 16px; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>🔍 Audit organisationnel AXIOM</h1>
  <p>Domaines 1, 2, 3, 6, 7, 8 — évaluation humaine, pas automatisée.</p>

  <form id="auditForm">
    <label>Nom de l'entreprise auditée</label>
    <input type="text" id="companyName" required>

    <label>Repo MCP lié (optionnel, pour vérifier l'éligibilité Platinum)</label>
    <input type="text" id="linkedRepo" placeholder="https://github.com/...">

    {% for q in questions %}
    {% if loop.first or q.domain != questions[loop.index0 - 1].domain %}
    <div class="domain-header">{{ q.domain }}</div>
    {% endif %}
    <div class="question">
      <p><strong>[{{ q.sub_domain }}]</strong></p>
      <p>{{ q.question }}</p>
      <p class="good-practice">Bonne pratique attendue : {{ q.good_practice_description }}</p>
      <select data-question-id="{{ loop.index0 }}" required>
        <option value="">-- Sélectionner un score --</option>
        <option value="0">0 — Absence totale</option>
        <option value="1">1 — Premiers pas</option>
        <option value="2">2 — En construction</option>
        <option value="3">3 — Bonne pratique en place</option>
        <option value="4">4 — Excellence / référence</option>
      </select>
    </div>
    {% endfor %}

    <button type="submit">Soumettre l'audit</button>
  </form>
  <div id="result"></div>

  <script>
    document.getElementById('auditForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const answers = Array.from(document.querySelectorAll('select')).map(s => parseInt(s.value));
      const payload = {
        company_name: document.getElementById('companyName').value,
        linked_repo_url: document.getElementById('linkedRepo').value,
        scores: answers,
      };
      const res = await fetch('/submit-audit', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      const resultDiv = document.getElementById('result');
      resultDiv.style.background = data.tier === 'Platinum' ? '#f0fdf4' : (data.tier === 'Gold' ? '#fefce8' : '#fef2f2');
      resultDiv.innerHTML = `<strong>Palier obtenu : ${data.tier}</strong><br>${data.reason}`;
    });
  </script>
</body>
</html>
"""


@app.route("/")
def audit_form():
    return render_template_string(AUDIT_FORM_PAGE, questions=AUDIT_QUESTIONNAIRE)


@app.route("/submit-audit", methods=["POST"])
def submit_audit():
    payload = request.get_json()
    company_name = payload.get("company_name", "").strip()
    linked_repo_url = payload.get("linked_repo_url", "").strip() or None
    scores = payload.get("scores", [])

    if not company_name:
        return jsonify({"error": "Nom d'entreprise requis"}), 400
    if len(scores) != len(AUDIT_QUESTIONNAIRE):
        return jsonify({"error": f"Attendu {len(AUDIT_QUESTIONNAIRE)} scores, reçu {len(scores)}"}), 400
    if any(s not in [0, 1, 2, 3, 4] for s in scores):
        return jsonify({"error": "Chaque score doit être entre 0 et 4"}), 400

    percentage = round(100 * sum(scores) / (len(scores) * 4), 1)

    tier, reason = compute_org_tier(percentage, linked_repo_url, "leaderboard.db")

    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO org_audits (company_name, linked_repo_url, answers_json, percentage, tier, audited_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (company_name, linked_repo_url, json.dumps(scores), percentage, tier))
    conn.close()

    return jsonify({"tier": tier, "percentage": percentage, "reason": reason})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5002)
