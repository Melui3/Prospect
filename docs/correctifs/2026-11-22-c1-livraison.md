# Prospect — Correctif C1 : livraison locale et recette

22 novembre 2026 · Sol → Nathaniel / Orion · Publication Drive non autorisée et non effectuée.

## Statut

Axes A, B, C et D intégrés localement. Recette automatisée et Windows sur données fictives réussie. Aucun fournisseur réel interrogé : cette livraison ne prouve pas encore l'autonomie commerciale sur des entreprises réelles.

Autorisation : mandat de Nathaniel dans la conversation, développement local, sauvegardes et tests isolés. Aucun envoi, campagne réelle, dépense, commit, push, déploiement ou Lot 5 réalisé par Sol. Un commit local supplémentaire `7593f64` a été constaté après l'interruption, sans commande de commit exécutée par Sol ; son auteur opérationnel n'est pas établi ici. Il a été préservé.

Sources lues : registre central Prospect et passations, diagnostic C1 / arbitrage d'Orion ; `docs/visual/2026-11-21-nateos-restauration.md`. La rectification de Nathaniel est retenue : le raccourci fonctionne ; son démarrage manquait de retour visible.

## A — Lanceur Windows

Le raccourci et sa cible sont conservés. Le lanceur propriétaire affiche un indicateur séparé et discret : préparation, éventuelle reconstruction de l'interface, accès privé, serveur/worker, ouverture. Aucun pourcentage artificiel. Le verrou existant reste responsable de l'instance unique ; un clic supplémentaire signale cette même instance.

L'indicateur ferme après identification de la fenêtre, sur erreur, arrêt ou disparition de son parent. Une défaillance de ce retour facultatif ne doit pas empêcher le lancement. La visibilité native Windows a été mesurée ; une capture directe fiable de cet indicateur n'a pas pu être obtenue dans cette session.

La recette a aussi démontré un défaut préexistant : un arrêt pendant l'ouverture pouvait laisser le navigateur dédié en arrière-plan. Avant correction : huit processus Edge QA résiduels. Après correction : zéro, port libéré. Le nettoyage vérifie le processus créé, le chemin de son exécutable et son profil dédié ; aucun navigateur tiers n'est ciblé. Une fermeture normale est essayée avant un arrêt de cet arbre de processus si nécessaire.

## B — Découverte interchangeable et bornée

Le parcours HTML Brave bloqué est remplacé par l'API officielle Tavily via un adaptateur `PROVIDERS`. Aucun repli automatique vers un autre moteur, miroir ou formule payante. Aucun SDK supplémentaire.

Le transport impose `basic`, désactive les paramètres automatiques, la réponse synthétique, les images et le contenu brut. Il ne conserve comme résultats utiles que les URL candidates, le fournisseur et la date. Ces résultats ne constituent pas des preuves commerciales : les pages restent vérifiées séparément, avec restrictions robots, identité, contacts et exclusions existants.

Les budgets par défaut sont 20 tentatives par jour et 600 par mois, selon le calendrier Europe/Paris. La réservation persistante intervient avant HTTP ; les échecs et tentatives incertaines comptent aussi. Un budget local atteint reporte l'exécution sans appel externe. Les quotas généraux par source/domaine, échéances et tentatives bornées du Lot 1 restent applicables.

Cache partagé de résultats pendant 24 heures et cache HTTP par tâche pour les reprises. L'empreinte HTTP inclut désormais le corps JSON : deux requêtes POST distinctes ne partagent plus une réponse par erreur. HTTP 429 / Retry-After, 5xx et erreurs réseau utilisent les reprises persistantes. Clé refusée, quota fournisseur ou réponse inexploitable donnent un blocage explicite, jamais une recherche vide réussie. Les secrets d'authentification ne sont pas ajoutés aux journaux, preuves ou caches.

`DISCOVERY_ENABLED=False` par défaut. Ce réglage désactive le nouveau moteur de recherche, pas tous les autres accès réseau historiques de l'application. Le worker réel n'a pas été lancé pour la recette. Les 14 tâches réelles restent inchangées et ne sont pas relancées.

## C — Qualification et historiques

Motifs de non-sélection affichés dans le résumé et sur chaque fiche : adresse absente/invalide, contact non corroboré, preuves commerciales insuffisantes, décision humaine, exclusion, doublon ou limite des cinq places. Le résumé compte le premier blocage par fiche, pas tous ses défauts cumulés.

L'interface distingue la sélection actuelle, les propositions dont historiques et le pilote. Le bouton est renommé « Analyser les fiches sans analyse », conformément à sa requête réelle. Les règles, seuils, ordre et exclusions du Lot 3 ne sont pas assouplis.

