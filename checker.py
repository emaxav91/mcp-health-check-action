"""
MCP Health Check — vérifie qu'un serveur MCP répond correctement, respecte
le protocole, et signale les mauvaises pratiques courantes.

Ce n'est PAS un outil de pentest de sécurité (marché déjà occupé par des
éditeurs cybersécurité établis) — c'est un outil de conformité/disponibilité
pour développeurs qui viennent de publier leur propre serveur MCP.

Usage :
    python3 checker.py <commande pour lancer le serveur MCP>
    Exemple : python3 checker.py python3 test_server.py
"""

import asyncio
import json
import sys
from datetime import datetime

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def check_tool_quality(tool) -> list[str]:
    """Règles de bonnes pratiques MCP — chaque violation est un problème
    concret qui peut faire dérailler un agent IA utilisant ce serveur."""
    issues = []

    if not tool.description or len(tool.description.strip()) == 0:
        issues.append(f"Outil '{tool.name}' : description vide (un agent IA ne saura pas quand l'utiliser)")
    elif len(tool.description) < 10:
        issues.append(f"Outil '{tool.name}' : description trop courte ({len(tool.description)} caractères)")

    schema = tool.input_schema or {}
    if schema.get("type") == "object" and not schema.get("properties") and not schema.get("required"):
        # Pas forcément un problème (outil sans paramètres), mais à signaler
        pass

    return issues


async def run_health_check(server_command: list[str]) -> dict:
    result = {
        "checked_at": datetime.now().isoformat(),
        "server_command": " ".join(server_command),
        "reachable": False,
        "protocol_version": None,
        "server_name": None,
        "tools_count": 0,
        "resources_count": 0,
        "resources_detail": [],
        "server_instructions": None,
        "capabilities": {},
        "consistent_tool_listing": None,
        "risky_tool_names": [],
        "issues": [],
        "tools_detail": [],
    }

    server_params = StdioServerParameters(
        command=server_command[0], args=server_command[1:]
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                init_result = await session.initialize()
                result["reachable"] = True
                result["protocol_version"] = init_result.protocol_version
                result["server_name"] = init_result.server_info.name

                tools_result = await session.list_tools()
                result["tools_count"] = len(tools_result.tools)

                for tool in tools_result.tools:
                    issues = check_tool_quality(tool)
                    result["issues"].extend(issues)
                    result["tools_detail"].append({
                        "name": tool.name,
                        "description_length": len(tool.description or ""),
                    })

                try:
                    resources_result = await session.list_resources()
                    result["resources_count"] = len(resources_result.resources)
                    result["resources_detail"] = [
                        {
                            "name": r.name,
                            "has_description": bool(r.description and len(r.description.strip()) > 0),
                            "has_mime_type": bool(r.mime_type),
                        }
                        for r in resources_result.resources
                    ]
                except Exception:
                    # Certains serveurs ne supportent pas les resources, c'est normal
                    result["resources_detail"] = []

                result["server_instructions"] = init_result.instructions

                # --- Capacités déclarées (utile pour proxy "Sécurité et audit") ---
                caps = init_result.capabilities
                result["capabilities"] = {
                    "logging": bool(caps.logging),
                    "experimental": bool(caps.experimental),
                }

                # --- Contrôle de cohérence (proxy "Fiabilité") ---
                # Deux appels list_tools() consécutifs doivent renvoyer la
                # même liste — une incohérence est un signe d'instabilité.
                tools_result_2 = await session.list_tools()
                names_1 = sorted(t.name for t in tools_result.tools)
                names_2 = sorted(t.name for t in tools_result_2.tools)
                result["consistent_tool_listing"] = (names_1 == names_2)

                # --- Détection de mots-clés à risque (proxy "Sécurité et audit") ---
                # Pas un scan de sécurité réel — juste un signal d'alerte
                # basique sur des noms d'outils à fort impact potentiel.
                RISKY_KEYWORDS = ["execute", "eval", "shell", "delete_all", "drop_", "sudo", "exec_"]
                risky_tools = [
                    t.name for t in tools_result.tools
                    if any(k in t.name.lower() for k in RISKY_KEYWORDS)
                ]
                result["risky_tool_names"] = risky_tools

    except Exception as e:
        result["issues"].append(f"ÉCHEC DE CONNEXION : {e}")

    return result


def print_report(result: dict):
    print("\n" + "=" * 60)
    print("RAPPORT DE SANTÉ MCP")
    print("=" * 60)
    print(f"Serveur testé : {result['server_command']}")
    print(f"Vérifié le    : {result['checked_at']}")
    print(f"Accessible    : {'✅ OUI' if result['reachable'] else '❌ NON'}")

    if result["reachable"]:
        print(f"Nom déclaré   : {result['server_name']}")
        print(f"Version proto : {result['protocol_version']}")
        print(f"Outils        : {result['tools_count']}")
        print(f"Ressources    : {result['resources_count']}")

    if result["issues"]:
        print(f"\n⚠️  {len(result['issues'])} problème(s) détecté(s) :")
        for issue in result["issues"]:
            print(f"  - {issue}")
    else:
        print("\n✅ Aucun problème détecté.")

    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python3 checker.py <commande du serveur MCP>")
        print("Exemple : python3 checker.py python3 test_server.py")
        sys.exit(1)

    server_command = sys.argv[1:]
    result = asyncio.run(run_health_check(server_command))
    print_report(result)

    # Sauvegarde JSON pour permettre le diff dans le temps plus tard
    with open("last_check.json", "w") as f:
        json.dump(result, f, indent=2)
