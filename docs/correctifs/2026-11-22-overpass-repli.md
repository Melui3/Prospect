# Prospect — Correctif du repli Overpass

22 novembre 2026 — Proposition Orion approuvée par Nathaniel dans les conversations Orion et Sol. Développement et tests isolés uniquement.

## Cause confirmée et correction

Le transport convertit les pannes réseau en ConsultationError. Le parcours Overpass propageait immédiatement cette exception : le point d'accès suivant n'était jamais consulté après un timeout. Un résultat vide provoquait au contraire une consultation supplémentaire inutile.

services.py permet désormais un repli limité aux timeouts et pannes de connexion. Les endpoints configurés sont conservés et dédupliqués. Les refus HTTP, quotas, délais fournisseur, erreurs TLS et réponses invalides interrompent ce parcours : aucun contournement de restriction. Une réponse vide valide termine la recherche, sans devenir une qualification positive.

Le délai global reste partagé entre les tentatives du passage. Chaque requête reçoit au maximum le temps restant. Le curseur du prochain endpoint et les causes réseau datées sont enregistrés dans le payload existant de la tâche. La reprise après une attente imposée par le débit ne répète pas le premier endpoint déjà indisponible. Une signature lie le curseur aux paramètres de recherche et à la liste des endpoints. Aucun changement de schéma.

Une indisponibilité totale reste une erreur temporaire explicite, soumise aux limites de tentatives déjà présentes dans le worker. Les identifiants OSM sont dédupliqués par couple type/identifiant. Les exceptions de programmation ne sont plus masquées comme une absence de résultat.

## Fichiers du lot

- backend/prospection/services.py : repli, validation des réponses et progression persistante.
- backend/prospection/consultations.py : validation optionnelle avant mise en cache ; invalidation ciblée d'une ancienne réponse en cache rejetée par ce validateur. Les autres appels conservent leur comportement.
- backend/prospection/test_overpass_fallback.py : douze tests de régression fictifs.
- docs/superpowers/plans/2026-11-22-overpass-repli.md : périmètre et plan.
- Ce compte rendu.

## Preuves exécutées

Avant correction : dix nouveaux tests exécutés, quatre échecs et quatre erreurs. Après correction : dix tests réussis, suite complète de 185 tests réussie. Une relecture indépendante a identifié deux anomalies supplémentaires : réponse invalide rejouée depuis le cache et type d'élément mal formé classé comme erreur de programmation. Les deux tests ajoutés ont échoué avant correction, puis réussi dans la suite complète finale : **187 tests, aucun échec**, exécutés via scripts/test-c1-isolated.py.

Cas couverts : timeout puis succès ; indisponibilité de tous les endpoints ; épuisement du délai global ; transmission du délai restant inférieur à une seconde ; résultat vide ; déduplication ; refus 403, 429 et 503 avec Retry-After ; réponse invalide ; TLS ; erreur de programmation ; reprise persistante après un report de débit sans répétition de la première connexion.

Les réponses invalides ne sont plus mises en cache ; une réponse valide reste réutilisable sans nouvelle consultation. Un champ type contenant une liste produit une erreur temporaire explicite. Les deux constats de la relecture ont été corrigés ; aucun autre constat n'a été reporté.

Le runner impose une base en mémoire, les emails en mémoire, la découverte désactivée et interdit les véritables requêtes HTTP. Les tests utilisent uniquement des données fictives. Le frontend n'a pas changé ; aucune compilation ni recette visuelle Windows n'a été exécutée pour ce correctif.

## Préservation et limites

Le correctif reste dans le worktree de développement : aucune intégration automatique dans l'application locale. Aucune base réelle, configuration privée, clé, preuve historique ou brouillon n'a été modifié. Tavily, la DA, les critères du Lot 3 et les règles d'approbation restent inchangés. Aucun envoi, recherche réelle, push, merge ou déploiement.

Les instances publiques Overpass restent susceptibles d'être indisponibles ; les tests simulés ne prouvent pas leur disponibilité ni la réussite commerciale du parcours réel. Les restrictions et délais des fournisseurs priment sur le repli. La documentation officielle rappelle les limites d'usage : https://dev.overpass-api.de/overpass-doc/en/preface/commons.html.

La reprise du pilote réel, l'intégration dans l'application locale et une nouvelle publication Drive ne sont pas effectuées dans ce lot.
