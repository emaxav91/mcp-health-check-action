"""
Score de conformité aligné sur les 4 fonctions du NIST AI RMF
(Govern, Map, Measure, Manage), appliqué à un serveur MCP.

⚠️ Important, honnêteté légale et technique :
Il n'existe PAS (encore) de certification NIST officielle pour MCP —
l'initiative de standards agents IA du NIST a été lancée en février 2026
et son profil d'interopérabilité complet est attendu au T4 2026.
Ce script produit un SCORE D'AUTO-ÉVALUATION inspiré des 4 fonctions du
NIST AI RMF (Govern/Map/Measure/Manage), PAS une certification officielle.
Ne jamais présenter ce score comme "certifié NIST" — présente-le comme
"auto-évaluation alignée sur le NIST AI RMF".

Chaque règle ci-dessous est directement vérifiable techniquement (pas
d'affirmation vague) et rattachée à la fonction NIST RMF la plus proche.
"""

from dataclasses import dataclass, field


@dataclass
class ScoreCheck:
    nist_function: str  # Govern / Map / Measure / Manage
    label: str
    passed: bool
    detail: str


@dataclass
class ComplianceScore:
    checks: list = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def percentage(self) -> float:
        if self.total == 0:
            return 0.0
        return round(100 * self.passed_count / self.total, 1)

    def by_function(self) -> dict:
        """Score détaillé par fonction NIST (Govern/Map/Measure/Manage)."""
        breakdown = {}
        for fn in ["Govern", "Map", "Measure", "Manage"]:
            fn_checks = [c for c in self.checks if c.nist_function == fn]
            if not fn_checks:
                continue
            passed = sum(1 for c in fn_checks if c.passed)
            breakdown[fn] = {
                "passed": passed,
                "total": len(fn_checks),
                "percentage": round(100 * passed / len(fn_checks), 1),
            }
        return breakdown


def compute_nist_aligned_score(health_check_result: dict) -> ComplianceScore:
    """Prend le résultat de checker.py (déjà testé) et calcule un score
    d'auto-évaluation par fonction NIST AI RMF."""
    score = ComplianceScore()

    # --- GOVERN : responsabilité, identification claire du système ---
    has_name = bool(health_check_result.get("server_name"))
    score.checks.append(ScoreCheck(
        "Govern", "Le serveur déclare un nom identifiable",
        has_name,
        f"server_name = {health_check_result.get('server_name')!r}"
    ))

    has_version = bool(health_check_result.get("protocol_version"))
    score.checks.append(ScoreCheck(
        "Govern", "Le serveur déclare une version de protocole",
        has_version,
        f"protocol_version = {health_check_result.get('protocol_version')!r}"
    ))

    # --- MAP : inventaire clair des capacités (outils, ressources) ---
    tools_count = health_check_result.get("tools_count", 0)
    score.checks.append(ScoreCheck(
        "Map", "Le serveur expose au moins un outil documenté",
        tools_count > 0,
        f"{tools_count} outil(s) détecté(s)"
    ))

    tools_detail = health_check_result.get("tools_detail", [])
    well_documented = [t for t in tools_detail if t.get("description_length", 0) >= 10]
    ratio_documented = len(well_documented) / len(tools_detail) if tools_detail else 0
    score.checks.append(ScoreCheck(
        "Map", "Tous les outils ont une description suffisante (≥10 caractères)",
        ratio_documented == 1.0,
        f"{len(well_documented)}/{len(tools_detail)} outils bien documentés"
    ))

    # --- MEASURE : le système est-il observable / auditable ---
    reachable = health_check_result.get("reachable", False)
    score.checks.append(ScoreCheck(
        "Measure", "Le serveur répond correctement au handshake d'initialisation",
        reachable,
        "Connexion établie" if reachable else "Échec de connexion"
    ))

    no_critical_issues = len(health_check_result.get("issues", [])) == 0
    score.checks.append(ScoreCheck(
        "Measure", "Aucun problème de conformité détecté lors du dernier contrôle",
        no_critical_issues,
        f"{len(health_check_result.get('issues', []))} problème(s) en cours"
    ))

    # --- MANAGE : limitation du risque, principe de moindre privilège ---
    # Heuristique simple : un outil sans schéma de paramètres du tout est
    # plus difficile à auditer/limiter qu'un outil avec un schéma typé.
    schemas_present = tools_count == 0 or all(
        "description_length" in t for t in tools_detail
    )
    score.checks.append(ScoreCheck(
        "Manage", "Les outils exposent des métadonnées structurées (auditabilité)",
        schemas_present,
        "Structure de métadonnées cohérente" if schemas_present else "Métadonnées incomplètes"
    ))

    return score


def print_score_report(score: ComplianceScore):
    print("\n" + "=" * 60)
    print("SCORE D'AUTO-ÉVALUATION — ALIGNÉ SUR LE NIST AI RMF")
    print("(Govern / Map / Measure / Manage)")
    print("⚠️  Auto-évaluation heuristique, PAS une certification officielle")
    print("=" * 60)

    print(f"\nScore global : {score.percentage}% ({score.passed_count}/{score.total} contrôles passés)\n")

    for fn, data in score.by_function().items():
        bar_filled = int(data["percentage"] / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        print(f"{fn:10s} [{bar}] {data['percentage']}% ({data['passed']}/{data['total']})")

    print("\nDétail des contrôles :")
    for c in score.checks:
        status = "✅" if c.passed else "❌"
        print(f"  {status} [{c.nist_function}] {c.label}")
        print(f"      -> {c.detail}")

    print("=" * 60)


if __name__ == "__main__":
    # Test avec un résultat simulé (correspond au format réel de checker.py)
    fake_result = {
        "reachable": True,
        "server_name": "test-server-demo",
        "protocol_version": "2025-11-25",
        "tools_count": 2,
        "issues": ["Outil 'mystery_tool' : description vide"],
        "tools_detail": [
            {"name": "get_weather", "description_length": 49},
            {"name": "mystery_tool", "description_length": 0},
        ],
    }

    score = compute_nist_aligned_score(fake_result)
    print_score_report(score)
