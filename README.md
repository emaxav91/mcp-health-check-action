# MCP Trust Score

GitHub Action de conformité et de disponibilité pour serveurs MCP (Model
Context Protocol). Elle se connecte à un serveur MCP, vérifie son bon
fonctionnement, et calcule trois scores complémentaires pour donner un
signal de confiance rapide, dans le flux CI/CD d'un développeur.

## Ce que l'outil vérifie

À chaque exécution, l'outil :
1. Se connecte au serveur MCP fourni et vérifie qu'il répond correctement
   au protocole (handshake, liste des outils, liste des ressources)
2. Calcule un **score NIST** — auto-évaluation heuristique alignée sur les
   4 fonctions du NIST AI RMF (Govern, Map, Measure, Manage)
3. Calcule un **score AXIOM** — signaux techniques inspirés du Domaine 5
   ("Data & AI Technical Integrity") d'un référentiel de maturité IA propriétaire
4. Peut faire échouer le job CI si le score passe sous un seuil configurable

## ⚠️ Ce que ces scores sont, et ne sont pas

Ni le score NIST ni le score AXIOM ne sont des certifications officielles.
Ce sont des **auto-évaluations heuristiques**, basées sur des contrôles
techniques vérifiables automatiquement (présence de descriptions, de
métadonnées, réponse correcte au protocole). Ils donnent un signal utile
et rapide, pas un audit de conformité complet — ni le NIST AI RMF ni AXIOM
ne se réduisent à ce qu'un script peut observer depuis l'extérieur d'un
serveur MCP.

Ce n'est également **pas un outil de sécurité/pentest**. Pour ça, voir des
outils comme les scanners dédiés à l'OWASP MCP Top 10, qui inspectent le
trafic en temps réel — un rôle différent et complémentaire à celui-ci.

## Installation dans ton propre repo

Ajoute ce fichier à `.github/workflows/mcp-trust-score.yml` :

```yaml
name: MCP Trust Score

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  mcp-trust-score:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: pip install -r requirements.txt   # adapte à ton projet

      - name: Vérifier la conformité MCP
        uses: TON-PSEUDO/mcp-trust-score@v1
        with:
          server-command: 'python3 my_server.py'
          min-score: '70'
```

## Inputs

| Nom | Description | Défaut |
|---|---|---|
| `server-command` | Commande pour lancer ton serveur MCP | requis |
| `min-score` | Score NIST minimum (%) requis pour que le job réussisse | `70` |
| `enable-blockchain-anchor` | Ancre un hash du rapport sur OpenTimestamps (Bitcoin) | `false` |

## Outputs

| Nom | Description |
|---|---|
| `score` | Score NIST (%) |
| `axiom_score` | Score AXIOM (%) |
| `blockchain_proof` | Chemin du fichier de preuve `.ots`, vide si non activé ou échec |
| `passed` | `true`/`false` selon le seuil `min-score` |
| `reachable` | `true`/`false` selon que le serveur a répondu |

## Traçabilité par ancrage OpenTimestamps

Active `enable-blockchain-anchor: true` dans ton workflow pour que chaque
run calcule un hash SHA-256 du rapport (score NIST + AXIOM + nom du
serveur + date) et l'ancre sur la blockchain Bitcoin via le protocole
ouvert OpenTimestamps — gratuit, sans portefeuille crypto à gérer.

✅ **Testé** : la logique Python (calcul de hash, appel du CLI `ots`,
gestion d'erreur) fonctionne correctement — vérifié avec le CLI officiel,
qui produit l'erreur réseau attendue quand les serveurs de calendrier ne
sont pas joignables. Cette fonctionnalité est conçue pour échouer
**silencieusement** (elle n'affecte jamais `passed`/le succès du job) si
l'ancrage réseau échoue — seule la ligne `blockchain_proof` reste vide.

⚠️ **Non vérifié en conditions réelles** : la soumission effective aux
serveurs de calendrier OpenTimestamps nécessite un accès réseau sortant
que l'environnement de développement utilisé n'avait pas. Teste-la sur
un vrai run GitHub Actions pour confirmer qu'un fichier `.ots` valide est
généré.

Une preuve fraîchement créée n'est pas immédiatement vérifiable — il faut
généralement attendre qu'un bloc Bitcoin la confirme (jusqu'à quelques
heures). Utilise `ots upgrade <fichier>.ots` puis `ots verify <fichier>.ots`
plus tard pour la confirmer.

**Alternative** : `blockchain_anchor.py` documente aussi une option
d'ancrage direct sur Polygon (plus rapide, nécessite un portefeuille
crypto) — non branchée au workflow principal, à activer manuellement si
préférée à OpenTimestamps.

## Structure du projet

```
mcp-health-check/
├── action.yml              # Déclaration de la GitHub Action
├── run_action.py           # Point d'entrée, orchestre les 3 étapes
├── checker.py               # Connexion au serveur MCP + contrôles de base
├── nist_score.py            # Score aligné NIST AI RMF
├── axiom_score.py           # Score inspiré du référentiel AXIOM (Domaine 5)
├── blockchain_anchor.py     # Traçabilité par hash (optionnel, non branché)
├── test_server.py           # Serveur MCP minimal pour tester l'Action
└── action-package/
    └── example-workflow.yml # Exemple de workflow à copier dans un repo cible
```

## Licence

MIT — voir le fichier `LICENSE`. Réutilisation, modification et
redistribution libres, y compris commerciales, à condition de conserver
la mention de copyright.