La reprise historique reste conditionnelle : aucune origine n'est déduite ni aucune date rafraîchie. En particulier, une ancienne observation sans origine démontrée n'est pas promue en preuve automatique. Aucun dossier réel n'a été converti. Pour une reprise ultérieure : établir une correspondance traçable avec la source/passation d'origine, conserver la preuve initiale et sa date, documenter méthode et limites, tester sur copie, puis requalifier avec les critères inchangés. Sans justification, conserver le blocage ou prévoir une nouvelle recherche explicitement autorisée. Une reprise humaine/assistée ne compte pas comme réussite autonome.

## D — Emails personnalisés et versions

Le générateur conditionnel du Lot 4 est conservé. L'accès à une régénération dépend toujours de la sélection stricte. L'interface identifie un brouillon historique et demande une confirmation explicite avant remplacement par une nouvelle version personnalisée. Les anciennes versions sont conservées ; une nouvelle version doit être approuvée à nouveau.

Scénario automatisé complet : campagne fictive secteur/ville → entreprise fournie par Overpass simulé, sans fiche préexistante → Tavily simulé → pages fictives → contact et observation corroborés → sélection → brouillon automatique → requête d'approbation simulée. Aucun enrichissement manuel fiche par fiche dans ce scénario. Un autre scénario conserve un ancien brouillon, régénère explicitement, approuve puis modifie le texte et vérifie l'invalidation.

Recette écran, uniquement sur deux fixtures QA : dossier recevable, email avec observation datée, NateOS et portfolio ; ancienne version conservée, approbation de v2, modification puis v3 non approuvée ; dossier sans contact et provenance manquante explicitement bloqué. Ces fixtures UI préfabriquées ne sont pas comptabilisées comme une découverte autonome. Aucun bouton d'envoi utilisé.

## Fichiers et composants

- `backend/config/settings.py` : paramètres Tavily, plafonds et activation désactivée par défaut.
- `backend/prospection/search_providers.py` : adaptateur Tavily, cache et budgets persistants.
- `backend/prospection/consultations.py` : réservation avant émission et empreinte du JSON.
- `backend/prospection/discovery.py` : utilisation du connecteur et provenance de recherche.
- `backend/prospection/selection.py` : collecte des explications, sans changement des critères.
- `backend/prospection/selection_diagnostics.py` : diagnostics en lecture seule.
- `backend/prospection/personal_api.py` : exposition des motifs et explications d'échec.
- `backend/prospection/test_discovery.py` : fixtures adaptées à l'API, tests existants conservés.
- `backend/prospection/test_c1.py` : 12 nouveaux tests C1, dont parcours campagne complet.
- `frontend/src/personal/Qualification.jsx` : motifs, distinction des historiques et confirmation de régénération.
- `frontend/src/personal/Today.jsx`, `Campaigns.jsx` : explication des blocages des sources.
- `scripts/Start-Prospect.ps1`, `Startup-Status.ps1` : retour visuel et nettoyage d'arrêt précoce.
- `scripts/test-c1-isolated.py` : tests Django en mémoire, HTTP réel interdit et emails en mémoire.
- Ce compte rendu. Aucun modèle ni migration modifié ; CSS, polices et structure NateOS conservés.

## Tests réellement exécutés

| Contrôle | Résultat |
| --- | --- |
| Suite Django complète, base en mémoire et HTTP réel interdit | 175 réussis, 0 échec au dernier passage |
| Frontend | 7 réussis, 0 échec |
| Compilation privée Vite | Réussie |
| Syntaxe des deux scripts PowerShell | 0 erreur |
| Lancement à froid, clic pendant démarrage, clic instance active | Une seule écoute ; même instance |
| Arrêt complet, port libéré, second lancement puis arrêt | Réussi ; zéro navigateur QA et indicateur résiduels |
| Arrêt pendant ouverture | Échec reproduit avant correction ; réussi après correction |
| Port occupé par notre écouteur fictif | Erreur explicite, code 1 ; écouteur préservé |
| Contrôle des écarts Git | Pas d'erreur de whitespace ; avertissement LF/CRLF non bloquant |
| Revue indépendante du code | Aucun défaut important supplémentaire identifié ; pas de test exécuté par le relecteur |

Les deux processus Python observés sont le lanceur de l'environnement virtuel et son enfant Python : une seule chaîne d'exécution et un seul serveur en écoute, pas deux serveurs concurrents.

Des passages intermédiaires ont échoué : fonctionnalités encore absentes avant intégration, anciennes fixtures HTML à adapter, puis un scénario de double-clic qui supposait à tort que le premier PID gagnait nécessairement le verrou. Ce scénario attend désormais la prise de propriété avant le second clic. Les résultats finaux ci-dessus remplacent ces passages ; ils n'effacent pas leurs limites de diagnostic.

