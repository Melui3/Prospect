# Prospect — Intégration locale du Lot 5

22 novembre 2026 — Sol. Autorisation explicite de Nathaniel : intégration contrôlée de 6cb4749, sauvegarde préalable, migration 0012, vérification de conservation et tests ; transmission du bilan à Orion. Aucun pilote réel autorisé.

## Réalisé et vérifié

- Prospect arrêté avant intervention ; aucun processus de l'application ni écoute sur 8765/8767. Aucun processus tiers arrêté.
- Aucun conflit sur les destinations ; index Git vide. Les modifications préexistantes et le dépôt imbriqué sont préservés.
- Sauvegarde préalable vérifiée : backend/backups/integration-lot5-20261122-222849/. Base SQLite sauvegardée par l'API backup, contrôle d'intégrité et comparaison des empreintes logiques ; fichiers remplacés et ancien frontend compilé conservés.
- Les 16 fichiers du commit local 6cb4749 sont intégrés dans l'application habituelle et correspondent exactement à leurs blobs Git. Aucun cherry-pick, merge ou nouveau commit ; HEAD principal reste 7593f64 et l'index reste vide.
- Migration prospection.0012 appliquée avec succès sur la seule base SQLite locale attendue. Plan préalable vérifié : uniquement cette migration. Aucun HTTP possible dans le processus de migration.
- Comparaison avant/après migration puis après tests : valeurs de tous les anciens champs et nombres de lignes identiques dans les 21 tables existantes. Seule différence attendue : inscription de la migration 0012 dans django_migrations et ajout des champs de contrôle. Champs de contrôle par défaut sur les 143 tâches historiques ; aucun pilote armé.
- Conservation : 114 prospects, 3 campagnes, 100 analyses, 100 brouillons, 100 versions, 0 journal d'envoi et 143 tâches. Intégrité SQLite = ok ; aucune violation de clé étrangère.
- Empreintes des configurations privées, du correctif Overpass et des travaux locaux préexistants contrôlés inchangées. DISCOVERY_ENABLED=False vérifié sans afficher de clé. Aucun réglage sensible modifié.

## Tests et compilation réellement exécutés depuis l'application habituelle

209 tests Django réussis via scripts/test-c1-isolated.py : base en mémoire, emails en mémoire et HTTP réel interdit. Sept tests frontend réussis. Compilation privée Vite réussie avec les paramètres du lanceur : base /, API /api, démo statique désactivée et mode desktop activé. Le frontend compilé a été actualisé dans backend/desktop_static ; index et ressources référencées présents, nouveau contrôle d'arrêt inclus dans le bundle.

Contrôle des fichiers stagés : index vide. git diff --check vérifié séparément. Les journaux des tests et du build ainsi que manifest.json, migration-proof.json et integration-proof.json sont conservés dans la sauvegarde privée. Ne pas publier la base sauvegardée ni ce dossier privé.

Avertissements de build non bloquants : données Browserslist anciennes et dossier de sortie desktop hors du frontend. Aucun paquet mis à jour pour les faire disparaître.

## Limites et prochaine étape

Aucun serveur ou worker réel lancé et aucune vérification visuelle Windows exécutée pour cette intégration. Le prochain lancement habituel utilisera le code et le frontend actualisés ; il ne s'agit pas d'une recette commerciale réelle validée.

Les limites fonctionnelles documentées demeurent : une requête déjà émise peut finir après les vingt minutes, mais sa réponse hors délai est rejetée ; les anciennes qualifications sans lien de provenance certain sont signalées plutôt que rattachées par supposition. Les nouveaux pilotes conservent leurs bornes et liens après interruption.

Une recette réelle exige encore une autorisation distincte portant sur secteur/zone, heure et bornes : cinq entreprises maximum, cinq tentatives Tavily basic, vingt minutes, une occurrence et aucun email. Aucune campagne ou recherche réelle n'est armée ; découverte toujours désactivée. Aucun push, déploiement, dépense, envoi ou publication Drive effectué.

## Retour arrière si nécessaire

Restaurer ensemble le code sauvegardé, l'ancien frontend compilé et la base avant migration, après arrêt confirmé de l'application et sauvegarde de toute donnée produite depuis. Ne jamais restaurer seulement l'ancienne base sous le nouveau code. Aucun retour arrière n'a été nécessaire ici ; aucune suppression automatique n'est prévue.
