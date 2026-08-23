"""
Data room + analyse assistée par IA pour l'audit organisationnel AXIOM.

Principe : une entreprise dépose ses documents (politiques IA, chartes,
rapports RSE, comptes-rendus de gouvernance...) dans un dossier "data
room". Cet outil lit ces documents et demande à Claude de proposer un
BROUILLON de score (0-4) pour chacune des 11 questions de l'audit, avec
la justification et la citation qui l'appuient.

⚠️ Honnêteté critique : ceci reste un BROUILLON, pas un audit final.
- L'IA ne note QUE ce qui est explicitement présent dans les documents
  fournis — si un sujet n'est pas couvert, elle doit le signaler comme
  "aucune preuve trouvée" plutôt que de deviner ou de supposer une bonne
  pratique par défaut.
- Un humain DOIT relire chaque score proposé avant de le valider dans
  le formulaire d'audit (org_audit_form.py) — ce script ne soumet rien
  automatiquement à la base d'audits.
- L'IA peut se tromper, mal interpréter un document, ou manquer un
  passage pertinent. Le format de sortie inclut un niveau de confiance
  par question pour aider l'humain à prioriser sa relecture.

Prérequis : pip install anthropic pypdf
Variable d'environnement requise : ANTHROPIC_API_KEY
"""

import json
import os
from pathlib import Path

from organizational_audit import AUDIT_QUESTIONNAIRE

try:
    import pypdf
except ImportError:
    pypdf = None


def read_document(file_path: Path) -> str:
    """Lit un document texte (.txt, .md) ou PDF (.pdf)."""
    if file_path.suffix.lower() == ".pdf":
        if pypdf is None:
            raise EnvironmentError("Installe pypdf pour lire les fichiers PDF : pip install pypdf")
        reader = pypdf.PdfReader(str(file_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if file_path.suffix.lower() in [".txt", ".md"]:
        return file_path.read_text(encoding="utf-8", errors="ignore")

    raise ValueError(f"Type de fichier non supporté : {file_path.suffix} (utilise .txt, .md ou .pdf)")


def load_data_room(data_room_path: str) -> dict:
    """Lit tous les documents d'un dossier data room et retourne leur
    contenu texte, avec le nom du fichier source pour chaque extrait."""
    folder = Path(data_room_path)
    if not folder.exists():
        raise FileNotFoundError(f"Dossier data room introuvable : {data_room_path}")

    documents = {}
    for file_path in folder.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in [".txt", ".md", ".pdf"]:
            try:
                content = read_document(file_path)
                if content.strip():
                    documents[file_path.name] = content
            except Exception as e:
                print(f"⚠️  Impossible de lire {file_path.name} : {e}")

    return documents


def build_audit_prompt(documents: dict) -> str:
    """Construit le prompt envoyé à Claude, avec les 11 questions et le
    contenu des documents, en insistant sur la rigueur (pas d'invention)."""

    questions_text = "\n\n".join(
        f"Question {i} [{q.domain} / {q.sub_domain}] :\n"
        f"{q.question}\n"
        f"Bonne pratique attendue : {q.good_practice_description}"
        for i, q in enumerate(AUDIT_QUESTIONNAIRE)
    )

    documents_text = "\n\n".join(
        f"--- Document : {name} ---\n{content[:6000]}"  # limite raisonnable par doc
        for name, content in documents.items()
    )

    return f"""Tu es un auditeur qui évalue la maturité organisationnelle IA d'une
entreprise, à partir UNIQUEMENT des documents fournis ci-dessous.

RÈGLES STRICTES :
- Ne note QUE ce qui est explicitement écrit ou clairement déductible des documents.
- Si un sujet n'est pas couvert par les documents, mets score=0 et
  confidence="aucune_preuve" — ne suppose JAMAIS qu'une bonne pratique
  existe juste parce qu'elle serait plausible pour une entreprise de ce type.
- Cite toujours un passage court (une phrase, pas un paragraphe entier)
  qui justifie ton score, ou indique "aucune mention trouvée".
- L'échelle va de 0 (absence totale) à 4 (excellence/référence).

QUESTIONS À ÉVALUER :
{questions_text}

DOCUMENTS FOURNIS :
{documents_text}

Réponds UNIQUEMENT avec un JSON strict, sous cette forme exacte :
{{
  "answers": [
    {{
      "question_index": 0,
      "score": 2,
      "evidence_quote": "citation courte ou 'aucune mention trouvée'",
      "confidence": "haute" | "moyenne" | "aucune_preuve"
    }}
  ]
}}"""


def run_ai_assisted_audit(data_room_path: str, api_key: str) -> dict:
    """Pipeline complet : lit la data room, interroge Claude, retourne
    le brouillon d'audit structuré."""
    from anthropic import Anthropic

    documents = load_data_room(data_room_path)
    if not documents:
        raise ValueError(
            f"Aucun document lisible trouvé dans {data_room_path} "
            f"(formats acceptés : .txt, .md, .pdf)"
        )

    print(f"📄 {len(documents)} document(s) chargé(s) : {', '.join(documents.keys())}")

    prompt = build_audit_prompt(documents)

    client = Anthropic(api_key=api_key)
    print("🤖 Analyse par Claude en cours...")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_response = message.content[0].text.strip()
    if raw_response.startswith("```"):
        raw_response = raw_response.strip("`").replace("json\n", "", 1)

    result = json.loads(raw_response)

    # Enrichit avec le texte des questions pour faciliter la relecture humaine
    for answer in result["answers"]:
        q = AUDIT_QUESTIONNAIRE[answer["question_index"]]
        answer["domain"] = q.domain
        answer["sub_domain"] = q.sub_domain
        answer["question"] = q.question

    result["ai_assisted"] = True
    result["human_reviewed"] = False  # doit être mis à True manuellement après relecture

    return result


def print_draft_report(result: dict):
    print("\n" + "=" * 70)
    print("BROUILLON D'AUDIT — GÉNÉRÉ PAR IA, RELECTURE HUMAINE REQUISE")
    print("=" * 70)

    for a in result["answers"]:
        confidence_flag = "⚠️ " if a["confidence"] == "aucune_preuve" else ""
        print(f"\n{confidence_flag}[{a['domain']} / {a['sub_domain']}]")
        print(f"  Score proposé : {a['score']}/4 (confiance: {a['confidence']})")
        print(f"  Preuve citée : {a['evidence_quote']}")

    no_evidence_count = sum(1 for a in result["answers"] if a["confidence"] == "aucune_preuve")
    print(f"\n{'=' * 70}")
    print(f"⚠️  {no_evidence_count}/{len(result['answers'])} question(s) sans preuve trouvée dans les documents.")
    print("Ce brouillon doit être relu et validé par un humain avant soumission")
    print("dans le formulaire d'audit (org_audit_form.py).")
    print("=" * 70)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage : python3 ai_audit_assist.py <chemin_vers_data_room>")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("Définis ANTHROPIC_API_KEY avant de lancer ce script.")

    result = run_ai_assisted_audit(sys.argv[1], api_key)
    print_draft_report(result)

    output_path = Path(sys.argv[1]) / "draft_audit_result.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Brouillon sauvegardé : {output_path}")
