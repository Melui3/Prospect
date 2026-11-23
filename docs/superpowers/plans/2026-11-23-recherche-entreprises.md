# Adaptateur Recherche d'entreprises — lot ciblé

Mandat : Nathaniel autorise développement dans le worktree et tests isolés, sans intégration/migration réelle ni campagne.

Architecture : module company_discovery raccordé à process_search. Réutiliser géocodage, transport, budgets, cache, checkpoints, identité, exclusions et chaîne Tavily/qualification/sélection/brouillons. Source épinglée dans le payload avant requête ; historique Overpass repris avec sa source, jamais relancé automatiquement. Pas de repli API vers Overpass.

Contrat officiel consulté le 23/11/2026 : https://recherche-entreprises.api.gouv.fr/openapi.json et https://www.data.gouv.fr/dataservices/api-recherche-dentreprises. near_point avec lat/long, radius en km≤50, filtres NAF ; matching_etablissements, pas le siège par défaut. Recontrôle du rayon et de l'activité locale. Requête minimale sans dirigeants/finances. Respect de opposition_diffusion_commerciale et statuts de diffusion ; inconnu ne vaut pas autorisation. Donnée administrative ne vaut ni besoin commercial ni contact vérifié.

Bornage : 25 unités légales/page, 4 pages maximum, 100 correspondances/entreprise sur leur première page, 100 établissements normalisés maximum hors pilote et 5 pour un pilote. Couverture limitée explicitement tracée ; aucune prétention d'exhaustivité. Reprises persistantes par checkpoints normalisés ; le cache HTTP brut est désactivé pour ce seul adaptateur, y compris sur erreur, sans changer les caches Tavily/Overpass. Une interruption après réception et avant checkpoint peut refaire cette page, sous les budgets et tentatives existants. Minimum 1,1 seconde, protections HTTP existantes, 429/Retry-After et erreurs réseau inchangés. Normalisation SIRET et attribution API distincte d'OSM ; aucun email/site inventé.

Secteurs : restaurant, boulangerie, coiffeur via correspondances NAF rév.2 vérifiées et code NAF explicite accepté ; autres libellés sans correspondance = blocage explicite, sans élargissement arbitraire. Couverture et changement NAF en2027 à documenter.

- [x] Tests RED contrat, siège extérieur/établissement local, rayon, activité, statuts/opposition, identifiants, pagination/reprise, HTTP, données minimales et trajet automatique.
- [x] Implémentation et adaptations des doubles de fournisseur dans les tests existants, sans suppression des tests Overpass.
- [x] Suite complète, migration inchangée, revue indépendante finale et éventuelle correction vérifiée.
- [x] Documentation, revue du diff, contrôle des blobs stagés, commit local explicite et passation complète à Orion. Pas de publication Drive implicite.

## Exécution et revue

Les tests ont été écrits avant implémentation et constatés en échec, puis le trajet complet simulé a réussi. Revue indépendante en lecture seule, puis une passe de corrections avec régressions observées avant correction :

- Final: fixed conflit de SIRET à même identité — test_different_sirets_at_the_same_address_never_merge RED→GREEN, refus explicite au lieu d'une fusion.
- Final: fixed réponse vide incohérente et pagination — test_empty_results_with_positive_total_are_not_a_success RED→GREEN ; contrôles avant traitement et pas de fausse absence de résultat.
- Final: fixed compteur des omissions et troncature — test_exactly_five_results_are_not_reported_as_truncated et scénario pilote RED→GREEN ; trois omissions sur huit candidats, zéro sur cinq exacts.
- Final: fixed données rejetées et corps d'erreur conservés — test_rejected_names_and_error_bodies_are_not_cached RED→GREEN ; option cache_response=False utilisée uniquement pour le registre, cache normalisé dans le job.

Final: Ruling: ne pas inventer une équivalence entre deux SIRET distincts malgré nom/adresse communs — l'identité unique actuelle ne permet pas leur fusion ; coût : blocage explicite à examiner plutôt que création ou fusion incertaine.
Final: Ruling: limiter les libellés sectoriels préconfigurés aux trois correspondances vérifiées, accepter un NAF explicite et bloquer les autres — coût : couverture sectorielle volontairement limitée jusqu'à validation de nouvelles correspondances.

Suite finale 232/232, dont 23 tests propres au lot ; frontend non modifié. Migration : aucune modification détectée. Aucune intégration réelle. Le calcul d'empreintes des fichiers privés a été refusé par le contrôle automatique ; remplacé par un contrôle en lecture seule du code intégré et des compteurs métier, sans ouvrir ces fichiers.
