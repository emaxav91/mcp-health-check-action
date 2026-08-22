# MCP Health Check

Outil de conformité et de disponibilité pour serveurs MCP (Model Context
Protocol) — pas un outil de pentest de sécurité (marché déjà occupé par
des éditeurs cybersécurité établis comme TrueFoundry, Lasso Security,
Qualys), mais un contrôle simple pour développeurs : **est-ce que mon
serveur MCP répond correctement et respecte les bonnes pratiques ?**

## Contexte marché (vérifié)

Le problème est réel et quantifié : plus de 40 CVE ont été révélées sur
des implémentations MCP entre janvier et avril 2026, et environ 200 000
serveurs MCP ont été évalués comme vulnérables dans un seul avis de
sécurité. L'écosystème MCP grandit vite et les outils de contrôle basique
(pas le pentest avancé) restent un vrai besoin pour les développeurs qui
publient leurs propres serveurs.

## ✅ Ce qui est réellement testé et vérifié (pas juste écrit)

Contrairement aux projets précédents (satellite, extension Chrome), celui-ci
a pu être **testé de bout en bout dans mon environnement de développement**,
parce qu'un serveur MCP communique en local (stdio), sans besoin d'accès
réseau externe :

1. Un serveur MCP de test (`test_server.py`) a été démarré, avec un outil
   bien documenté et un autre volontairement mal documenté (description vide)
2. Le checker (`checker.py`) s'est connecté à ce serveur, a récupéré son nom
   (`test-server-demo`), sa version de protocole (`2025-11-25`), et la liste
   de ses 2 outils
3. Il a correctement détecté le seul problème introduit volontairement
   (description vide sur `mystery_tool`) — **sans aucun faux positif** sur
   l'outil bien documenté
4. Le résultat JSON (`last_check.json`) est propre et structuré, prêt à être
   comparé dans le temps avec le même moteur de diff déjà construit dans les
   projets précédents (voir `ai-infra-watch-backend/fetch_and_diff.py`)

C'est la première fois dans cette série de projets qu'on a une vérification
complète, pas juste "la syntaxe compile".

## ⚠️ Ce qui reste à valider

- Testé uniquement sur un serveur MCP **local et volontairement simple**.
  Le comportement sur de vrais serveurs MCP publics (potentiellement plus
  complexes, avec transport HTTP/SSE plutôt que stdio) n'est pas vérifié.
- Le SDK MCP officiel évolue vite (version 2.0.0 utilisée ici a une API assez
  différente des tutoriels plus anciens trouvés en ligne — attention si tu
  regardes de la doc externe, les noms de champs peuvent différer).

## Installation

```bash
pip install -r requirements.txt
```

## Utilisation

```bash
# Teste ton propre serveur MCP
python3 checker.py python3 mon_serveur.py

# Ou avec le serveur de démo inclus, pour voir le format de sortie
python3 checker.py python3 test_server.py
```

## Règles de conformité actuellement vérifiées

- Le serveur répond-il correctement au handshake d'initialisation ?
- Chaque outil a-t-il une description non vide et suffisamment longue
  (un agent IA a besoin d'une bonne description pour savoir quand utiliser
  l'outil) ?

## Prochaines étapes pour en faire un vrai produit

1. **Étendre les règles de conformité** : schémas de paramètres incomplets,
   absence de gestion d'erreurs, noms d'outils ambigus
2. **Support HTTP/SSE** en plus de stdio (beaucoup de serveurs MCP publics
   tournent en HTTP)
3. **Brancher le moteur de diff + alertes** déjà construit (réutilisable
   tel quel) : surveiller un serveur MCP dans le temps, alerter si sa
   conformité se dégrade après une mise à jour
4. **Modèle freemium** : check ponctuel gratuit, surveillance continue en
   payant — même structure que les projets précédents
