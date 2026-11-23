# Prospect — Lot 5, préparation sans recherche réelle

22 novembre 2026 — Sol. Statut : préparation arrêtée sur blocage substantiel confirmé. Aucune recette commerciale réelle autorisée ou lancée dans cette phase.

## Sources consultées et continuité

Registre officiel : https://docs.google.com/document/d/1t4DLnrdTsLi8lrhIDwg93MaE1gL1J8S5kwlMYqbH95Q/edit — lu via le connecteur Drive, notamment les passations C1 et la demande d'analyse Overpass/Tavily du 22 novembre.
Fiche Notion existante : https://app.notion.com/p/4191f4b82a02817c94c8f5d724191696 — lue via le connecteur Notion. Elle indique encore une intégration Overpass non exécutée : cette mention est en retard sur la preuve locale d'intégration déjà produite. Aucun document partagé n'a été modifié.
L'intégration locale e2866ee est documentée dans 2026-11-22-integration-locale-overpass.md. Les preuves locales priment pour connaître le code effectivement utilisé, sans effacer l'historique documentaire.

## État constaté en lecture seule

114 prospects, 3 campagnes, 100 analyses, 100 brouillons, 100 versions, aucun journal d'envoi. 143 tâches : 100 terminées et 43 en erreur ; aucune tâche en attente, en cours ou en pause. Les trois campagnes ont une récurrence désactivée et aucune prochaine échéance. Ces erreurs n'ont pas été relancées. Ce comptage ne constitue pas une nouvelle analyse des causes des 43 erreurs.

Paramètres effectifs : DISCOVERY_ENABLED=False ; fournisseur tavily ; clé présente sans lecture ou affichage de sa valeur ; plafonds 20 recherches/jour et 600/mois ; 4 liens candidats et 2 pages supplémentaires par candidat (12 pages maximum par qualification) ; budgets HTTP 500 par tâche, 60 par source et 30 par domaine sur une heure ; délai minimum 1,1 seconde ; Overpass 45 secondes par passage, 18 par endpoint ; enveloppe de consultation 70 secondes par passage. Les crédits sont réservés avant émission, y compris pour une tentative incertaine. Un quota peut reporter une tâche au prochain jour/mois : ces budgets ne constituent donc pas à eux seuls une fin automatique de pilote.

Le statut Free avec paiement à l'usage désactivé est une déclaration antérieure de Nathaniel ; le tableau de bord fournisseur n'a pas été rouvert. Aucun appel Tavily, Overpass, Nominatim ou page d'entreprise réelle dans cette préparation.

## Chaîne et déclenchement

Le worker local appelle automatiquement enqueue_due_scheduled_searches. Les récurrences existantes sont de 7, 14 ou 30 jours. Le premier clic actuel lance immédiatement la recherche ; l'interface ne propose pas une première échéance ponctuelle dans quelques minutes. Une recette planifiée rapprochée devra préciser explicitement son armement ponctuel, sans le confondre avec le clic de lancement.

Le worker tourne avec l'application locale ; aucune exécution lorsque le PC est éteint ou le service arrêté n'est démontrée. Après découverte OSM, capture et déduplication, le code crée les qualifications éligibles. Celles-ci découvrent les pages et contacts, consignent les preuves, puis appellent la préparation des brouillons manquants pour la sélection stricte globale de cinq maximum. Les brouillons existants restent conservés. Les décisions humaines, oppositions et critères Lot 3 ne sont pas assouplis. Les brouillons produits ne sont pas approuvés automatiquement.

## Vérifications réellement exécutées

Deux sondes Django supplémentaires ont été exécutées en mémoire en réutilisant les fixtures C1 et les méthodes de production. Le transport réseau réel était bloqué, les réponses fictives, les emails en mémoire. Aucune méthode commerciale n'a été exécutée dans la base réelle.

1. Chaîne planifiée : échéance fictive atteinte, appel du worker sans enqueue_search ni sélection manuelle de fiche ; premier endpoint Overpass en ReadTimeout, deuxième endpoint réussi ; capture, découverte Tavily simulée, lecture de pages fictives, qualification, sélection consultée par l'API existante et brouillon. Résultat : 1 entreprise, 1 opportunité sélectionnée, 1 brouillon personnalisé avec observation, NateOS et portfolio ; 0 approbation, 0 envoi. Toutes les preuves générées portent l'origine automatique. Test réussi.
2. Sonde d'arrêt : après cette découverte, le parent search est done, sa qualification est queued. L'appel API pause du parent répond 200 mais laisse la qualification queued et conserve next_search_at. Le test constate ce comportement ; sa réussite technique ne signifie pas que l'arrêt soit sûr. Blocage confirmé.

