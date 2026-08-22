# Mise en prod — MCP Trust Score

## ✅ Ce qui est réellement testé (pas juste écrit)

`run_action.py` a été testé de bout en bout, dans les deux scénarios :
- **Succès** : seuil 70%, score réel obtenu 71.4% → code de sortie 0,
  outputs corrects (`reachable=true`, `score=71.4`, `passed=true`)
- **Échec** : seuil 90%, même score réel 71.4% → code de sortie 1 (fait
  échouer le job CI), outputs corrects (`passed=false`)

`action.yml` a été validé comme YAML syntaxiquement correct, avec la
structure attendue par GitHub Actions (inputs, outputs, steps composite).

## ⚠️ Ce qui n'est PAS testé

Le workflow complet **dans un vrai environnement GitHub Actions** — mon
environnement de dev n'a pas Docker ni d'accès à l'infrastructure GitHub
pour lancer un vrai job CI. La logique métier (le vrai cœur du produit)
est testée ; l'intégration avec l'infrastructure GitHub doit être vérifiée
en conditions réelles, à l'étape 4 ci-dessous.

## Étapes pour publier, dans l'ordre

### 1. Crée un repo GitHub dédié
Nomme-le clairement, ex: `mcp-trust-score`. Mets tous les fichiers
de ce dossier à la racine du repo :
```
action.yml
checker.py
nist_score.py
blockchain_anchor.py
run_action.py
test_server.py
requirements.txt
README.md
```

### 2. Tag une version
GitHub Actions se référence par tag, pas par nom de branche :
```bash
git init
git add .
git commit -m "v1.0 - MCP Trust Score"
git tag -a v1 -m "Version 1"
git push origin main --tags
```

### 3. Teste-la d'abord sur TON PROPRE repo avant de la publier
Crée un second repo de test avec `test_server.py` dedans, ajoute
`.github/workflows/test.yml` (copie `action-package/example-workflow.yml`,
en remplaçant `TON-PSEUDO/mcp-health-check@v1` par le chemin de ton repo,
ex: `./` si tu testes dans le même repo, ou `TON-PSEUDO/mcp-trust-score@v1`
une fois publié). Vérifie dans l'onglet "Actions" de GitHub que le job
tourne et affiche bien le rapport.

**C'est l'étape la plus importante** — c'est le premier vrai test en
conditions réelles de tout le pipeline. S'il y a un problème d'intégration
avec l'infrastructure GitHub (permissions, chemins, versions Python), il
apparaîtra ici, pas avant.

### 4. Publie sur le GitHub Marketplace
Une fois que l'étape 3 fonctionne :
1. Va sur la page de ton repo GitHub
2. Onglet "Releases" → "Draft a new release"
3. Choisis le tag `v1`
4. Coche "Publish this Action to the GitHub Marketplace"
5. Choisis une catégorie (ex: "Code quality", "Security")
6. Publie

### 5. Ajoute la traçabilité blockchain (optionnel, itération suivante)
`blockchain_anchor.py` est prêt mais nécessite un test réseau réel avant
intégration dans l'Action (voir les avertissements dans ce fichier). Ne
l'ajoute au workflow qu'après l'avoir validé indépendamment.

## Distribution et visibilité, une fois publié

- Ajoute un badge dans le README des repos qui l'utilisent (GitHub génère
  automatiquement le markdown du badge sur la page Marketplace)
- Poste sur les mêmes canaux pertinents pour la communauté MCP (r/LocalLLaMA,
  Discord MCP/Anthropic, Indie Hackers) — cette fois avec un lien concret
  vers une Action utilisable, pas juste une idée à valider
