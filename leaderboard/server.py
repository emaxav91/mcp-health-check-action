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
import os
import db as db_layer
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, render_template_string

import badge_tier
from organizational_audit import AUDIT_QUESTIONNAIRE
from blockchain_anchor import compute_report_hash, create_opentimestamps_proof
import framework_watch

app = Flask(__name__)
DB_PATH = "leaderboard.db"

RATE_LIMIT_MINUTES = 10
GOLD_MIN_PERCENTAGE = 75.0
TIER_ORDER = {"none": 0, "EMMA": 1, "Silver": 2}

def get_db():
    return db_layer.get_db(DB_PATH)


def init_db():
    pk = db_layer.autoincrement_pk()
    now = db_layer.now_expr()
    conn = get_db()
    with conn:
        conn.execute(f"""
        CREATE TABLE IF NOT EXISTS submissions (
            id {pk},
            server_name TEXT NOT NULL,
            repo_url TEXT NOT NULL,
            nist_score REAL NOT NULL,
            axiom_score REAL NOT NULL,
            proof_hash TEXT,
            submitted_at TEXT DEFAULT {now}
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_repo_url ON submissions(repo_url)")
        conn.execute(f"""
        CREATE TABLE IF NOT EXISTS org_audits (
            id {pk},
            company_name TEXT NOT NULL,
            linked_repo_url TEXT,
            answers_json TEXT NOT NULL,
            percentage REAL NOT NULL,
            tier TEXT NOT NULL,
            audited_at TEXT DEFAULT {now}
        )
        """)
        conn.execute(f"""
        CREATE TABLE IF NOT EXISTS anchored_badges (
            id {pk},
            repo_url TEXT NOT NULL,
            tier TEXT NOT NULL,
            certification_hash TEXT NOT NULL UNIQUE,
            proof_path TEXT,
            anchor_status TEXT DEFAULT 'pending',
            anchored_at TEXT DEFAULT {now}
        )
        """)
    conn.close()


init_db()  # Appelé au chargement du module — nécessaire pour gunicorn,
           # qui n'exécute jamais le bloc `if __name__ == "__main__"`.
framework_watch.init_framework_tables(DB_PATH)


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
    last_submitted = badge_tier._parse_timestamp(row["submitted_at"])
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

    repo_url = payload["repo_url"]

    # Palier AVANT cette soumission, pour détecter une progression après coup
    previous_history = badge_tier.get_submission_history(DB_PATH, repo_url)
    previous_tier = badge_tier.compute_badge_tier(previous_history).tier

    conn = get_db()
    with conn:
        conn.execute(f"""
            INSERT INTO submissions (server_name, repo_url, nist_score, axiom_score, proof_hash, submitted_at)
            VALUES (?, ?, ?, ?, ?, {db_layer.now_expr()})
        """, (payload["server_name"], repo_url, payload["nist_score"],
              payload["axiom_score"], payload.get("proof_hash")))
    conn.close()

    # Palier APRÈS cette soumission
    updated_history = badge_tier.get_submission_history(DB_PATH, repo_url)
    new_tier_result = badge_tier.compute_badge_tier(updated_history)
    new_tier = new_tier_result.tier

    response = {"ok": True}

    # Ancrage automatique UNIQUEMENT en cas de vraie progression (ex: none->EMMA,
    # EMMA->Silver) — pas à chaque soumission qui maintient le même palier,
    # pour éviter de spammer la blockchain de certifications redondantes.
    if TIER_ORDER.get(new_tier, 0) > TIER_ORDER.get(previous_tier, 0):
        response["tier_progression"] = f"{previous_tier} -> {new_tier}"
        anchor_result = _attempt_badge_anchor(repo_url, new_tier_result)
        response["auto_anchor"] = anchor_result

    return jsonify(response), 200


def _attempt_badge_anchor(repo_url: str, tier_result) -> dict:
    """Tente l'ancrage automatique d'un badge après une progression de
    palier. Best-effort : un échec ici ne doit JAMAIS faire échouer la
    soumission de score elle-même (même logique que l'ancrage principal
    dans run_action.py)."""
    certification_hash = compute_report_hash({
        "repo_url": repo_url, "tier": tier_result.tier,
        "latest_axiom_score": tier_result.latest_axiom_score,
    })

    conn = get_db()
    existing = conn.execute(
        "SELECT anchor_status FROM anchored_badges WHERE certification_hash = ?",
        (certification_hash,)
    ).fetchone()

    if existing:
        conn.close()
        return {"status": existing["anchor_status"], "certification_hash": certification_hash, "note": "déjà tenté"}

    with conn:
        conn.execute(
            "INSERT INTO anchored_badges (repo_url, tier, certification_hash, anchor_status) VALUES (?,?,?,?)",
            (repo_url, tier_result.tier, certification_hash, "pending")
        )
    conn.close()

    try:
        report_path = f"/tmp/badge_{certification_hash[:16]}.json"
        with open(report_path, "w") as f:
            json.dump({"repo_url": repo_url, "tier": tier_result.tier, "certification_hash": certification_hash}, f)

        proof_path = create_opentimestamps_proof(report_path)

        conn = get_db()
        with conn:
            conn.execute(
                "UPDATE anchored_badges SET anchor_status = 'anchored', proof_path = ? WHERE certification_hash = ?",
                (proof_path, certification_hash)
            )
        conn.close()
        return {"status": "anchored", "certification_hash": certification_hash, "proof_path": proof_path}

    except Exception as e:
        conn = get_db()
        with conn:
            conn.execute(
                "UPDATE anchored_badges SET anchor_status = 'failed' WHERE certification_hash = ?",
                (certification_hash,)
            )
        conn.close()
        return {"status": "failed", "certification_hash": certification_hash, "error": str(e)}


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
    .badge-pill { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }
    .badge-silver { background: #e2e8f0; color: #475569; }
    .badge-emma { background: #fef3c7; color: #92400e; }
    .badge-none { color: #94a3b8; font-size: 12px; }
    .nav { margin-bottom: 20px; }
    .nav a { color: #2563eb; margin-right: 16px; }
  </style>
</head>
<body>
  <div class="nav"><a href="/">🏆 Classement</a><a href="/audit">🔍 Audit organisationnel</a></div>
  <h1>🏆 MCP Trust Score — Classement</h1>
  <table>
    <tr><th>Rang</th><th>Serveur</th><th>Score NIST</th><th>Score AXIOM</th><th>Palier</th><th>Soumis le</th><th>Preuve</th></tr>
    {% for e in entries %}
    <tr>
      <td>{{ loop.index }}</td>
      <td><a href="{{ e.repo_url }}">{{ e.server_name }}</a></td>
      <td class="{{ 'score-high' if e.nist_score >= 90 else ('score-mid' if e.nist_score >= 70 else 'score-low') }}">{{ e.nist_score }}%</td>
      <td>{{ e.axiom_score }}%</td>
      <td>
        {% if e.badge_tier == 'Silver' %}<span class="badge-pill badge-silver">🥈 Silver</span>
        {% elif e.badge_tier == 'EMMA' %}<span class="badge-pill badge-emma">EMMA</span>
        {% else %}<span class="badge-none">—</span>
        {% endif %}
        {% if e.badge_tier != 'none' %}
          {% if e.anchor_status == 'anchored' %}<br><span style="font-size:11px;color:#16a34a;">⛓️ ancré</span>
          {% elif e.anchor_status == 'pending' or e.anchor_status == 'failed' %}<br><span style="font-size:11px;color:#94a3b8;">ancrage {{ e.anchor_status }}</span>
          {% else %}<br><button onclick="anchorBadge('{{ e.repo_url }}', this)" style="font-size:11px;padding:2px 6px;">Ancrer</button>
          {% endif %}
        {% endif %}
      </td>
      <td>{{ e.submitted_at }}</td>
      <td>{{ e.proof_hash[:12] + '...' if e.proof_hash else '—' }}</td>
    </tr>
    {% endfor %}
  </table>

  <script>
    async function anchorBadge(repoUrl, btn) {
      btn.disabled = true;
      btn.textContent = 'Ancrage...';
      try {
        const res = await fetch('/badge/anchor', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({repo_url: repoUrl}),
        });
        const data = await res.json();
        alert(data.anchor_status === 'anchored' ? 'Ancré avec succès !' : ('Statut : ' + (data.anchor_status || data.error)));
        location.reload();
      } catch (e) {
        alert('Erreur : ' + e.message);
        btn.disabled = false;
        btn.textContent = 'Ancrer';
      }
    }
  </script>
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

    entries = []
    for r in rows:
        entry = dict(r)
        history = badge_tier.get_submission_history(DB_PATH, entry["repo_url"])
        tier_result = badge_tier.compute_badge_tier(history)
        entry["badge_tier"] = tier_result.tier

        entry["anchor_status"] = None
        if tier_result.tier != "none":
            cert_hash = compute_report_hash({
                "repo_url": entry["repo_url"], "tier": tier_result.tier,
                "latest_axiom_score": tier_result.latest_axiom_score,
            })
            conn2 = get_db()
            existing = conn2.execute(
                "SELECT anchor_status FROM anchored_badges WHERE certification_hash = ?", (cert_hash,)
            ).fetchone()
            conn2.close()
            entry["anchor_status"] = existing["anchor_status"] if existing else "not_requested"

        entries.append(entry)

    return render_template_string(LEADERBOARD_PAGE, entries=entries)


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
        certification_hash = compute_report_hash({
            "repo_url": repo_url, "tier": result.tier,
            "latest_axiom_score": result.latest_axiom_score,
        })
        response["certification_hash"] = certification_hash

        # Vérifie si cette certification exacte a déjà été ancrée
        conn = get_db()
        existing = conn.execute(
            "SELECT anchor_status, proof_path FROM anchored_badges WHERE certification_hash = ?",
            (certification_hash,)
        ).fetchone()
        conn.close()

        if existing:
            response["anchor_status"] = existing["anchor_status"]
            response["proof_path"] = existing["proof_path"]
        else:
            response["anchor_status"] = "not_requested"
            response["anchor_hint"] = "POST /badge/anchor avec ce repo_url pour ancrer ce badge sur la blockchain."

    return jsonify(response)


@app.route("/badge/anchor", methods=["POST"])
def anchor_badge():
    """Déclenche l'ancrage blockchain réel d'un badge — action explicite,
    séparée de la simple consultation (/badge), pour ne pas refaire un
    appel réseau OpenTimestamps à chaque affichage de page."""
    payload = request.get_json() or {}
    repo_url = payload.get("repo_url") or request.args.get("repo_url")
    if not repo_url:
        return jsonify({"error": "Paramètre 'repo_url' requis"}), 400

    history = badge_tier.get_submission_history(DB_PATH, repo_url)
    result = badge_tier.compute_badge_tier(history)

    if result.tier == "none":
        return jsonify({"error": "Ce repo n'a atteint aucun palier — rien à ancrer."}), 400

    certification_hash = compute_report_hash({
        "repo_url": repo_url, "tier": result.tier,
        "latest_axiom_score": result.latest_axiom_score,
    })

    conn = get_db()
    existing = conn.execute(
        "SELECT anchor_status, proof_path FROM anchored_badges WHERE certification_hash = ?",
        (certification_hash,)
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({
            "message": "Déjà ancré ou en cours — pas de nouvel ancrage déclenché.",
            "certification_hash": certification_hash,
            "anchor_status": existing["anchor_status"],
        })

    # Insère un enregistrement "pending" avant même de tenter l'ancrage,
    # pour éviter une double soumission si deux requêtes arrivent en même temps
    with conn:
        conn.execute(
            "INSERT INTO anchored_badges (repo_url, tier, certification_hash, anchor_status) VALUES (?,?,?,?)",
            (repo_url, result.tier, certification_hash, "pending")
        )
    conn.close()

    try:
        report_path = f"/tmp/badge_{certification_hash[:16]}.json"
        with open(report_path, "w") as f:
            json.dump({"repo_url": repo_url, "tier": result.tier, "certification_hash": certification_hash}, f)

        proof_path = create_opentimestamps_proof(report_path)

        conn = get_db()
        with conn:
            conn.execute(
                "UPDATE anchored_badges SET anchor_status = 'anchored', proof_path = ? WHERE certification_hash = ?",
                (proof_path, certification_hash)
            )
        conn.close()

        return jsonify({"certification_hash": certification_hash, "anchor_status": "anchored", "proof_path": proof_path})

    except Exception as e:
        conn = get_db()
        with conn:
            conn.execute(
                "UPDATE anchored_badges SET anchor_status = 'failed' WHERE certification_hash = ?",
                (certification_hash,)
            )
        conn.close()
        return jsonify({"error": f"Échec de l'ancrage : {e}", "certification_hash": certification_hash, "anchor_status": "failed"}), 500


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
        conn.execute(f"""
            INSERT INTO org_audits (company_name, linked_repo_url, answers_json, percentage, tier, audited_at)
            VALUES (?, ?, ?, ?, ?, {db_layer.now_expr()})
        """, (company_name, linked_repo_url, json.dumps(scores), percentage, tier))
    conn.close()

    return jsonify({"tier": tier, "percentage": percentage, "reason": reason})


@app.route("/framework-status")
def framework_status():
    conn = get_db()
    rows = conn.execute("SELECT * FROM framework_versions").fetchall()
    events = conn.execute(
        "SELECT * FROM framework_update_events ORDER BY detected_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return jsonify({
        "tracked_frameworks": [dict(r) for r in rows],
        "recent_updates": [dict(e) for e in events],
    })


@app.route("/framework-check", methods=["POST"])
def trigger_framework_check():
    """Déclenche une vérification à la demande — utile pour tester,
    en attendant une vraie tâche planifiée (cron) en production."""
    github_token = os.environ.get("GITHUB_TOKEN")
    events = framework_watch.run_framework_check(DB_PATH, github_token=github_token)

    email_result = None
    if events:
        email_result = framework_watch.send_framework_alert_emails(DB_PATH, events)

    return jsonify({
        "checked": True,
        "changes_detected": len(events),
        "events": events,
        "email_notification": email_result,
    })


@app.route("/subscribe", methods=["POST"])
def subscribe():
    payload = request.get_json()
    email = (payload.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Email valide requis"}), 400

    conn = get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO framework_subscribers (email) VALUES (?)", (email,)
            )
    except db_layer.IntegrityError:
        conn.close()
        return jsonify({"message": "Déjà abonné"}), 200
    conn.close()
    return jsonify({"ok": True, "message": "Abonné aux alertes de mise à jour des référentiels."})


@app.route("/test-email", methods=["POST"])
def test_email():
    """Envoie un email de test à tous les abonnés actuels, avec des
    données factices — sert uniquement à vérifier que la configuration
    SMTP (Brevo) fonctionne réellement, sans toucher au système de
    détection de changement de référentiel."""
    fake_events = [{
        "framework": "test_smtp",
        "summary": "Ceci est un email de test — la configuration SMTP fonctionne.",
        "url": "https://mcp-trust-score.onrender.com",
    }]
    result = framework_watch.send_framework_alert_emails(DB_PATH, fake_events)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
