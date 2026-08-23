"""
Questionnaire d'audit organisationnel — Domaines 1, 2, 3, 6, 7, 8 du
Framework AXIOM, appliqué à l'ENTREPRISE qui publie un agent/serveur MCP
(pas à l'agent lui-même — voir badge_tier.py pour les paliers techniques
EMMA/Silver, qui portent sur l'agent).

⚠️ Ce module NE calcule PAS de score automatiquement. Chaque question
nécessite un jugement humain (entretien, preuve documentaire) — c'est
volontaire et honnête : ces domaines ne sont pas vérifiables par un
script (contrairement aux Domaines 4 et 5, techniques, déjà automatisés).

Usage prévu : un auditeur humain remplit ce questionnaire lors d'un
entretien avec l'entreprise, note chaque critère selon l'échelle AXIOM
originale (absence -> bonne pratique en place), puis le score global
détermine l'éligibilité aux paliers Gold/Platinum.

Sources : reformulation fidèle des critères du fichier de notation AXIOM
original de l'auteure (Domaines 1, 2, 3, 6, 7, 8 — les domaines non
automatisables).
"""

from dataclasses import dataclass, field


@dataclass
class AuditQuestion:
    domain: str
    sub_domain: str
    question: str
    good_practice_description: str
    score: int = None
    evidence_notes: str = ""


AUDIT_QUESTIONNAIRE = [
    AuditQuestion(
        domain="1. Strategy & Vision",
        sub_domain="Vision IA",
        question="Le dirigeant porte-t-il une vision claire et des convictions sur l'IA, "
                  "au-delà d'un sujet purement technologique ?",
        good_practice_description="Des convictions claires sont portées par le dirigeant, "
                                   "cohérentes avec le business de l'entreprise.",
    ),
    AuditQuestion(
        domain="2. Governance & Organizational Maturity",
        sub_domain="Pilotage et gouvernance 360°",
        question="Existe-t-il un dispositif de pilotage (type AI-value cockpit) avec des "
                  "indicateurs clés (OKR) permettant aux dirigeants de suivre la stratégie IA ?",
        good_practice_description="Déploiement d'indicateurs clés répondant à la stratégie "
                                   "de l'organisation, suivis par les dirigeants.",
    ),
    AuditQuestion(
        domain="2. Governance & Organizational Maturity",
        sub_domain="Modèle organisationnel",
        question="Des valeurs éthiques et une culture de l'IA responsable sont-elles "
                  "diffusées dans les processus et la compétence des employés ?",
        good_practice_description="Gouvernance et processus robustes, culture IA intégrée "
                                   "à la compréhension des objectifs de l'entreprise.",
    ),
    AuditQuestion(
        domain="2. Governance & Organizational Maturity",
        sub_domain="Information & Communication",
        question="Des canaux de communication existent-ils pour diffuser les politiques IA "
                  "et remonter les problèmes/préoccupations des parties prenantes ?",
        good_practice_description="Canaux de diffusion des politiques ET canaux de "
                                   "remontée des préoccupations, dans les deux sens.",
    ),
    AuditQuestion(
        domain="3. Vendor Dependency",
        sub_domain="Gestion de l'écosystème IA",
        question="L'entreprise a-t-elle une gestion structurée de ses partenaires et "
                  "tiers IA pour sécuriser l'exécution de ses solutions ?",
        good_practice_description="Dépendance aux fournisseurs identifiée et gérée — "
                                   "critère à affiner lors de l'audit (peu détaillé dans "
                                   "le référentiel original).",
    ),
    AuditQuestion(
        domain="6. Financial Impact",
        sub_domain="Maîtrise des coûts",
        question="Un modèle de coûts est-il appliqué, avec un suivi régulier des dépenses "
                  "liées aux modèles/solutions IA ?",
        good_practice_description="Vision claire des coûts engagés + suivi régulier pour "
                                   "piloter les dépenses.",
    ),
    AuditQuestion(
        domain="7. Sustainability",
        sub_domain="Responsabilité",
        question="La supervision humaine et la responsabilité sont-elles intégrées tout "
                  "au long du cycle de vie de l'IA (conformité légale/réglementaire) ?",
        good_practice_description="Supervision humaine et responsabilité intégrées pour "
                                   "gérer les risques et respecter la réglementation.",
    ),
    AuditQuestion(
        domain="7. Sustainability",
        sub_domain="Équité",
        question="Les solutions IA sont-elles conçues pour réduire ou éliminer les biais "
                  "envers des individus, communautés ou groupes ?",
        good_practice_description="Conception explicitement orientée réduction des biais.",
    ),
    AuditQuestion(
        domain="7. Sustainability",
        sub_domain="Durabilité",
        question="Les solutions IA sont-elles conçues pour être économes en énergie et "
                  "réduire les émissions de carbone ?",
        good_practice_description="Sobriété énergétique et impact carbone pris en compte "
                                   "dès la conception.",
    ),
    AuditQuestion(
        domain="8. AI Empowerment",
        sub_domain="Manifeste et charte",
        question="Existe-t-il un manifeste et une charte IA déployés à grande échelle "
                  "dans l'organisation ?",
        good_practice_description="Manifeste/charte existants et effectivement déployés, "
                                   "pas juste rédigés.",
    ),
    AuditQuestion(
        domain="8. AI Empowerment",
        sub_domain="Acculturation et adoption",
        question="Une organisation est-elle en place pour faire monter en compétences les "
                  "équipes métiers sur l'IA au quotidien ?",
        good_practice_description="Pilotage actif de la montée en compétences et des "
                                   "usages IA, pas une formation ponctuelle isolée.",
    ),
]


def audit_summary(questionnaire):
    answered = [q for q in questionnaire if q.score is not None]
    if not answered:
        return {"status": "not_started", "domains_covered": 0}

    total_possible = len(answered) * 4
    total_scored = sum(q.score for q in answered)

    return {
        "status": "complete" if len(answered) == len(questionnaire) else "in_progress",
        "questions_answered": f"{len(answered)}/{len(questionnaire)}",
        "percentage": round(100 * total_scored / total_possible, 1) if total_possible else 0,
    }


if __name__ == "__main__":
    print(f"Questionnaire d'audit organisationnel AXIOM — {len(AUDIT_QUESTIONNAIRE)} questions\n")
    current_domain = None
    for q in AUDIT_QUESTIONNAIRE:
        if q.domain != current_domain:
            current_domain = q.domain
            print(f"\n=== {current_domain} ===")
        print(f"\n[{q.sub_domain}]")
        print(f"Q: {q.question}")
        print(f"Bonne pratique attendue: {q.good_practice_description}")
