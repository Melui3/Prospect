# Prospect — Résultats du pilote réel du 23 novembre 2026

## Bilan commercial : aucune opportunité livrée

Le pilote a bien été programmé et déclenché automatiquement, puis s'est terminé en échec technique de découverte avant toute consultation Tavily. Il ne démontre pas l'autonomie commerciale complète de Prospect.

| Étape / mesure | Résultat réel |
| --- | --- |
| Périmètre | Restaurants, Vitré, rayon 1 km, une occurrence |
| Programmation | Campagne 9, job 144, échéance 10 h 00, fin absolue 10 h 20, Paris |
| Déclenchement observé | 10 h 00 min 00,100861 s ; job running / Recherche des entreprises |
| Fin automatique de recherche | 10 h 04 min 05,531466 s ; error / Échec définitif documenté |
| Arrêt explicite de campagne | 10 h 05 min 17 s ; récurrence désactivée, aucun travail restant |
| Entreprises identifiées / nouvelles / doublons | 0 / 0 / 0 ; aucun lot OSM exploitable reçu |
| Contacts corroborés / preuves commerciales recevables | 0 / 0 ; étapes non atteintes |
| Opportunités sélectionnées / brouillons nouveaux | 0 / 0 ; étapes non atteintes |
| Consultations Overpass | 5 requêtes HTTP, dans 3 passages automatiques du worker |
| Recherches Tavily basic / crédits du pilote | 0 / 0 ; Tavily non atteint |
| Emails, approbations, aide manuelle par fiche | 0 / 0 / aucune |

Toutes les heures du tableau sont celles de Paris le 23 novembre 2026. L'arrêt anticipé respecte la fenêtre maximale de vingt minutes ; aucune nouvelle tentative n'a été créée après épuisement du budget du worker.

## Déroulement et causes observées

Préconditions revérifiées avant le lancement : seize fichiers identiques au commit 6cb4749, migration 0012, intégrité SQLite, clé présente sans affichage, plafonds 20/jour et 600/mois, aucune concurrence et aucune récurrence autre que le seul job pilote planifié. Au début de la recette, zéro crédit Tavily réservé ce jour et un réservé pour le mois, issu du contrôle technique antérieur.

L'automatisation a repris cette conversation avant l'échéance. Elle a lancé le seul lanceur existant avec DISCOVERY_ENABLED=True uniquement dans l'environnement de cette instance ; aucun .env modifié. L'interface locale était disponible avant 10 h. Le worker a pris lui-même le job à 10 h : aucune commande de recherche, qualification ou rédaction par fiche n'a été exécutée par Sol.

1. Premier passage : ReadTimeout sur overpass-api.de vers 10 h 00 min 18 s, puis HTTP 502 de z.overpass-api.de à 10 h 00 min 19 s. Report automatique au plus tôt à 10 h 01 min 22,879945 s.
2. Deuxième passage : ReadTimeout sur z.overpass-api.de vers 10 h 01 min 41 s, puis HTTP 502 de lz4.overpass-api.de. Report automatique au plus tôt à 10 h 03 min 46,182680 s.
3. Troisième passage : ReadTimeout sur lz4.overpass-api.de vers 10 h 04 min 05 s. Budget de trois tentatives du worker épuisé ; outcome permanent_error, statut error, aucun quatrième passage prévu.

Le repli réseau intégré a donc été utilisé et sa progression persistante a fonctionné. Les HTTP 502 ont interrompu le passage avec délai de reprise, conformément aux restrictions existantes ; aucun contournement ni changement de fournisseur. Ces traces démontrent l'échec technique du parcours Overpass, mais ne permettent pas de départager une défaillance du serveur distant d'un intermédiaire réseau. La disponibilité publique n'a pas été réinterrogée manuellement après l'échec.

Le dernier texte d'erreur contient encore « Une reprise bornée sera programmée par le worker », alors que le statut et l'événement final confirment l'épuisement des reprises. Cette incohérence de formulation a été constatée dans l'interface ; aucun correctif n'a été développé pendant le pilote.

## Contrôles dans l'interface existante

Navigation privée vérifiée dans l'application lancée par le lanceur : Aujourd'hui → Recherches → Qualification → Recherches. Sur la campagne 9 : Vitré / 1 km, récurrence Aucune désactivée pour le pilote, état d'attente et délai de reprise, puis Interrompue / Échec définitif documenté. Le contrôle Arrêter la campagne était accessible pendant l'attente.

Qualification → Sélection commerciale affichait zéro opportunité et « Aucune opportunité ne dispose actuellement de toutes les preuves nécessaires ». Aucun bouton d'analyse, génération, approbation ou envoi utilisé. Aucun brouillon nouveau à contrôler visuellement : le parcours a échoué avant cette étape. Aucune coordonnée de prospect n'est reproduite dans ce compte rendu.

## Arrêt et préservation vérifiés

Après l'échec terminal, Sol a appelé le contrôle d'arrêt de la seule campagne 9, puis le script Stop-Prospect.ps1 pour l'instance dont le lanceur avait été créé par cette tâche (identité vérifiée). Fermeture propre confirmée : zéro processus Prospect et aucune écoute sur 8765/8767 ; zéro job actif ou en pause et aucune récurrence. Aucun processus tiers arrêté.

Comparaison à la sauvegarde avant programmation : valeurs intégrales des tables prospects, analyses, brouillons, versions, journaux d'envoi et événements métier identiques ; anciennes campagnes et anciens jobs inchangés. Conservation de 114 prospects, 100 analyses, 100 brouillons, 100 versions et zéro journal d'envoi. Le seul job pilote conserve ses erreurs et son historique. Intégrité SQLite ok ; aucune violation de clé étrangère. Les caches et compteurs de consultation techniques reflètent les cinq tentatives réelles.

Les .env et réglages privés sont identiques à leurs empreintes avant programmation. DISCOVERY_ENABLED=False reste permanent. Compteurs Tavily après la recette : zéro crédit réservé le 23 novembre, un pour le mois, inchangés. Aucun email, approbation, push, déploiement, dépense supplémentaire ni réarmement. L'automatisation à occurrence unique est supprimée après ce passage pour empêcher toute nouvelle exécution.

Preuves détaillées privées : backend/backups/pilot-20261123-vitre/programming-proof.json et execution-proof.json, avec la sauvegarde avant programmation et les traces techniques conservées par l'application. Ne pas publier ce dossier ni la base. Ce rapport est destiné à la coordination, sans secrets.

## Conclusion et suite à décider

Réussite vérifiée : programmation, déclenchement autonome à l'échéance, repli réseau, reports persistants, arrêt borné et préservation. Échec commercial : zéro entreprise identifiée et aucune livraison de brouillon. Contact, qualification, sélection et rédaction réels restent non évalués ; le bon fonctionnement Tavily n'a pas été retesté par ce pilote puisqu'il n'a jamais été appelé.

Soumettre à Orion et Nathaniel le blocage de la découverte initiale via Overpass, sans proposer une relance identique ni compter des recherches assistées comme autonomie. Toute analyse corrective, évolution de source ou nouvelle campagne réelle doit faire l'objet d'une décision distincte. Aucun développement lancé dans cette recette.

## Où Nathaniel retrouve le résultat

Recherches : campagne restaurant / Vitré / 1 km numéro 9, erreur et historique. Prospects : filtre campagne 9, aucun nouveau résultat. Qualification : Sélection commerciale vide ; les cent brouillons historiques ne sont pas des résultats de ce pilote.
