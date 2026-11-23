# Prospect — Adaptateur Recherche d'entreprises

23 novembre 2026 — Sol → Orion. Développement local autorisé par Nathaniel. Statut : réalisé dans le worktree dédié, testé sur données fictives ; ni intégré à l'application habituelle ni validé commercialement.

## Changement ciblé

Les nouvelles recherches persistantes passent par l'API publique Recherche d'entreprises, sans appel Overpass. Le fournisseur est épinglé avant consultation. Une tâche déjà commencée avec Overpass, ou dont les éléments ont été enregistrés, conserve sa source et sa progression ; aucun historique en erreur n'est relancé. Le correctif Overpass reste présent et testé, sans repli automatique de la nouvelle API vers lui.

Le module company_discovery utilise near_point après le géocodage existant, puis vérifie les établissements de matching_etablissements. Il ne capture pas le siège hors zone. Il contrôle le SIRET et son rattachement au SIREN, l'activité NAF locale, le rayon calculé, les états administratifs et les statuts de diffusion. Une opposition commerciale explicite est conservée par les clés d'exclusion existantes ; un statut ou une opposition inconnus ne sont pas interprétés comme une autorisation.

Les données normalisées rejoignent capture_prospect et les jobs de qualification existants. L'identifiant externe siret:… reste distinct des identifiants OSM ; une ancienne fiche OSM reconnue conserve son identifiant, ses données, sa décision et son brouillon, et reçoit le lien SIRET/provenance manquant. Un changement d'enseigne avec le même SIRET ne crée pas de doublon. Deux SIRET différents de même nom/adresse produisent un blocage explicite plutôt qu'une fusion incertaine.

Aucun email ni site n'est fabriqué à partir du registre. Tavily, la corroboration des contacts, les preuves commerciales, la sélection Lot3, le générateur Lot4, les versions et approbations demeurent la chaîne aval. Une activité administrative ne constitue pas un besoin commercial vérifié.

## Documentation officielle et conditions vérifiées

Sources consultées sans interrogation d'entreprise réelle :

- Contrat OpenAPI : https://recherche-entreprises.api.gouv.fr/openapi.json et documentation https://recherche-entreprises.api.gouv.fr/docs/.
- Présentation DINUM : https://www.data.gouv.fr/dataservices/api-recherche-dentreprises et https://annuaire-entreprises.data.gouv.fr/donnees/api-entreprises.
- Base Sirene / licence / transition NAF : https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret.
- Licence Ouverte2.0 : https://www.data.gouv.fr/pages/legal/licences/etalab-2-0.
- Correspondances NAF INSEE : pages sousClasse/56.10a,56.10b,10.71c,96.02a sur https://www.insee.fr/fr/metadonnees/nafr2/ ; restauration rapide56.10C documentée dans la classe56.10, page détaillée non récupérée par l'outil lors du contrôle.

API ouverte et gratuite ; aucune clé ni abonnement nouveau. Recherche géographique par lat/long et radius en kilomètres, plafond fournisseur50km. Pagination de25 unités légales par page maximum et liste de correspondances locales distincte du siège. Limite annoncée7requêtes/seconde/IP et30/ASN, susceptible d'être réduite ; elle n'est pas une disponibilité garantie. L'adaptateur impose au moins1,1seconde et conserve les budgets plus restrictifs de Prospect, User-Agent descriptif, refus et Retry-After.

Le champ officiel opposition_diffusion_commerciale a une signification distincte du statut de diffusion ; true, false et null sont traités séparément. La licence MIT indiquée par le contrat ne dispense pas du respect des droits sur les données. La base Sirene est sous Licence Ouverte2.0 : attribution et dates source/consultation sont conservées, sans prétendre à une caution de l'administration. Aucune règle d'envoi n'est assouplie et l'accès public ne vaut pas autorisation générale de prospection.

## Bornes, reprise et minimisation

Quatre pages maximum,25 unités par page, première page de100établissements correspondants par unité. Maximum100établissements normalisés hors pilote et5avant capture pour un pilote. Pages non consultées, couverture limitée et candidats effectivement omis sont tracés ; cinq résultats exacts ne sont pas présentés comme une troncature. Ce parcours n'est pas exhaustif.

