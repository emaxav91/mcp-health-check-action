"""
Score dérivé des Domaines 4 ("Fiabilité, Sécurité et audit") et 5
("Data & AI Technical Integrity") du Framework AXIOM, appliqué à un
serveur MCP.

⚠️ Honnêteté importante sur ce que ce module fait et ne fait pas :

Le Framework AXIOM est un référentiel de MATURITÉ ORGANISATIONNELLE de l'IA
(vision du dirigeant, gouvernance, knowledge management...). La grande
majorité de ses domaines (Strategy & Vision, Knowledge Management au sens
organisationnel, etc.) ne sont PAS vérifiables par un script — ils
nécessitent un questionnaire ou un entretien humain.

Ce module ne couvre QUE les sous-domaines des Domaines 4 et 5 qui ont un
proxy technique observable sur un serveur MCP. Chaque contrôle est une
HEURISTIQUE APPROXIMATIVE, pas une mesure directe de ce que le sous-domaine
AXIOM original évalue. À ne jamais présenter comme "conforme AXIOM" —
présente plutôt "signaux techniques inspirés du référentiel AXIOM
(Domaines 4 et 5)".
"""

from dataclasses import dataclass, field


@dataclass
class AxiomCheck:
    sub_domain: str  # Un des 4 sous-domaines AXIOM du Domaine 5
    label: str
    passed: bool
    detail: str


@dataclass
class AxiomScore:
    checks: list = field(default_factory=list)

    @property
    def percentage(self) -> float:
        if not self.checks:
            return 0.0
        return round(100 * sum(1 for c in self.checks if c.passed) / len(self.checks), 1)

    def by_sub_domain(self) -> dict:
        breakdown = {}
        sub_domains = [
            "Explicabilité",
            "Intégrité des données",
            "Catalogue & réutilisabilité",
            "Knowledge Management",
            "Fiabilité",
            "Sécurité et audit",
        ]
        for sd in sub_domains:
            sd_checks = [c for c in self.checks if c.sub_domain == sd]
            if not sd_checks:
                continue
            passed = sum(1 for c in sd_checks if c.passed)
            breakdown[sd] = {
                "passed": passed,
                "total": len(sd_checks),
                "percentage": round(100 * passed / len(sd_checks), 1),
            }
        return breakdown


