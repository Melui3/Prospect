# Prospect — Intégration locale Recherche d'entreprises

23 novembre 2026 — Sol → Orion. Autorisation explicite de Nathaniel : intégration locale contrôlée de b5de1a5 dans l'application habituelle, sauvegarde, tests, démarrage sans recherche réelle et transmission des preuves. Aucun commit supplémentaire autorisé ni créé.

## État final

Les treize fichiers du lot b5de1a5 sont intégrés et correspondent exactement à leurs blobs Git. L'application habituelle dispose maintenant de l'adaptateur Recherche d'entreprises pour les nouvelles recherches, avec reprise des anciens jobs Overpass sur leur source historique. Cette intégration ne valide pas un résultat commercial réel.

Git avant/après : branche principale sur 7593f64, index vide, modifications locales préexistantes préservées. Aucun merge, cherry-pick, rebase ou nouveau commit ; aucun push. Le dépôt imbriqué n'a pas été modifié. Les fichiers hors lot contrôlés, notamment le service Overpass et les protections Lot5, restent identiques à leurs empreintes Git avant intégration.

## Sauvegarde et conservation

Sauvegarde préalable dans backend/backups/integration-registry-20261123-153603/ : before.sqlite3, fichiers remplacés, manifest.json. La sauvegarde SQLite a été comparée à la base source avant modification. Aucun .env ou réglage privé n'a été ouvert pour copie ou empreinte ; ces fichiers ne font pas partie de l'intégration.

Comparaison après tests puis après démarrage/navigation/arrêt : les valeurs et nombres de lignes des21tables existantes sont identiques à la sauvegarde. IntégritéSQLiteok, aucune violation de clé étrangère. Conservation de114prospects,4campagnes,100analyses,100brouillons,100versions,0journal d'envoi et144tâches ; aucun travail actif ni récurrence. Les caches techniques et compteurs existants sont eux aussi inchangés, ce qui confirme qu'aucun parcours de découverte n'a été déclenché pendant la recette.

## Vérifications réellement exécutées

- 232testsDjango réussis depuis le dossier habituel via scripts/test-c1-isolated.py : base en mémoire, emails en mémoire, HTTP réel interdit. Les exemples API et la chaîne jusqu'au brouillon sont fictifs.
- 7testsfrontend réussis via npm test. Aucun fichier frontend du lot à compiler ; aucune compilation ni modification de la DA ou de la démo nécessaire.
- Contrôle de migration :0012 déjà appliquée, aucune migration en attente ; makemigrations --check --dry-run ne détecte aucun changement. Aucune migration exécutée.
- Contrôle Django : aucune anomalie détectée.
- Démarrage réel via le lanceur habituel, processusDISCOVERY_ENABLED=False, avec précontrôle zéro job actif/récurrence/journal d'envoi. Aucun appel de recherche ou endpoint d'envoi effectué.
- Recette native en lecture seule : Aujourd'hui (114entreprises, DA NateOS), Prospects (tableau chargé), Qualification (sélection vide et motifs), Recherches (quatre campagnes historiques), Modèles email (écran Templates email et contrôles visibles), Réglages (sections Envoi et livraison / Sauvegardes locales). Aucun bouton de lancement, reprise, analyse, génération, approbation, suppression, envoi ou enregistrement utilisé. L'édition des modèles et les actions métier avec mutation n'ont pas été testées sur les données réelles.
- Arrêt propre par Stop-Prospect.ps1 après vérification de l'identité du lanceur créé pour cette recette. Zéro processus Prospect restant et aucune écoute8765/8767 ; aucun processus tiers arrêté.
- Vérification finale : treize fichiers exacts, code hors lot inchangé, index vide, HEAD inchangé, git diff --check sans erreur.

Deux observations de navigation ont dû être actualisées après changement de géométrie ou détection d'entrée utilisateur ; aucun clic n'a été réessayé sans nouvel état. Aucun changement de données constaté après ces contrôles.

## Preuves et fichiers

Liste exacte du lot : company_discovery.py, consultations.py, identity.py, jobs.py ; test_company_discovery.py ; adaptations de fixtures dans test_c1.py,test_discovery.py,test_orchestration.py,test_overpass_fallback.py,test_personal.py,test_pilot_limits.py ; compte rendu de développement et plan du23novembre.

Journaux django-tests.log et frontend-tests.log, manifeste et integration-proof.json conservés dans la sauvegarde privée. Ne pas publier le dossier ni la base. Ce compte rendu ne contient aucune clé ni coordonnée de prospect.

## Limites et prochaine décision

Les garanties et limites du lot restent celles documentées : restaurant,boulangerie,coiffeur ou NAF explicite ; autres libellés non mappés bloqués ; pagination bornée et couverture non exhaustive ; géocodageNominatim encore externe ; correspondances NAF à revoir lors du passage2027. Une opposition inconnue ne vaut pas autorisation ; deuxSIRETdifférents ne sont pas fusionnés ; aucun contact ni besoin n'est inventé.

Aucune disponibilité, coordonnée, preuve commerciale ou rédaction réelle validée pendant cette intégration. Le critère d'un brouillon réel exploitable reste à vérifier dans un prochain pilote après nouvelle autorisation explicite. Aucune campagne ou interrogation commerciale de l'API, aucun email, push, déploiement, dépense, nouvelle fonctionnalité ou publicationDrive/Notion. Aucun commit supplémentaire.

## Retour arrière documenté, non exécuté

Après arrêt confirmé de l'application et sauvegarde de toute nouvelle donnée ultérieure, restaurer uniquement les fichiers remplacés depuis la sauvegarde et retirer uniquement les nouveaux fichiers listés dans son manifeste s'ils n'ont pas changé depuis. Aucune modification de schéma n'étant nécessaire, aucune restauration SQLite n'est requise pour annuler ce seul changement de code ; ne pas écraser les données produites ultérieurement. Aucun retour arrière n'a été nécessaire.
