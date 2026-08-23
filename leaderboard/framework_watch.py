"""
Veille des référentiels — surveille les mises à jour de NIST AI RMF,
OWASP MCP Top 10, et AXIOM pour alerter les abonnés que leur score
MCP Trust Score pourrait être obsolète et mérite d'être relancé.

⚠️ Rythme d'évolution réel de chaque référentiel (vérifié) :
- OWASP MCP Top 10 : le plus actif — encore en bêta (Phase 3), prochaine
  version majeure prévue octobre 2026, publications périodiques ensuite.
  C'est celui qui justifie le plus une vraie veille automatique.
- NIST AI RMF : cadre gouvernemental stable, révisions majeures rares
  (années, pas mois). Surveillé quand même par cohérence, mais peu
  d'alertes attendues en pratique.
- AXIOM : contrôlé par l'auteure elle-même — pas de détection automatique
  nécessaire, juste un déclenchement manuel quand la grille change.

⚠️ Statut de test réel, vérifié dans cet environnement de dev :
- La vérification OWASP (via l'API GitHub) FONCTIONNE réellement — testée
  avec un vrai appel réseau, un vrai SHA de commit a été récupéré.
- La vérification NIST échoue dans CET environnement précis, mais pour
  une raison confirmée sans ambiguïté : mon sandbox de développement
  bloque le domaine nist.gov (`x-deny-reason: host_not_allowed`), ce
  n'est pas un blocage de NIST lui-même ni un bug de code. À tester
  chez toi ou sur Render, où l'accès réseau n'a pas cette restriction.
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime

import requests

OWASP_REPO_API = "https://api.github.com/repos/OWASP/www-project-mcp-top-10/commits"
NIST_AI_RMF_PAGE = "https://www.nist.gov/itl/ai-risk-management-framework"


def init_framework_tables(db_path: str):
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS framework_versions (
            framework TEXT PRIMARY KEY,
            last_known_version TEXT,
            last_checked_at TEXT DEFAULT (datetime('now'))
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS framework_update_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            framework TEXT NOT NULL,
            old_version TEXT,
            new_version TEXT,
            detected_at TEXT DEFAULT (datetime('now'))
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS framework_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            subscribed_at TEXT DEFAULT (datetime('now'))
        )
        """)
    conn.close()


def get_stored_version(db_path: str, framework: str) -> str | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT last_known_version FROM framework_versions WHERE framework = ?",
        (framework,)
    ).fetchone()
    conn.close()
    return row["last_known_version"] if row else None


def set_stored_version(db_path: str, framework: str, version: str):
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute("""
            INSERT INTO framework_versions (framework, last_known_version, last_checked_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(framework) DO UPDATE SET
                last_known_version = excluded.last_known_version,
                last_checked_at = datetime('now')
        """, (framework, version))
    conn.close()


def record_update_event(db_path: str, framework: str, old_version: str, new_version: str):
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute(
            "INSERT INTO framework_update_events (framework, old_version, new_version) VALUES (?,?,?)",
            (framework, old_version, new_version)
        )
    conn.close()


def check_owasp_mcp_top10(github_token: str | None = None) -> str:
    """Retourne le SHA du dernier commit touchant index.md du repo
    OWASP MCP Top 10 — sert de "version" détectable."""
    headers = {"Authorization": f"token {github_token}"} if github_token else {}
    response = requests.get(
        OWASP_REPO_API,
        params={"path": "index.md", "per_page": 1},
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    commits = response.json()
    if not commits:
        raise ValueError("Aucun commit trouvé — vérifie le chemin du fichier surveillé.")
    return commits[0]["sha"]


def check_nist_ai_rmf() -> str:
    """Retourne un hash du contenu de la page officielle NIST AI RMF —
    pas d'API de versioning officielle, donc on détecte un changement
    de contenu comme proxy."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MCPTrustScoreBot/1.0; "
                       "+https://github.com/mcp-trust-score-org/mcp-trust-score)"
    }
    response = requests.get(NIST_AI_RMF_PAGE, headers=headers, timeout=15)
    response.raise_for_status()
    return hashlib.sha256(response.content).hexdigest()


def run_framework_check(db_path: str, github_token: str | None = None) -> list[dict]:
    """Vérifie OWASP et NIST, enregistre les changements détectés.
    AXIOM n'est pas vérifié ici — voir trigger_axiom_update() pour son
    déclenchement manuel."""
    init_framework_tables(db_path)
    events = []

    checks = {
        "owasp_mcp_top10": lambda: check_owasp_mcp_top10(github_token),
        "nist_ai_rmf": check_nist_ai_rmf,
    }

    for framework, check_fn in checks.items():
        try:
            new_version = check_fn()
        except Exception as e:
            print(f"⚠️  Échec de la vérification pour {framework} : {e}")
            continue

        old_version = get_stored_version(db_path, framework)

        if old_version is None:
            print(f"ℹ️  {framework} : première vérification, version de référence enregistrée.")
            set_stored_version(db_path, framework, new_version)
            continue

        if old_version != new_version:
            print(f"🔔 {framework} : changement détecté ({old_version[:12]}... -> {new_version[:12]}...)")
            record_update_event(db_path, framework, old_version, new_version)
            set_stored_version(db_path, framework, new_version)
            events.append({"framework": framework, "old_version": old_version, "new_version": new_version})
        else:
            print(f"✅ {framework} : pas de changement.")

    return events


def trigger_axiom_update(db_path: str, new_version_label: str):
    """Déclenchement MANUEL par l'auteure quand elle met à jour AXIOM
    elle-même — pas de détection automatique nécessaire, elle contrôle
    directement la source."""
    init_framework_tables(db_path)
    old_version = get_stored_version(db_path, "axiom") or "initial"
    record_update_event(db_path, "axiom", old_version, new_version_label)
    set_stored_version(db_path, "axiom", new_version_label)
    print(f"🔔 AXIOM : mise à jour manuelle enregistrée ({old_version} -> {new_version_label})")


if __name__ == "__main__":
    events = run_framework_check("framework_watch.db", github_token=os.environ.get("GITHUB_TOKEN"))
    print(f"\n{len(events)} changement(s) de référentiel détecté(s).")