Non exécutés : API Tavily réelle, campagne réelle, délivrabilité, envoi réel, audit visuel exhaustif mobile et clavier des six espaces après C1. Les avertissements Vite concernent les données Browserslist anciennes et le dossier de compilation placé hors du frontend.

## Préservation et preuves

Sauvegarde préalable : `backend/backups/c1-20261122/`, dont `before.sqlite3`, fichiers source et manifeste d'empreintes. Ce dossier privé contient aussi des sauvegardes de réglages : ne pas le publier ni l'ajouter à Git.

Comparaison finale : empreintes de SQLite, `.env` et réglages privés identiques à l'état initial ; aucune table réelle modifiée ; `integrity_check = ok`. Conservation de 114 prospects, 2 campagnes, 100 analyses, 100 brouillons, 100 versions, 0 journal d'envoi et 128 tâches. Les six fichiers sources de DA/polices contrôlés sont identiques au manifeste initial.

Preuves locales dans ce dossier : `preservation.json`, `django-tests-final.log`, `frontend-tests-final.log`, `frontend-build-final.log`, `launcher-final.json`, `launcher-port-conflict.json`, `feedback-native.txt`, scripts de recette, `c1-qualification.png` et `c1-non-selection.png`. Les captures ne montrent que des données fictives.

Commande de vérification isolée depuis le dépôt : `backend\.venv\Scripts\python.exe -B scripts\test-c1-isolated.py`.

## Prérequis et procédure avant un essai réel — NON exécutée

1. Disposer d'un compte Tavily Researcher gratuit, sans carte ni facturation à l'usage. Vérifier ce statut dans son tableau de bord : le code ne peut pas certifier le type de compte associé à une clé.
2. Configurer `TAVILY_API_KEY` uniquement côté serveur sur le PC, par variable d'environnement ou fichier `.env` local ignoré par Git. Ne pas transmettre la clé dans une conversation, capture, URL ou document partagé. Le jeton privé d'accès à Prospect est distinct et reste inchangé.
3. Vérifier `DISCOVERY_PROVIDER=tavily`, `TAVILY_DAILY_LIMIT=20`, `TAVILY_MONTHLY_LIMIT=600`. Laisser `DISCOVERY_ENABLED=False` jusqu'à l'autorisation explicite du lot réel.
4. Faire approuver un petit périmètre réel secteur/zone, non une liste d'entreprises préchoisies. Sauvegarder, vérifier l'absence d'autres jobs/récurrences et isoler les 14 anciens échecs. Ne pas les reprendre automatiquement.
5. Après cette seule autorisation : activer le connecteur pour la recette, lancer un lot borné, suivre crédits et états, puis arrêter le worker à sa fin. Mesurer la chaîne sans aide manuelle : entreprises découvertes, contacts corroborés, preuves recevables, sélection de zéro à cinq, brouillons ou blocages explicites.
6. Contrôler les preuves, les destinataires et les versions exactes ; arrêter la recette avant tout envoi. Une approbation d'un brouillon ne constitue pas une autorisation d'envoi pour cette mission. Désactiver la découverte après la recette si l'exploitation n'est pas autorisée.

Références fournisseur consultées : [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search), [crédits](https://docs.tavily.com/documentation/api-credits), [tarifs](https://www.tavily.com/pricing), [usages permis](https://help.tavily.com/articles/5880393096-permitted-use-customer-applications). L'offre annonce 1 000 crédits gratuits mensuels sans carte ; une recherche basic vaut un crédit. L'usage commercial est permis, sans garantie de service de l'offre gratuite.

## Limites et décision attendue

La qualité et la couverture réelles de Tavily ne sont pas encore mesurées. Robots, homonymies et données insuffisantes peuvent laisser la sélection vide : c'est un blocage explicite, pas une raison d'abaisser les critères. Les modèles de rédaction restent conditionnels, sans modèle de langage ajouté.

Les compteurs locaux concernent cette base Prospect, pas les usages d'une même clé par d'autres applications. Restaurer une ancienne sauvegarde de SQLite ou supprimer les compteurs peut remettre leur état en arrière : avant une telle opération, rapprocher les crédits du tableau de bord fournisseur. Une interruption après émission mais avant réception ne permet pas de garantir une requête exactement une fois ; les réservations conservatrices et tentatives bornées limitent l'impact.

À décider séparément : configuration de la clé, autorisation d'une recette réelle bornée, puis publication de cette passation dans le registre existant. Aucun de ces trois actes n'a été effectué.
