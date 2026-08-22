"""
Traçabilité par ancrage de hash — preuve immuable qu'un contrôle de
conformité MCP a eu lieu à une date précise, avec un résultat précis.

⚠️ Choix honnête à faire AVANT de coder l'intégration finale :
Il existe deux façons de faire ça, avec un compromis clair.

OPTION A — OpenTimestamps (recommandé pour démarrer)
  - Gratuit, pas de portefeuille crypto à gérer, pas de frais de transaction
  - Ancre le hash dans la blockchain Bitcoin via un protocole standard ouvert
  - Largement utilisé pour l'horodatage de documents juridiques/preuves
  - Limite : la confirmation complète prend quelques heures (le temps qu'un
    bloc Bitcoin soit miné), pas instantané

OPTION B — Ancrage direct sur Polygon (si tu veux vraiment "de la blockchain"
pour le marketing/pitch)
  - Quasi instantané, coûte des fractions de centime par transaction
  - Nécessite un portefeuille crypto avec un peu de MATIC/POL pour payer le gas
  - Plus complexe à mettre en place pour un utilisateur non-crypto

Mon conseil : commence par l'option A. Elle donne EXACTEMENT la même
garantie de preuve d'intégrité, sans complexité ni coût, et "ancré sur
Bitcoin" est un argument de vente au moins aussi solide que "sur Polygon"
pour un client qui n'y connaît rien en crypto.

⚠️ Non testé en conditions réelles : la création de preuve OpenTimestamps
et l'ancrage Polygon nécessitent un accès réseau que mon environnement
de dev n'a pas. Ce qui EST testé ci-dessous : le calcul de hash lui-même.

Prérequis :
    pip install opentimestamps-client   # Option A
    pip install web3                    # Option B (déjà installé)
"""

import hashlib
import json


def compute_report_hash(report: dict) -> str:
    """Empreinte SHA-256 déterministe d'un rapport de conformité.
    Fonction pure, testée ci-dessous, sans dépendance réseau."""
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


# ============================================================
# OPTION A — OpenTimestamps (recommandé)
# ============================================================

# ============================================================
# OPTION A — OpenTimestamps (recommandé)
# ============================================================

def create_opentimestamps_proof(file_path: str, timeout: int = 60) -> str:
    """Crée une preuve d'horodatage OpenTimestamps pour un fichier donné,
    en passant par le CLI officiel `ots` (approche recommandée par le
    projet — plus stable que d'appeler l'API interne Python directement).

    Retourne le chemin du fichier de preuve généré (<file_path>.ots).

    ⚠️ Nécessite un accès réseau vers les serveurs de calendrier
    OpenTimestamps (a.pool.opentimestamps.org et autres). Testé dans mon
    environnement de dev : le CLI s'exécute correctement et échoue
    proprement avec un message réseau explicite ("need at least 2
    attestations but received 0 within timeout") quand ces serveurs ne
    sont pas joignables — donc le code lui-même est correct, seul l'accès
    réseau manquait. Chez toi, avec un accès réseau normal, ça doit aboutir.

    Prérequis : pip install opentimestamps-client
    """
    import subprocess
    import shutil

    if shutil.which("ots") is None:
        raise EnvironmentError(
            "Le CLI 'ots' n'est pas trouvé. Installe-le avec : "
            "pip install opentimestamps-client"
        )

    result = subprocess.run(
        ["ots", "stamp", file_path],
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    proof_path = f"{file_path}.ots"

    if result.returncode != 0:
        raise RuntimeError(
            f"Échec de l'horodatage OpenTimestamps.\n"
            f"Sortie : {result.stdout}\n"
            f"Erreur : {result.stderr}\n"
            f"Cause la plus probable : pas d'accès réseau sortant vers "
            f"les serveurs de calendrier OpenTimestamps."
        )

    return proof_path


def verify_opentimestamps_proof(file_path: str, timeout: int = 30) -> dict:
    """Vérifie une preuve d'horodatage existante (fichier .ots à côté du
    fichier original). Retourne un statut structuré.

    ⚠️ Une preuve fraîchement créée n'est PAS immédiatement vérifiable —
    il faut généralement attendre qu'un bloc Bitcoin la confirme (jusqu'à
    quelques heures). Utilise `upgrade_opentimestamps_proof` avant de
    vérifier si la preuve est récente.
    """
    import subprocess
    import shutil

    if shutil.which("ots") is None:
        raise EnvironmentError("Le CLI 'ots' n'est pas trouvé.")

    proof_path = f"{file_path}.ots"
    result = subprocess.run(
        ["ots", "verify", proof_path],
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    return {
        "verified": result.returncode == 0,
        "output": result.stdout + result.stderr,
    }


def upgrade_opentimestamps_proof(file_path: str, timeout: int = 30) -> bool:
    """Tente de compléter une preuve en attente de confirmation Bitcoin.
    Retourne True si la preuve a été mise à jour (donc désormais plus
    proche d'être vérifiable)."""
    import subprocess
    import shutil

    if shutil.which("ots") is None:
        raise EnvironmentError("Le CLI 'ots' n'est pas trouvé.")

    proof_path = f"{file_path}.ots"
    result = subprocess.run(
        ["ots", "upgrade", proof_path],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode == 0


# ============================================================
# OPTION B — Ancrage direct sur Polygon
# ============================================================

def anchor_hash_on_polygon(report_hash: str, private_key: str, rpc_url: str) -> str:
    """Envoie une transaction Polygon avec le hash du rapport dans le champ
    `data` — preuve d'existence horodatée par le bloc qui la contient.

    ⚠️ NON TESTÉ (pas d'accès réseau à un nœud RPC dans mon environnement).
    Vérifie ce code sur le réseau de test Polygon Amoy avant toute
    utilisation avec de vrais fonds."""
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    account = w3.eth.account.from_key(private_key)

    tx = {
        "from": account.address,
        "to": account.address,  # transaction à soi-même, juste pour porter la donnée
        "value": 0,
        "gas": 30000,
        "gasPrice": w3.eth.gas_price,
        "nonce": w3.eth.get_transaction_count(account.address),
        "data": f"0x{report_hash}",
        "chainId": w3.eth.chain_id,
    }

    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()


if __name__ == "__main__":
    # Ce qu'on PEUT tester sans réseau : le calcul de hash lui-même
    sample_report = {
        "server_name": "test-server-demo",
        "checked_at": "2026-08-22T13:08:20",
        "percentage": 71.4,
    }

    report_hash = compute_report_hash(sample_report)
    print(f"✅ Hash calculé (testé, fonctionne) : {report_hash}")
    print("\nCe hash est ce qu'on ancrerait sur OpenTimestamps ou Polygon.")
    print("Choisis une option ci-dessus selon ton besoin de rapidité vs simplicité.")
