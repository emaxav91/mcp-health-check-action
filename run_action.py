"""
Point d'entrée pour la GitHub Action MCP Health Check.

Lit les inputs de l'action (variables d'environnement INPUT_*, convention
standard GitHub Actions), lance le contrôle de conformité + le score NIST,
écrit les outputs, et retourne un code de sortie non-zéro si le score est
sous le seuil défini — ce qui fait échouer le job CI, exactement comme
les outils concurrents trouvés sur le Marketplace (fail-on-critical).
"""

import asyncio
import os
import sys

from checker import run_health_check, print_report
from nist_score import compute_nist_aligned_score, print_score_report


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
