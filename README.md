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

## Outputs

| Nom | Description |
|---|---|
| `score` | Score NIST (%) |
| `axiom_score` | Score AXIOM (%) |
| `passed` | `true`/`false` selon le seuil `min-score` |
| `reachable` | `true`/`false` selon que le serveur a répondu |

## Traçabilité par ancrage de hash (optionnel)

`blockchain_anchor.py` permet de calculer une empreinte SHA-256 d'un
rapport de conformité, pour en prouver l'intégrité et l'horodatage dans le
temps. Deux options d'ancrage sont documentées dans le fichier : OpenTimestamps
(recommandé, gratuit, ancré sur Bitcoin) ou Polygon (plus rapide, nécessite
un portefeuille crypto). Ce module n'est pas encore branché au pipeline
principal — à activer manuellement une fois testé sur ton propre cas d'usage.

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
