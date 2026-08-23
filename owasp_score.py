"""
Score dérivé de 2 catégories de l'OWASP MCP Top 10 (MCP03, MCP08),
appliqué à un serveur MCP.

⚠️ Honnêteté importante, comme pour NIST et AXIOM :
L'OWASP MCP Top 10 compte 10 catégories de risque. Ce module n'en couvre
QUE 2, celles qu'un contrôle protocolaire ponctuel (pas un proxy réseau
en temps réel) peut légitimement observer :

- MCP03 (Tool Poisoning) : proxy partiel via qualité de description et
  détection de mots-clés à risque
- MCP08 (Lack of Audit and Telemetry) : proxy via présence d'une
  capacité de logging déclarée

Les 8 autres catégories (MCP01 tokens, MCP02 scope creep, MCP04 supply
chain, MCP05 command injection, MCP06 intent flow, MCP07 auth/authz,
MCP09 shadow servers, MCP10 context oversharing) nécessitent une
inspection du trafic en temps réel ou une analyse hors du périmètre d'un
contrôle ponctuel — hors de portée de cet outil. Ne jamais présenter ce
score comme "conforme OWASP MCP Top 10" — présente-le comme "signaux
techniques inspirés de 2 catégories sur 10 de l'OWASP MCP Top 10".
"""

from dataclasses import dataclass, field


@dataclass
class OwaspCheck:
    category: str  # ex: "MCP03: Tool Poisoning"
    label: str
    passed: bool
    detail: str


@dataclass
class OwaspScore:
    checks: list = field(default_factory=list)

    @property
    def percentage(self) -> float:
        if not self.checks:
            return 0.0
        return round(100 * sum(1 for c in self.checks if c.passed) / len(self.checks), 1)

    def by_category(self) -> dict:
        breakdown = {}
        categories = ["MCP03: Tool Poisoning", "MCP08: Audit & Telemetry"]
        for cat in categories:
            cat_checks = [c for c in self.checks if c.category == cat]
            if not cat_checks:
                continue
            passed = sum(1 for c in cat_checks if c.passed)
            breakdown[cat] = {
                "passed": passed,
                "total": len(cat_checks),
                "percentage": round(100 * passed / len(cat_checks), 1),
            }
        return breakdown


def compute_owasp_technical_score(health_check_result: dict) -> OwaspScore:
    score = OwaspScore()

    # --- MCP03 : Tool Poisoning ---
    # Proxy 1 : descriptions vides/creuses = plus faciles à détourner
    # silencieusement (un agent IA se fie à la description pour décider
    # d'utiliser l'outil ou non).
    tools_detail = health_check_result.get("tools_detail", [])
    well_described = [t for t in tools_detail if t.get("description_length", 0) >= 10]
    ratio = len(well_described) / len(tools_detail) if tools_detail else 1
    score.checks.append(OwaspCheck(
        "MCP03: Tool Poisoning",
        "Les outils ont des descriptions non vides (réduit le risque de détournement silencieux)",
        ratio == 1.0,
        f"{len(well_described)}/{len(tools_detail)} outils correctement décrits"
    ))

    # Proxy 2 : mots-clés à risque déjà détectés par checker.py
    risky_tools = health_check_result.get("risky_tool_names", [])
    score.checks.append(OwaspCheck(
        "MCP03: Tool Poisoning",
        "Pas de noms d'outils à fort impact potentiel non signalés",
        len(risky_tools) == 0,
        f"À vérifier manuellement : {', '.join(risky_tools)}" if risky_tools
        else "Aucun nom à risque évident détecté"
    ))

    # --- MCP08 : Lack of Audit and Telemetry ---
    capabilities = health_check_result.get("capabilities", {})
    score.checks.append(OwaspCheck(
        "MCP08: Audit & Telemetry",
        "Le serveur déclare une capacité de journalisation (logging)",
        bool(capabilities.get("logging")),
        "Logging déclaré" if capabilities.get("logging") else "Logging non déclaré — trou d'audit potentiel"
    ))

    return score


def print_owasp_report(score: OwaspScore):
    print("\n" + "=" * 60)
    print("SIGNAUX TECHNIQUES INSPIRÉS DE L'OWASP MCP TOP 10")
    print("(2 catégories sur 10 : MCP03, MCP08)")
    print("⚠️  Ne remplace PAS un scan de sécurité complet (voir README)")
    print("=" * 60)

    print(f"\nScore global : {score.percentage}%\n")

    for cat, data in score.by_category().items():
        bar_filled = int(data["percentage"] / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        print(f"{cat:28s} [{bar}] {data['percentage']}%")

    print("\nDétail :")
    for c in score.checks:
        status = "✅" if c.passed else "❌"
        print(f"  {status} [{c.category}] {c.label}")
        print(f"      -> {c.detail}")

    print("=" * 60)