Les quotas source/domaine/tâche et les garanties Lot5 sont réutilisés. HTTP429/Retry-After,403,5xx et pannes réseau restent des erreurs/report explicites. Le schéma et les compteurs de pagination incohérents ne deviennent pas une recherche vide réussie. Un arrêt pendant HTTP empêche la capture et une reprise repart des checkpoints validés.

Les réponses sont demandées en mode minimal, sans dirigeants/finances. Les corps HTTP du registre ne sont pas mis en cache, y compris404/410 ; seuls les établissements acceptés et leurs provenances utiles sont conservés dans le job. Cette option ne change ni le cache Tavily ni celui d'Overpass. Une interruption après réponse et avant checkpoint peut refaire la page ; pas de garantie exactement-une-fois, mais budgets et tentatives restent bornés.

## Résultats réellement exécutés

232 tests Django réussis via scripts/test-c1-isolated.py, dont23 tests du nouveau lot. Base et emails en mémoire, HTTP réel bloqué. Les tests ont échoué avant implémentation ; les constats de la revue ont été reproduits avant correction puis vérifiés par la suite complète.

Démonstration simulée : campagne sans fiche préexistante → réponse administrative représentative → établissement normalisé → Tavily simulé → source publique fictive → contact corroboré → preuve de carte tierce → sélection stricte →1brouillon conditionnel personnalisé avec observation, NateOS et portfolio, zéro approbation/envoi et aucune intervention par fiche. Ce résultat satisfait le critère technique, pas le critère commercial réel.

Autres contrôles : siège extérieur/établissement local ; mauvais NAF/rayon/statut ; opposition et inconnus ; SIRET doublonné ou conflictuel ; reprise sans répétition de la page validée ; plafond de pages ; huit candidats donnent cinq captures et trois omissions ; HTTP temporaires/permanents ; arrêt ; données sensibles rejetées du cache ; décisions et brouillons historiques conservés sur fixtures. Les tests Lot5 et Overpass restent exécutés.

makemigrations --check --dry-run : aucune modification détectée. Aucun modèle ni migration modifié. Frontend, DA et démo inchangés : tests frontend/compilation/recette visuelle non réexécutés dans ce lot.

## Fichiers du lot

company_discovery.py et test_company_discovery.py nouveaux ; jobs.py pour le routage et les états ; identity.py pour le lien SIRET et les conflits ; consultations.py pour la seule option de non-cache brut du registre. Fixtures de fournisseur adaptées dans test_c1.py,test_discovery.py,test_orchestration.py,test_personal.py,test_pilot_limits.py ; test_overpass_fallback.py épingle explicitement sa reprise historique Overpass. Plan et présent rapport.

## Préservation et limites restantes

Worktree initial propre sur sol/prospect-dev, base6cb4749, correctifs e2866ee et6cb4749 préservés. Aucune opération d'écriture dans l'application habituelle, aucun fichier privé ni base copiés dans le worktree. Contrôle en lecture seule : les16fichiers du Lot5 restent exactement ceux de6cb4749 dans l'application habituelle ; intégritéSQLiteok ;114prospects,4campagnes,100analyses,100brouillons,100versions,0journal d'envoi et144jobs ; aucun actif.

Un contrôle automatique a refusé la lecture des fichiers privés pour en calculer des empreintes. Vérification remplacée sans ouvrir ces fichiers : code intégré et compteurs métier en lecture seule. Aucune vérification cryptographique des réglages privés revendiquée pour ce lot.

Libellés préconfigurés : restaurant,boulangerie,coiffeur. Un code NAF explicite est accepté ; les autres libellés non mappés s'arrêtent sans élargissement arbitraire. Les correspondances NAF rév.2 doivent être revues lors du passage annoncé à la NAF2025 au début2027. Le filtre d'activité de l'API porte sur l'entreprise ; des établissements d'activité secondaire peuvent donc manquer malgré le recontrôle local. Le géocodage Nominatim reste une dépendance externe et une commune ambiguë exige une vérification du périmètre avant pilote.

Aucune disponibilité ni qualité de résultat fournisseur réel mesurée, aucun nouveau contact ou brouillon réel produit. Le critère commercial reste à vérifier après autorisations distinctes d'intégration locale puis de campagne bornée. Aucun moteur nouveau, refonte, envoi, push, déploiement, dépense ou publication Drive/Notion dans ce lot.
