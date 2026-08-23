"""
Serveur combiné — fusionne l'API du classement (leaderboard) et le
formulaire d'audit organisationnel dans une seule application Flask.

Pourquoi la fusion était nécessaire : le formulaire d'audit doit vérifier
le palier technique (Silver) d'un repo pour déterminer l'éligibilité
Platinum — ça exige qu'il lise la MÊME base de données que l'API du
classement. Deux services séparés sur deux instances distinctes
n'auraient pas partagé le même fichier SQLite.

Routes :
- /                    -> classement public (HTML)
- /leaderboard.json    -> classement public (JSON)
- /submit              -> soumission automatique de score (POST)
- /badge               -> calcul du palier technique EMMA/Silver
- /audit               -> formulaire d'audit organisationnel (HTML)
- /submit-audit        -> soumission d'un audit (POST)

Prérequis : pip install flask
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, render_template_string

import badge_tier
from organizational_audit import AUDIT_QUESTIONNAIRE

app = Flask(__name__)
DB_PATH = "leaderboard.db"

RATE_LIMIT_MINUTES = 10
GOLD_MIN_PERCENTAGE = 75.0

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
            repo_url TEXT NOT NULL,
            nist_score REAL NOT NULL,
            axiom_score REAL NOT NULL,
            proof_hash TEXT,
            submitted_at TEXT DEFAULT (datetime('now'))
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_repo_url ON submissions(repo_url)")
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


init_db()  # Appelé au chargement du module — nécessaire pour gunicorn,
           # qui n'exécute jamais le bloc `if __name__ == "__main__"`.


# ============================================================
# LEADERBOARD (repris tel quel de api.py)
# ============================================================

def verify_hash_consistency(payload: dict) -> bool:
    if not payload.get("proof_hash"):
        return True
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
    conn = get_db()
    row = conn.execute(
        "SELECT submitted_at FROM submissions WHERE repo_url = ? ORDER BY submitted_at DESC LIMIT 1",
        (repo_url,)
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
        return jsonify({"error": f"Trop de soumissions récentes. Réessaie dans {RATE_LIMIT_MINUTES} minutes."}), 429

    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO submissions (server_name, repo_url, nist_score, axiom_score, proof_hash, submitted_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (payload["server_name"], payload["repo_url"], payload["nist_score"],
              payload["axiom_score"], payload.get("proof_hash")))
    conn.close()
    return jsonify({"ok": True}), 200


@app.route("/leaderboard.json")
def leaderboard_json():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.* FROM submissions s
        INNER JOIN (SELECT repo_url, MAX(submitted_at) AS max_date FROM submissions GROUP BY repo_url) latest
        ON s.repo_url = latest.repo_url AND s.submitted_at = latest.max_date
        ORDER BY s.nist_score DESC
    """).fetchall()
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
    .nav { margin-bottom: 20px; }
    .nav a { color: #2563eb; margin-right: 16px; }
  </style>
</head>
<body>
  <div class="nav"><a href="/">🏆 Classement</a><a href="/audit">🔍 Audit organisationnel</a></div>
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
    rows = conn.execute("""
        SELECT s.* FROM submissions s
        INNER JOIN (SELECT repo_url, MAX(submitted_at) AS max_date FROM submissions GROUP BY repo_url) latest
        ON s.repo_url = latest.repo_url AND s.submitted_at = latest.max_date
        ORDER BY s.nist_score DESC
    """).fetchall()
    conn.close()
    return render_template_string(LEADERBOARD_PAGE, entries=[dict(r) for r in rows])


@app.route("/badge")
def badge():
    repo_url = request.args.get("repo_url")
    if not repo_url:
        return jsonify({"error": "Paramètre 'repo_url' requis"}), 400

    history = badge_tier.get_submission_history(DB_PATH, repo_url)
    result = badge_tier.compute_badge_tier(history)

    response = {
        "repo_url": repo_url, "tier": result.tier,
        "latest_axiom_score": result.latest_axiom_score,
        "submission_count_in_window": result.submission_count_in_window,
        "reason": result.reason,
    }
    if result.tier != "none":
        certification = {
            "repo_url": repo_url, "tier": result.tier,
            "latest_axiom_score": result.latest_axiom_score,
            "computed_at": datetime.now().isoformat(),
        }
        canonical = json.dumps(certification, sort_keys=True, separators=(",", ":"))
        response["certification_hash"] = hashlib.sha256(canonical.encode()).hexdigest()

    return jsonify(response)


# ============================================================
# AUDIT ORGANISATIONNEL (repris de org_audit_form.py)
# ============================================================

def compute_org_tier(percentage: float, linked_repo_url: str) -> tuple:
    if percentage < GOLD_MIN_PERCENTAGE:
        return "none", f"Score organisationnel ({percentage}%) sous le seuil Gold ({GOLD_MIN_PERCENTAGE}%)."

    if not linked_repo_url:
        return "Gold", f"Score organisationnel {percentage}% ≥ {GOLD_MIN_PERCENTAGE}% — Gold atteint. Aucun repo lié fourni pour Platinum."

    try:
        history = badge_tier.get_submission_history(DB_PATH, linked_repo_url)
        tech_result = badge_tier.compute_badge_tier(history)
    except Exception:
        tech_result = None

    if tech_result and tech_result.tier == "Silver":
        return "Platinum", f"Score organisationnel {percentage}% ET palier technique Silver confirmé — Platinum atteint."

    return "Gold", f"Score organisationnel {percentage}% ≥ {GOLD_MIN_PERCENTAGE}% — Gold atteint, mais palier technique Silver requis pour Platinum non confirmé."


AUDIT_FORM_PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Audit organisationnel AXIOM</title>
  <style>
    body { font-family: -apple-system, Arial, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; color: #1e293b; }
    h1 { color: #0f172a; }
    .nav { margin-bottom: 20px; }
    .nav a { color: #2563eb; margin-right: 16px; }
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
  <div class="nav"><a href="/">🏆 Classement</a><a href="/audit">🔍 Audit organisationnel</a></div>
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


@app.route("/audit")
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
    tier, reason = compute_org_tier(percentage, linked_repo_url)

    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO org_audits (company_name, linked_repo_url, answers_json, percentage, tier, audited_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (company_name, linked_repo_url, json.dumps(scores), percentage, tier))
    conn.close()

    return jsonify({"tier": tier, "percentage": percentage, "reason": reason})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
