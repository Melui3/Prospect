# Prospect — Pilote commercial du 23 novembre 2026

## Statut : PROGRAMMÉ, NON DÉCLENCHÉ, NON TERMINÉ

Autorisation explicite de Nathaniel : restaurants à Vitré, rayon 1 km, une seule occurrence, cinq entreprises maximum, cinq tentatives Tavily basic maximum, fenêtre du 23 novembre 2026 de 10 h à 10 h 20, heure de Paris. Aucun email, push, déploiement ni dépense supplémentaire.

Campagne locale : 9. Job pilote : 144. Échéance persistante : 2026-11-23T10:00:00+01:00 (09:00 UTC). Fin absolue : 2026-11-23T10:20:00+01:00. État actuel : queued, aucune tentative et aucun résultat commercial produit. Récurrence désactivée.

## Préconditions vérifiées avant armement

Les seize fichiers du lot correspondent au commit 6cb4749 ; migration 0012 présente dans la base attendue ; intégrité SQLite ok. Aucun processus Prospect ni écoute sur 8765/8767 au contrôle préalable. Aucun job en attente, en cours ou en pause et aucune récurrence avant création du seul job pilote.

Clé Tavily présente sans affichage ni déplacement. Fournisseur tavily, basic imposé par le connecteur ; plafonds généraux 20/jour et 600/mois. Avant programmation : zéro crédit réservé pour le 23 novembre et un crédit réservé pour novembre, soit au moins cinq disponibles. L'offre Free et le paiement à l'usage désactivé ont été confirmés précédemment par Nathaniel ; aucun tableau de bord fournisseur n'a été rouvert et le code local ne peut certifier le compte commercial associé à la clé.

Les bornes, arrêts et reprises sont ceux du lot testé et intégré, sans nouvelle modification de code. Une réponse déjà en cours peut finir après l'échéance mais elle doit être rejetée ; aucun report de la fenêtre. Les anciennes tâches en erreur ne sont pas reprises.

## Déclenchement automatique configuré

Une tâche Codex attachée à cette conversation est ACTIVE : « Exécuter le pilote Prospect du 23 novembre », identifiant ex-cuter-le-pilote-prospect-du-23-novembre. Une seule exécution, préparation à 9 h 58 le 23 novembre (fuseau Windows/Paris vérifié). Elle doit revérifier les préconditions, démarrer le lanceur existant avec DISCOVERY_ENABLED=True uniquement dans le processus du pilote, puis laisser le worker existant prendre le job à 10 h. Aucun clic de lancement ni recherche manuelle par entreprise n'est prévu.

Les fichiers .env et réglages privés restent inchangés, avec DISCOVERY_ENABLED=False permanent. Une instance ou un travail concurrent détecté avant lancement doit bloquer le pilote, sans arrêt de processus tiers. La tâche doit suivre sa propre exécution jusqu'à la fin ou l'échéance, arrêter le seul pilote et l'instance qu'elle a lancée, vérifier l'absence de travaux résiduels, rédiger le bilan et le transmettre à Orion.

Prérequis d'exécution : PC allumé, éveillé, session Windows disponible et Codex ouvert à 9 h 58. Il ne s'agit pas d'un service cloud ni d'un réveil matériel garanti. Une exécution tardive ne doit jamais repousser 10 h 20 ; après cette heure, aucune recherche et aucun réarmement.

## Préservation et preuves locales

Sauvegarde SQLite avant armement et preuve détaillée dans backend/backups/pilot-20261123-vitre/. Ce dossier est privé : ne pas le publier. La programmation ajoute uniquement une campagne et un job futur ; les 114 prospects, 100 analyses, 100 brouillons, 100 versions et zéro journal d'envoi sont conservés. Aucune recherche réelle exécutée pendant la préparation ; HTTP bloqué dans le processus d'armement.

Preuve de programmation à transmettre immédiatement à Orion. Les résultats réels seront transmis après exécution par la tâche autorisée et distingueront : déclenchement constaté, fin/arrêt constaté ou blocage. Ne pas confondre cette programmation avec une réussite autonome démontrée.

## Où retrouver les futurs résultats

Recherches → campagne 9, restaurant / Vitré / 1 km. Prospects → filtre de cette campagne. Qualification → Sélection commerciale ou À enrichir, avec preuves et brouillons à relire. Aucun brouillon ne doit être approuvé ni envoyé pendant cette recette.
