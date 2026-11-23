# Prospect — Lot 5, arrêt complet et bornes du pilote

22 novembre 2026 — Sol. Mandat de Nathaniel : correctif local et tests isolés. Livraison dans le worktree dédié uniquement ; aucune intégration automatique dans l'application habituelle.

## Résultat

Les qualifications créées par une recherche conservent désormais leur parent. Le bouton existant de Recherches peut arrêter la campagne même quand sa découverte est terminée. L'arrêt suspend les travaux rattachés, neutralise toute prochaine échéance et met la récurrence à zéro. Il n'efface ni preuves, ni résultats, ni brouillons. Les autres campagnes ne sont pas arrêtées.

Le pilote utilise les jobs et le connecteur Tavily existants : cinq éléments d'entreprise maximum avant capture, cinq tentatives HTTP Tavily basic maximum partagées par les qualifications, et échéance absolue fixée à vingt minutes après l'heure planifiée. Les plafonds généraux 20/jour et 600/mois restent applicables. Les tentatives échouées ou incertaines comptent ; un cache valide ne consomme pas de tentative supplémentaire. Si le budget général refuse avant émission, la réservation du pilote est annulée avec la transaction.

Une interruption ne remet à zéro ni l'échéance, ni le compteur, ni la progression. Une campagne ayant déjà un pilote ne peut pas en créer une deuxième occurrence, ni réactiver sa récurrence. Un pilote explicitement arrêté ou expiré ne se reprend pas. Les campagnes ordinaires restent reprenables par action explicite, sans réactivation automatique de leur récurrence.

Les contrôles ont lieu avant consultation, après réponse, aux checkpoints et dans les transactions de capture, de preuve et de brouillon. Les brouillons automatiques du pilote restent limités à ses fiches et soumis à la sélection stricte existante ; aucune approbation automatique ni régénération des anciens brouillons.

## Preuves réellement exécutées

- 209 tests Django réussis via scripts/test-c1-isolated.py, dont 22 nouveaux tests du lot. Base et emails en mémoire, HTTP réel bloqué.
- Trajet fictif : pilote planifié non déclenché avant échéance, puis worker → capture → recherche simulée → preuves → sélection → brouillon personnalisé, portfolio, zéro approbation et zéro envoi.
- Arrêt après découverte, interruption/reprise sans doublons, arrêt pendant HTTP, réponse arrivée hors délai rejetée sans cache, absence de sixième appel Tavily malgré cinq erreurs réseau, compteur partagé et conservé, cache sans double consommation, échéance conservée après recovery.
- Migration 0011 → 0012 sur données fictives : conservation des campagnes, prospects, preuves, brouillons, versions et jobs, vérifiée sur les valeurs des anciens champs.
- Protections des deux API de campagnes, conservation du rattachement après suppression d'une campagne arrêtée, refus de reprise d'un descendant détaché de la campagne mais conservant son parent historique.
- Sept tests frontend réussis. Compilation Vite réussie, puis compilation du mode privé avec les paramètres utilisés par le lanceur (sans démarrer celui-ci).
- Revue indépendante en lecture seule : anomalies reproduites puis corrigées. Pas de seconde revue ; les tests couvrent les corrections de revue.

Les premiers tests ont échoué avant implémentation ; les régressions de relecture ont aussi été constatées avant correction. Les résultats ci-dessus sont ceux du dernier passage. Aucun test fournisseur réel ni test visuel Windows n'a été effectué. Avertissements de compilation : données Browserslist anciennes et dossier de sortie desktop hors du frontend ; compilation terminée avec succès.

## Limites explicites

Une requête déjà émise ne peut pas être annulée chez le fournisseur. Son timeout est réduit au temps restant ; une réponse après échéance ne produit pas de résultat, de cache ou de brouillon. Les appels système/réseau sous-jacents peuvent finir après l'échéance : la limite de vingt minutes est celle du traitement commercial accepté, pas une garantie de destruction d'une connexion distante à la milliseconde.

Les anciennes qualifications dépourvues de parent ne sont pas rattachées par supposition à partir d'un prospect ou d'une date. L'API signale les tâches potentiellement liées et demande un examen distinct ; les travaux dont la provenance est certaine sont arrêtés et la récurrence est désactivée malgré cette incertitude. Les tâches indépendantes ne sont ni adoptées ni comptabilisées dans la réussite du pilote. Cette règle évite d'inventer une provenance ou d'arrêter un autre travail.

Pas de test de charge multi-processus ou de disponibilité des fournisseurs publics. Les écritures de planification et d'arrêt utilisent la même transaction/verrou de campagne. Un zéro résultat réel restera un résultat recevable s'il est explicite ; aucune promesse de cinq opportunités retenues.

## Composants modifiés

backend/prospection/run_limits.py et migration 0012 ; models.py ; jobs.py ; consultations.py ; search_providers.py ; identity.py ; qualification.py ; drafts.py ; personal_api.py ; views.py ; test_pilot_limits.py. Frontend : Campaigns.jsx et api.js uniquement pour le contrôle d'arrêt existant ; aucun fichier CSS, police ou démo modifié. Plan et présent compte rendu.

Migration nécessaire mais NON appliquée à la base réelle : quatre champs sur SearchJob (parent, échéance, compteur, arrêt) et conservation des jobs quand leur campagne est supprimée. Elle sera à sauvegarder et appliquer uniquement lors d'une intégration locale contrôlée autorisée. Les résultats historiques ne sont ni convertis en preuves nouvelles ni réécrits.

## Préparation de la future recette — non exécutée

L'API propriétaire schedule-pilot accepte une heure future start_at et prépare un job à occurrence unique. Aucune requête d'armement n'a été faite hors des tests en mémoire. L'interface conserve les parcours existants ; la planification ponctuelle reste une opération de préparation contrôlée, sans nouveau formulaire.

Avant un essai réel : intégrer le lot et sa migration après sauvegarde, vérifier les paramètres effectifs et l'absence d'autre travail actif, fixer la zone, l'heure et les bornes, obtenir l'autorisation distincte de Nathaniel, puis seulement activer/ armer la recette. Aucun accord de campagne réelle n'est inféré de cette livraison.

## Préservation

Le dépôt et la base de l'application habituelle ne sont pas modifiés par ce lot. Aucun secret, fichier privé ou base réelle n'a été copié dans le worktree. La découverte reste désactivée hors des overrides de tests fictifs. Aucun envoi, campagne réelle, service payant, push, merge, déploiement ou publication Drive. Aucun développement d'un nouveau moteur ni changement des critères Lot 3 ou de la DA.