def compute_axiom_technical_score(health_check_result: dict) -> AxiomScore:
    score = AxiomScore()

    # --- Sous-domaine : Explicabilité ---
    # Proxy : le serveur documente-t-il globalement son fonctionnement
    # (instructions) et ses outils individuellement (descriptions) ?
    has_instructions = bool(health_check_result.get("server_instructions"))
    score.checks.append(AxiomCheck(
        "Explicabilité",
        "Le serveur fournit des instructions globales sur son usage",
        has_instructions,
        f"instructions = {'présentes' if has_instructions else 'absentes'}"
    ))

    tools_detail = health_check_result.get("tools_detail", [])
    well_explained = [t for t in tools_detail if t.get("description_length", 0) >= 20]
    ratio = len(well_explained) / len(tools_detail) if tools_detail else 0
    score.checks.append(AxiomCheck(
        "Explicabilité",
        "Les outils ont des descriptions suffisamment détaillées (≥20 caractères)",
        ratio >= 0.8,
        f"{len(well_explained)}/{len(tools_detail)} outils bien décrits"
    ))

    # --- Sous-domaine : Intégrité des données ---
    # Proxy : les ressources exposées ont-elles des métadonnées permettant
    # d'évaluer leur provenance/nature (description, type MIME) ?
    resources_detail = health_check_result.get("resources_detail", [])
    if resources_detail:
        with_desc = sum(1 for r in resources_detail if r.get("has_description"))
        with_mime = sum(1 for r in resources_detail if r.get("has_mime_type"))
        score.checks.append(AxiomCheck(
            "Intégrité des données",
            "Les ressources ont une description",
            with_desc == len(resources_detail),
            f"{with_desc}/{len(resources_detail)} ressources décrites"
        ))
        score.checks.append(AxiomCheck(
            "Intégrité des données",
            "Les ressources ont un type MIME déclaré",
            with_mime == len(resources_detail),
            f"{with_mime}/{len(resources_detail)} ressources typées"
        ))
    else:
        score.checks.append(AxiomCheck(
            "Intégrité des données",
            "Aucune ressource exposée à évaluer",
            True,  # Neutre : pas de ressources = pas de risque d'intégrité détectable ici
            "Ce serveur n'expose pas de resources MCP"
        ))

    # --- Sous-domaine : Catalogue & réutilisabilité ---
    # Proxy grossier : détecte les outils "fourre-tout" (nom générique
    # suggérant une responsabilité trop large, mauvais signe de modularité)
    generic_names = {"do_everything", "run", "execute", "process", "handle", "manage"}
    tools_count = health_check_result.get("tools_count", 0)
    generic_tools = [
        t for t in tools_detail
        if any(g in t.get("name", "").lower() for g in generic_names)
    ]
    score.checks.append(AxiomCheck(
        "Catalogue & réutilisabilité",
        "Pas d'outils au nom trop générique (signe de mauvaise modularité)",
        len(generic_tools) == 0,
        f"{len(generic_tools)} outil(s) au nom générique détecté(s)" if generic_tools
        else "Noms d'outils spécifiques, bon signe de modularité"
    ))

    # --- Sous-domaine : Knowledge Management ---
    # Proxy : mêmes ressources, on vérifie ici la présence d'un nom clair
    # (proxy pour "source identifiable", pas un vrai contrôle de gouvernance)
    if resources_detail:
        named = sum(1 for r in resources_detail if r.get("name"))
        score.checks.append(AxiomCheck(
            "Knowledge Management",
            "Les ressources ont un nom identifiable (source traçable)",
            named == len(resources_detail),
            f"{named}/{len(resources_detail)} ressources nommées"
        ))
    else:
        score.checks.append(AxiomCheck(
            "Knowledge Management",
            "Aucune ressource exposée à évaluer",
            True,
            "Ce serveur n'expose pas de resources MCP"
        ))

    # --- Sous-domaine : Fiabilité (Domaine 4) ---
    # Proxy : deux appels list_tools() consécutifs renvoient-ils le même
    # résultat ? Une incohérence est un signal d'instabilité du serveur.
    consistent = health_check_result.get("consistent_tool_listing")
    if consistent is not None:
        score.checks.append(AxiomCheck(
            "Fiabilité",
            "Le serveur renvoie une liste d'outils cohérente entre deux appels",
            consistent,
            "Cohérent" if consistent else "Incohérence détectée entre deux appels list_tools()"
        ))

    # --- Sous-domaine : Sécurité et audit (Domaine 4) ---
    # Proxy 1 : le serveur déclare-t-il une capacité de journalisation
    # (logging) ? C'est un signal de base pour l'auditabilité, pas une
    # preuve qu'un vrai audit trail est en place.
    capabilities = health_check_result.get("capabilities", {})
    score.checks.append(AxiomCheck(
        "Sécurité et audit",
        "Le serveur déclare une capacité de journalisation (logging)",
        bool(capabilities.get("logging")),
        "Logging déclaré" if capabilities.get("logging") else "Logging non déclaré dans les capacités"
    ))

    # Proxy 2 : absence de noms d'outils à risque évident (execute, shell,
    # delete_all...) — pas un scan de sécurité, juste un signal d'alerte
    # basique à vérifier manuellement si présent.
    risky_tools = health_check_result.get("risky_tool_names", [])
    score.checks.append(AxiomCheck(
        "Sécurité et audit",
        "Pas de noms d'outils évoquant une action à fort impact (execute, shell, delete_all...)",
        len(risky_tools) == 0,
        f"Outils à vérifier manuellement : {', '.join(risky_tools)}" if risky_tools
        else "Aucun nom d'outil à risque évident détecté"
    ))

    return score


def print_axiom_report(score: AxiomScore):
    print("\n" + "=" * 60)
    print("SIGNAUX TECHNIQUES INSPIRÉS DU FRAMEWORK AXIOM")
    print("(Domaines 4 et 5 : Fiabilité/Sécurité & Data/AI Technical Integrity)")
    print("⚠️  Proxy heuristique — ne remplace pas une évaluation AXIOM complète")
    print("=" * 60)

    print(f"\nScore global : {score.percentage}%\n")

    for sd, data in score.by_sub_domain().items():
        bar_filled = int(data["percentage"] / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        print(f"{sd:30s} [{bar}] {data['percentage']}%")

    print("\nDétail :")
    for c in score.checks:
        status = "✅" if c.passed else "❌"
        print(f"  {status} [{c.sub_domain}] {c.label}")
        print(f"      -> {c.detail}")

    print("=" * 60)
