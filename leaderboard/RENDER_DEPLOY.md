# Déployer le serveur combiné (classement + audit) sur Render

`server.py` fusionne l'API du classement ET le formulaire d'audit
organisationnel, avec une base de données SQLite partagée — nécessaire
pour que le calcul du palier Platinum puisse vérifier le palier
technique Silver d'un repo lié.

✅ **Testé réellement, y compris sous gunicorn** (le vrai serveur de
production, pas juste le serveur de développement Flask) : les deux
pages se chargent, la soumission de score fonctionne, et le cas complet
Platinum (audit organisationnel excellent + repo technique Silver) a
été vérifié de bout en bout pour la première fois — ça fonctionne.

## Déploiement sur Render (gratuit pour démarrer)

1. Crée un compte sur https://render.com (gratuit)
2. "New +" → "Web Service"
3. Connecte ton repo GitHub `mcp-trust-score-org/mcp-trust-score`
4. **Root Directory** : `leaderboard` (important — sinon Render cherche
   les fichiers à la racine du repo, pas dans ce sous-dossier)
5. **Build Command** : `pip install -r requirements.txt`
6. **Start Command** : `gunicorn server:app`
7. Plan : **Free**
8. "Create Web Service"

Render te donne une URL publique (type
`https://mcp-trust-score.onrender.com`) une fois le déploiement terminé
(quelques minutes).

## ⚠️ Limite du tier gratuit Render à connaître

Le plan gratuit met le service en veille après 15 minutes d'inactivité
— la première requête après une pause peut prendre 30-60 secondes à
répondre (le temps que le service se réveille). Pas un problème pour
un usage occasionnel, à garder en tête si tu veux une réactivité
constante (passerait alors sur un plan payant, ~7$/mois).

## ⚠️ Limite de la base SQLite sur Render (à connaître avant que ça pose problème)

Sur le tier gratuit, le système de fichiers de Render est **éphémère** —
la base `leaderboard.db` sera **réinitialisée à chaque redéploiement**
(nouveau push, ou simple redémarrage du service). Pour un usage sérieux
à moyen terme, il faudra migrer vers une vraie base de données
persistante (Render propose du PostgreSQL managé, gratuit sur un tier
limité) plutôt que le fichier SQLite local. Pas bloquant pour tester,
mais à anticiper avant de compter dessus pour de vraies données.

## Une fois déployé : branche l'Action dessus

Dans le workflow d'un utilisateur (`.github/workflows/*.yml`) :

```yaml
      - name: Vérifier la conformité MCP
        uses: mcp-trust-score-org/mcp-trust-score@v1
        with:
          server-command: 'python3 my_server.py'
          submit-to-leaderboard: 'true'
          leaderboard-api-url: 'https://ton-url-render.onrender.com'
```

## ⚠️ Point de vigilance technique : format des timestamps

Toutes les insertions en base utilisent `datetime('now')` de SQLite
(format `YYYY-MM-DD HH:MM:SS`). Si tu ajoutes un jour un script externe
qui insère des lignes avec `datetime.now().isoformat()` de Python
(format `YYYY-MM-DDTHH:MM:SS.ffffff`, avec un "T"), le tri
chronologique (`ORDER BY submitted_at`) se casse silencieusement — les
deux formats ne se trient pas correctement ensemble en comparaison de
chaînes de caractères. Toujours utiliser `datetime('now')` côté SQL
pour rester cohérent.

## Migration vers PostgreSQL (résout le problème de base éphémère)

✅ **Testée réellement** : un vrai serveur PostgreSQL 16 a été installé,
démarré, et utilisé pour tester l'intégralité du pipeline (soumission,
badges, audit, limite de fréquence, ancrage). Un vrai bug a été trouvé
et corrigé en cours de route : PostgreSQL inclut le fuseau horaire dans
ses timestamps, contrairement à SQLite, ce qui cassait la comparaison de
dates — corrigé dans `badge_tier._parse_timestamp()`.

### Créer la base PostgreSQL sur Render

1. Sur Render, "New +" → "PostgreSQL"
2. Nom : `mcp-trust-score-db`, plan **Free**
3. Une fois créée, copie l'**"Internal Database URL"** (pas l'externe —
   l'interne est plus rapide et gratuite pour la communication entre
   services Render)

### Connecter le service web à cette base

1. Va sur ton service `mcp-trust-score` → Environment Variables
2. Ajoute `DATABASE_URL` avec la valeur copiée à l'étape précédente
3. Sauvegarde — Render redéploie automatiquement

Le code bascule **automatiquement** sur PostgreSQL dès que cette
variable est présente — aucun autre changement nécessaire. Sans elle,
le code continue de fonctionner en SQLite (utile pour tester en local).

⚠️ **Limite du tier gratuit PostgreSQL Render** : expire après 90 jours
d'inactivité du compte de facturation (vérifie les conditions actuelles
sur render.com au moment de la mise en prod) — suffisant pour valider
le produit, mais prévoir un plan payant avant un usage long terme sérieux.