Les 187 tests de non-régression ont réussi lors de l'intégration immédiatement précédente ; ils n'ont pas été rejoués dans cette phase. Le frontend, la compilation et la recette visuelle réelle ne sont pas exécutés ici. La consultation API d'une fixture ne vaut pas vérification visuelle Windows.

## Blocage substantiel et arrêt

Le bouton de campagne agit sur le job search. Quand ce parent est terminé, l'interface ne propose plus sa pause et l'API de pause ne fait plus rien pour lui. Les jobs qualification créés n'ont pas de lien de parenté de tâche/campagne dédié ; ils restent actifs. Désactiver la récurrence empêche une recherche future mais n'arrête pas ces qualifications.

Une recherche marquée terminée peut donc continuer à consommer des consultations et préparer des résultats via ses qualifications. Sans dispositif borné d'arrêt de toute la chaîne, une recette ne doit pas être présentée comme arrêtable depuis le contrôle de campagne. Conformément à la consigne de Nathaniel, arrêt sur ce blocage substantiel : aucun correctif produit entrepris dans cette phase et aucun nouveau moteur développé.

Correction minimale à cadrer avant poursuite : rattacher durablement les qualifications issues d'une recherche à leur exécution ; prévoir un arrêt de campagne qui neutralise la prochaine échéance et suspend tous ses travaux, sans affecter les tâches d'autres campagnes ni les preuves déjà enregistrées ; vérifier l'arrêt avant la prochaine consultation et la reprise sans doublons. La définition d'une première échéance ponctuelle et d'une borne de consommation/durée du pilote doit aussi être rendue explicite. Tester ces garde-fous sur des données fictives avant toute autorisation de recherche réelle.

## Scénario unique proposé — non armé et non lançable en l'état

Une seule campagne « restaurants / Vitré / rayon 1 km », sans noms d'entreprise présélectionnés, avec une première échéance approuvée par Nathaniel, PC allumé et worker local disponible. Aucune reprise des 43 erreurs historiques. Déclenchement par l'échéance et non par un clic manuel sur chaque fiche.

Bornes proposées : une seule occurrence, fenêtre de 20 minutes à partir du déclenchement, maximum 5 entreprises nouvelles à qualifier selon un ordre automatique déterministe, maximum 5 tentatives Tavily basic dans cette recette, toujours sous les plafonds partagés 20/jour et 600/mois. Aucune montée en gamme, dépense, bascule de fournisseur ou extension de zone. Les critères commerciaux restent inchangés ; la sélection peut contenir de zéro à cinq opportunités.

Attention : ces bornes spécifiques de 5 entreprises, 5 tentatives et 20 minutes sont un périmètre proposé, pas des contrôles déjà implémentés ou armés. La sélection de cinq ne borne actuellement ni le nombre de fiches capturées ni le total de recherches d'une campagne. Le scénario ne devient lançable qu'après preuve des contrôles d'arrêt et de bornage.

Mesurer : échéance et heure de démarrage effectif ; entreprises identifiées et dédupliquées ; contacts corroborés, incertains ou absents ; preuves recevables avec URL/date/origine ; exclusions ; opportunités retenues et raisons ; nouveaux brouillons personnalisés et versions ; tentatives/crédits réservés ; reports et erreurs ; instant d'arrêt et absence de poursuite. Toute intervention manuelle est consignée et exclue du résultat autonome. Aucune approbation ni aucun envoi pendant la recette.

Point d'arrêt obligatoire maintenu : présenter le périmètre final, les contrôles éprouvés et la date/heure à Nathaniel, puis obtenir son autorisation explicite distincte avant armement ou consultation commerciale réelle. La présente mission ne vaut pas cet accord.

## Où retrouver les résultats après une future recette autorisée

Recherches : campagne, progression et erreurs. Prospects : filtre par campagne. Qualification : Sélection commerciale, preuves, réserves et brouillon de chaque dossier ; À enrichir pour les blocages. Les anciens brouillons restent dans leur historique ; ne pas les comptabiliser comme une nouvelle livraison.

## Préservation

Empreintes de la base SQLite, des deux .env et des réglages privés identiques avant/après les sondes. Aucune donnée ou configuration réelle changée, aucun serveur/worker réel démarré pour cette préparation, aucun envoi, recherche commerciale, commit, push, déploiement ou dépense. Aucun code produit, critère commercial ou style modifié. Ce rapport est local uniquement.
