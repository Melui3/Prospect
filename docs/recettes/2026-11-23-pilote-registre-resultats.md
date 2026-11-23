# PASSATION NATEOS BRIDGE V0.2 — Prospect : pilote réel Recherche d’entreprises

23 novembre 2026 — Sol → Orion / Nathaniel.
Statut : BROUILLON PRÉPARÉ LOCALEMENT, NON TRANSMIS, NON PUBLIÉ DANS DRIVE.
Source : application habituelle D:/Projets/Prospect, SQLite réel, campagne 10, recherche 145, qualifications 146 à 150. Autorisation : mandat explicite de Nathaniel du 23/11/2026 dans la conversation Prospect. Aucun nouveau correctif autorisé ou engagé.

## Résultat et décision à examiner

ÉCHEC DU CRITÈRE COMMERCIAL : aucun brouillon personnalisé exploitable. La découverte administrative et les cinq recherches Tavily ont réellement fonctionné. La chaîne s’est interrompue pendant la consultation des pages candidates : trois refus robots.txt et deux HTTP 403. Aucun contact corroboré, aucune qualification commerciale achevée, aucune opportunité sélectionnée, aucun nouveau brouillon.

Aucune donnée fictive et aucune recherche ou rédaction manuelle fiche par fiche n’ont servi à ce résultat. Le géocodage préparatoire et le lancement technique ne sont pas comptés comme enrichissement autonome. Les tests fictifs antérieurs ne constituent pas une réussite commerciale de ce pilote.

## Préconditions et bornes

- Les 13 fichiers du lot b5de1a5 sont exacts avant/après. Migration 0012 déjà appliquée. Aucune migration, modification de code, commit, push ou déploiement pendant ce pilote. HEAD habituel 7593f64, index vide ; modifications locales préexistantes conservées.
- Sauvegarde SQLite avant préparation et lancement ; 114 prospects, 4 campagnes, 100 analyses, 100 brouillons et 100 versions historiques ; 0 journal d’envoi, 144 tâches préexistantes.
- Aucun job actif ni récurrence avant activation. Anciens travaux Overpass non relancés.
- Vitré, Ille-et-Vilaine, France : commune officielle 35360, département 35. Point résolu par Prospect 48.1244503, -1.214331, vérifié dans le contour officiel. Rayon 1 km, restaurant (NAF 56.10A/B/C). Sources géographiques : géocodeur existant et https://geo.api.gouv.fr/communes/35360 . Aucun élargissement manuel.
- Offre Free et Pay-as-you-go désactivé : confirmation antérieure de Nathaniel, non revérifiée dans le tableau de bord fournisseur pendant ce pilote. Quotas locaux 20/jour et 600/mois ; réservations initiales 0 aujourd’hui et 1 ce mois.
- Découverte activée uniquement dans l’environnement du lanceur démarré pour ce pilote. Configuration persistante DISCOVERY_ENABLED=False, encore vérifiée après arrêt.
- Campagne 10, occurrence unique, cinq entreprises maximum, cinq tentatives Tavily basic maximum, échéance absolue 16:15:10 heure de Paris. Validation humaine et exclusions inchangées, aucun envoi déclenché.

## Programmée / déclenchée / terminée

Toutes les heures suivantes sont Europe/Paris, le 23 novembre 2026.

- Programmée à 15:54:25 pour 15:55:10.155101, via schedule_pilot existant ; une seule occurrence.
- Déclenchée automatiquement par le worker du lanceur habituel : recherche 145 terminée à 15:55:11.363041, cinq fiches capturées et cinq qualifications filles créées.
- Les cinq qualifications deviennent terminales entre 15:55:17 et 15:55:48.821883. Temps entre échéance prévue et dernier résultat terminal : environ 39 secondes. Aucun succès de qualification n’est déduit du statut done de la recherche administrative ; son outcome est insufficient_evidence.
- Arrêt explicite de campagne enregistré à 15:58:37.906929, après constat des cinq échecs ; aucun enfant sans provenance signalé. Application et worker fermés proprement ensuite par Stop-Prospect.ps1, après vérification de l’identité du lanceur. Arrêt largement avant la borne de vingt minutes.
- Après arrêt : campagne paused, repeat_days=0, next_search_at=NULL, racine stopped_at renseigné ; zéro job queued/running, zéro récurrence, zéro processus Prospect restant détecté et zéro écoute sur 8765/8767.

## Mesures réellement observées

| Étape | Résultat |
|---|---:|
| Appels Recherche d’entreprises | 1 |
| Unités légales reçues sur la première page | 25 |
| Rejets d’établissements journalisés | 13 |
| Établissements retenus et capturés | 5 |
| Établissements supplémentaires omis par le plafond | 10 |
| Pages API restantes non interrogées | 6 |
| Recherches Tavily basic tentées et terminées | 5 |
| Contacts professionnels corroborés | 0 |
| Qualifications achevées / preuves commerciales recevables validées | 0 / 0 |
| Opportunités du pilote sélectionnées | 0 |
| Nouveaux brouillons / nouvelles versions | 0 / 0 |
| Emails envoyés / journaux d’envoi | 0 / 0 |

Les 25 unités légales et les compteurs d’établissements n’ont pas le même dénominateur : une unité peut exposer plusieurs établissements. Ne pas soustraire 13 et 10 de 25. Rejets : 8 oppositions commerciales, 4 états inactifs ou inconnus, 1 activité locale incompatible. Pagination arrêtée volontairement au plafond ; scope_truncated=true. Découverte non exhaustive, aucun résultat national ou au-delà du rayon n’a été ajouté manuellement.

