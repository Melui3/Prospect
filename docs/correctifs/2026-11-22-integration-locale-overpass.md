# Prospect — Intégration locale Overpass

22 novembre 2026. Intégration contrôlée autorisée explicitement par Nathaniel dans la conversation Sol.

Avant : application habituelle au commit Git 7593f64 ; services.py et consultations.py identiques au parent du correctif ; test_overpass_fallback.py absent. Aucun processus Prospect identifié, aucune écoute sur 8765/8767.

Après : les cinq fichiers du commit e2866ee ont été intégrés sans merge ni cherry-pick. Leur empreinte Git correspond exactement au commit source. Les autres modifications locales et le dépôt imbriqué sont préservés. Aucun nouveau commit créé dans l'application habituelle ; HEAD reste 7593f64.

Sauvegarde des fichiers remplacés et manifeste de contrôle : backend/backups/integration-overpass-20261122-214637/. Pour revenir en arrière, restaurer uniquement les fichiers remplacés depuis cette sauvegarde et retirer uniquement les nouveaux fichiers listés dans son manifeste, après vérification de leur absence de modifications ultérieures. Les données privées ne figurent pas dans ce rapport.

Validation exécutée depuis le dossier habituel : scripts/test-c1-isolated.py — 187 tests Django réussis, base et emails en mémoire, HTTP réel interdit. Contrôle des empreintes après tests : base SQLite, éventuels journaux SQLite, configurations privées et travaux locaux suivis inchangés. Paramètre effectif DISCOVERY_ENABLED=False vérifié sans afficher de clé. git diff --check réussi.

Aucune migration, aucun lancement du serveur/worker, aucune campagne ou recherche réelle, aucun email, push ou déploiement. Le correctif sera chargé au prochain lancement habituel. Aucune disponibilité réelle d'Overpass n'est démontrée par ces tests simulés. Le frontend et la DA n'ont pas été modifiés.
