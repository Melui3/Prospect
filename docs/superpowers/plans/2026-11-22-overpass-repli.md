# Prospect — Repli Overpass borné

Mandat : proposition d’Orion approuvée par Nathaniel, confirmée dans la conversation Sol le 22 novembre 2026. Développement local et tests isolés uniquement. Pas de nouveau pilote réel.

## Architecture et limites

Conserver le transport HTTP, les budgets, les échéances persistantes et les endpoints configurés. Modifier seulement le parcours Overpass de services.py. Un timeout ou une panne de connexion peut faire examiner le point d’accès suivant ; aucun repli pour 403, 429, 5xx avec délai fournisseur, quota local, erreur TLS, réponse invalide ou erreur de programmation. Le délai global existant reste partagé par les tentatives d’un même passage.

La progression par endpoint doit survivre à un report imposé par le limiteur de débit. Le curseur et les causes réseau seront conservés dans le payload du job, sans migration. Une signature lie cet état aux filtres, coordonnées, rayon et endpoints. Une réponse vide valide termine la recherche sans chercher artificiellement des résultats ailleurs.

## Étapes et vérifications

1. Ajouter des tests avec les réponses HTTP simulées du transport existant : premier timeout puis succès ; toutes les connexions indisponibles ; budget global épuisé ; délai restant transmis ; réponse vide ; doublons OSM ; 403/429/503 ; réponse invalide ; TLS et erreur de programmation.
2. Vérifier l’échec des régressions avant correction. Corriger le repli et sa journalisation. Tester aussi une reprise de worker après report de débit, sans répéter le premier endpoint déjà échoué.
3. Exécuter la suite Django complète avec HTTP réel interdit et base en mémoire, ainsi que le contrôle de confidentialité des fichiers stagés. Le frontend n’est pas modifié. Documenter les résultats réellement obtenus et les limites, puis créer un commit local des seuls fichiers du lot.

Ne modifier ni Tavily, ni les critères commerciaux, les preuves et brouillons historiques, les fichiers de configuration privée ou la DA. Aucun push, merge, déploiement, envoi, nouvelle recherche réelle ou publication Drive automatique. Ne pas intégrer automatiquement le code du worktree dans l’application locale.

## Exécution et relecture

Tests initiaux : 10 scénarios, 4 échecs et 4 erreurs avant correction ; tous réussis après correction, suite complète 185/185.

Final: fixed réponse Overpass invalide conservée en cache — test_invalid_response_is_not_replayed_from_persistent_cache RED→GREEN. Un validateur optionnel du transport contrôle la réponse avant mise en cache et supprime une ancienne entrée rejetée. Ce complément limité au mécanisme de validation est nécessaire pour rendre la reprise effective ; aucun budget ni politique fournisseur n'est modifié.

Final: fixed type d'élément non scalaire — test_malformed_element_type_remains_a_temporary_response_error RED→GREEN. Relecture indépendante en lecture seule, deux constats corrigés en un passage. Suite finale 187/187 ; aucun constat mineur reporté.
