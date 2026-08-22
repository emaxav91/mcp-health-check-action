"""
Point d'entrée pour la GitHub Action MCP Health Check.

Lit les inputs de l'action (variables d'environnement INPUT_*, convention
standard GitHub Actions), lance le contrôle de conformité + le score NIST,
écrit les outputs, et retourne un code de sortie non-zéro si le score est
sous le seuil défini — ce qui fait échouer le job CI, exactement comme
les outils concurrents trouvés sur le Marketplace (fail-on-critical).
"""

import asyncio
import json
import os
import sys

from checker import run_health_check, print_report
from nist_score import compute_nist_aligned_score, print_score_report
from axiom_score import compute_axiom_technical_score, print_axiom_report
from blockchain_anchor import compute_report_hash, create_opentimestamps_proof


def write_github_output(name: str, value: str):
    """Écrit dans le fichier GITHUB_OUTPUT, mécanisme standard des Actions
    pour exposer des valeurs réutilisables dans les étapes suivantes du workflow."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{name}={value}\n")
    else:
        # Hors GitHub Actions (test local) : juste afficher
        print(f"[output] {name}={value}")


def main():
    server_command_raw = os.environ.get("INPUT_SERVER-COMMAND", "")
    min_score = float(os.environ.get("INPUT_MIN-SCORE", "70"))

    if not server_command_raw:
        print("❌ Erreur : input 'server-command' requis (ex: 'python3 my_server.py')")
        sys.exit(1)

    server_command = server_command_raw.split()

    print(f"🔍 Vérification du serveur MCP : {server_command_raw}")
    print(f"📊 Seuil minimum requis : {min_score}%\n")

    result = asyncio.run(run_health_check(server_command))
    print_report(result)

    if not result["reachable"]:
        write_github_output("reachable", "false")
        write_github_output("score", "0")
        print("\n❌ ÉCHEC : le serveur MCP n'a pas répondu.")
        sys.exit(1)

    score = compute_nist_aligned_score(result)
    print_score_report(score)

    axiom = compute_axiom_technical_score(result)
    print_axiom_report(axiom)
    write_github_output("axiom_score", str(axiom.percentage))

    # --- Ancrage blockchain (optionnel, désactivé par défaut) ---
    # Coche 'enable-blockchain-anchor: true' dans le workflow pour l'activer.
    # Désactivé par défaut car ça ajoute un appel réseau externe (serveurs
    # de calendrier OpenTimestamps) qui peut ralentir ou échouer selon le
    # réseau du runner CI — ne doit pas bloquer le job gratuit par défaut.
    enable_anchor = os.environ.get("INPUT_ENABLE-BLOCKCHAIN-ANCHOR", "false").lower() == "true"
    if enable_anchor:
        print("\n🔗 Ancrage blockchain (OpenTimestamps) activé...")
        report_summary = {
            "server_name": result.get("server_name"),
            "checked_at": result.get("checked_at"),
            "nist_score": score.percentage,
            "axiom_score": axiom.percentage,
        }
        report_hash = compute_report_hash(report_summary)
        print(f"   Hash du rapport : {report_hash}")

        report_path = "mcp_trust_report.json"
        with open(report_path, "w") as f:
            json.dump(report_summary, f, indent=2)

        try:
            proof_path = create_opentimestamps_proof(report_path)
            print(f"   ✅ Preuve créée : {proof_path}")
            write_github_output("blockchain_proof", proof_path)
            write_github_output("report_hash", report_hash)
        except Exception as e:
            # L'ancrage est une fonctionnalité optionnelle : un échec ici
            # ne doit JAMAIS faire échouer le job principal.
            print(f"   ⚠️  Ancrage échoué (non bloquant) : {e}")
            write_github_output("blockchain_proof", "")

    write_github_output("reachable", "true")
    write_github_output("score", str(score.percentage))
    write_github_output("passed", str(score.percentage >= min_score).lower())

    if score.percentage < min_score:
        print(f"\n❌ ÉCHEC : score {score.percentage}% inférieur au seuil {min_score}%.")
        sys.exit(1)

    print(f"\n✅ SUCCÈS : score {score.percentage}% ≥ seuil {min_score}%.")
    sys.exit(0)


if __name__ == "__main__":
    main()