Vingt-sept observations partielles sont conservées dans les checkpoints des qualifications. Elles comprennent recherches publiques, accès impossibles et indications d’identité certaines ou incertaines. Elles ne constituent pas vingt-sept preuves commerciales recevables et ne permettent pas d’affirmer une absence de site ou un besoin de prestation. Aucune QualificationReview créée pour ces cinq fiches, aucun contact candidat retenu.

## Fiches et blocages exacts

| Fiche | Entreprise découverte | Job | Dernier blocage |
|---|---|---|---|
| 115 | AU VIEUX VITRE | 146 | « Consultation refusée par robots.txt. » — Facebook |
| 116 | LA FABRIQUE D’EMBAS | 147 | « website (www.tripadvisor.fr) répond HTTP 403. » |
| 117 | BREIZH BOWL | 148 | « Consultation refusée par robots.txt. » — Instagram |
| 118 | LE PICHET | 149 | « website (www.tripadvisor.com) répond HTTP 403. » |
| 119 | OUI SAS | 150 | « Consultation refusée par robots.txt. » — Facebook |

Les cinq recherches Tavily ont search_completed=true. Les temporisations de consultation ont été reprises par le worker sans intervention par fiche ; chacune aboutit ensuite à un échec définitif documenté lors d’un refus de source. Les autres pages candidates et les observations partielles n’ont pas suffi à terminer la qualification. Aucun contournement des restrictions. Les fiches conservent enrichment_status=pending malgré leurs jobs en error : limite d’affichage/état à examiner, sans modification ici.

Point de blocage confirmé : consultation des sources candidates pendant discover_prospect, avant finalisation contact/preuves/qualification et avant sélection/rédaction. Le pilote ne démontre ni un problème d’accès à Tavily ni une panne de la nouvelle découverte administrative. Il ne démontre pas non plus l’absence de site des cinq entreprises. Les résultats contiennent des correspondances incertaines ; aucune opportunité n’en est inventée.

## Quotas et coûts

Racine : pilot_tavily_attempts=5. Chaque enfant journalise un appel tavily_search, soit cinq au total, mode basic du connecteur existant. Compteurs locaux après : 5/20 aujourd’hui et 6/600 ce mois, delta cinq réservations. Consommation attendue : cinq crédits basic gratuits ; la consommation exacte du compte distant et l’absence de facture n’ont pas été contrôlées dans le tableau de bord pendant l’exécution. Aucun achat, activation de facturation ou changement d’offre effectué. Un appel API Recherche d’entreprises gratuit, et consultations de pages publiques selon les restrictions existantes.

## Conservation et contrôles exécutés

Comparaison ligne par ligne des lignes préexistantes dans les sept tables suivies : aucun prospect, campagne, analyse, brouillon, version, journal d’envoi ou job historique modifié ou supprimé. Après : 119 prospects, 5 campagnes, 100 analyses, 100 brouillons, 100 versions, 0 journal d’envoi, 150 jobs. Seuls cinq prospects, une campagne et six jobs sont ajoutés dans ces tables ; caches et compteurs techniques évoluent normalement. Les enregistrements d’opposition durables sont conservés selon le moteur existant.

SQLite integrity_check=ok, zéro violation de clé étrangère. Aucun dossier réel copié dans le worktree. Aucune modification DA, critère commercial, réglage privé ou approbation humaine. Aucun test fictif supplémentaire nécessaire ni lancé pendant cette exécution réelle. Contrôles exécutés : préflight, géographie, suivi des six jobs, arrêt contrôlé, comparaison SQLite, intégrité/relations, compteurs, empreintes des treize fichiers, index Git, processus et ports. Interface non réinspectée visuellement pendant ce pilote ; résultats vérifiés en lecture seule dans les données persistées, application fermée après arrêt.

## Preuves privées et accès Nathaniel

Preuves locales privées : backend/backups/pilot-registry-20261123-155339/ : before.sqlite3, baseline-ids.json, geography-proof.json, programming-proof.json, result-proof.json, code-proof.json. Ne pas publier la base, les caches ni les réglages. Ce compte rendu omet les clés et coordonnées personnelles non nécessaires.

Pour revoir : ouvrir Prospect normalement, puis Recherches → restaurant / Vitré, Ille-et-Vilaine, France / 1 km (campagne 10) ; Prospects → fiches 115 à 119. Qualification ne contient aucune nouvelle opportunité recevable ; les 100 brouillons visibles restent historiques. Ne pas utiliser Reprendre ou relancer la campagne sans nouvelle autorisation.

## Propositions pour revue, sans exécution

1. Examiner pourquoi un refus d’une page candidate rend toute la qualification définitivement en échec plutôt que de permettre une conclusion bornée à partir d’autres sources autorisées. Cette exécution ne préjuge pas du correctif pertinent.
2. Examiner la cohérence entre statut technique des jobs et état pending des fiches, et la visibilité des checkpoints partiels.
3. Décider séparément d’un diagnostic ou correctif et de tout nouveau pilote. Aucun cycle de correction engagé, aucune seconde campagne créée.

Transmission : passation préparée localement uniquement. Aucune publication Drive/Notion ni message envoyé à Orion dans cette mission.
