# Prospect — Restauration visuelle NateOS V1

21 novembre 2026 · Sol · Développement local autorisé par Nathaniel dans la conversation.
Direction artistique : mandat Nox fourni dans la conversation. Aucun commit, push ou déploiement.

## Résultat

Identité unifiée sur les six espaces privés : noir profond, cuir brun et bordeaux,
accents dorés, titres Playfair Display, textes opérationnels sans-serif, signature
NateOS / Prospect. Cartes, tableaux, formulaires, onglets, fiches, modales et états
reprennent les mêmes codes. La navigation mobile a six entrées accessibles sur deux
rangées ; le contrôle de verrouillage reste visible. Les tableaux défilent dans leur
conteneur sans élargir la page.

Références relevées dans D:/Projets/Portfolio/src/styles/index.css et signature.css :
noir #0D0D0D, cuir #362822, bordeaux #710912, or #C28D39, ivoire #EFE5D2.
L’or clair #D6AD68 et des couleurs sémantiques plus claires sont employés pour le
texte. Les deux graisses Playfair locales proviennent des ressources déjà présentes
dans le portfolio, avec leur licence SIL OFL conservée. Aucun chargement de police
depuis un service extérieur.

## Périmètre précis

- frontend/src/personal/nateos.css : nouvelle couche visuelle isolée, 166 règles
  toutes limitées au conteneur .personal.
- frontend/src/personal/fonts/ : Playfair 400/600 et LICENSE.txt.
- frontend/src/personal/App.jsx : import du thème, signature et icône existante
  Lucide, libellés accentués, nom accessible de navigation, conteneur visuel pour
  la route privée des modèles email. Routes et gestionnaires conservés.
- frontend/src/personal/common.jsx : notifications avec texte/icône en plus de la
  couleur, chargement annoncé par role=status. Gestion des états inchangée.
- Ce compte rendu.

Le composant partagé frontend/src/pages/Templates.jsx, les styles globaux, le
transport API, les données de démo et les fonctionnalités métier sont inchangés.
Le versionnement et les approbations restent à leurs emplacements existants dans
Qualification et l’éditeur de fiche. Aucun déplacement ni ajout de fonctionnalité.

L’état préexistant non commité du Lot 4 et le dossier imbriqué Prospect/ ont été
préservés. Les empreintes de tous les fichiers suivis ont été comparées à leur
état initial : seuls les deux fichiers JSX privés ci-dessus ont changé parmi les
fichiers préexistants.

## Recette exécutée

| Espace / parcours | Résultat observé |
| --- | --- |
| Aujourd’hui | Indicateurs, relances, nouvelles fiches et activité harmonisés |
| Prospects | Filtres, tableau, statuts et fiche latérale accessibles |
| Qualification | Sélection, preuves, limites, brouillon et historique accessibles |
| Recherches | Formulaire, secteurs, zones, récurrence et historique lisibles ; aucun lancement |
| Modèles email | Liste et éditeur harmonisés uniquement dans l’espace privé ; annulation testée |
| Réglages | Formulaires et sauvegardes harmonisés ; modale de confirmation ouverte puis fermée sans restauration |
| État vide | Filtre À enrichir vide affiché, navigation conservée |
| Erreur de connexion | Serveur fictif arrêté puis Actualiser : message Attention, icône et explication visibles |
| Clavier | Passage du champ Entreprise au champ Ville par Tab vérifié ; focus doré visible dans la confirmation |
| Mobile | Six routes vérifiées à 390 puis 320 pixels, aucun débordement horizontal global |

Les tableaux gardent une largeur minimale et leur défilement horizontal.
La police locale est effectivement chargée et le titre est rendu en Prospect Editorial.
Les captures sont réalisées uniquement avec six entreprises fictives, jamais avec
les données privées. Les chargements transitoires ont été observés dans l’arbre
d’accessibilité ; leur capture visuelle systématique et une recette exhaustive au
lecteur d’écran n’ont pas été réalisées. La notification de succès a été contrôlée
en style et contraste sans soumettre de formulaire métier.

Tests réellement exécutés : 7 tests frontend réussis ; compilation Vite locale
réussie ; 163 tests Django réussis avec HTTP réel interdit, dont la sélection et le
versionnement/approbation du Lot 4 ; git diff --check réussi.
Aucun nouveau test miroir du CSS n’a été ajouté. Le contrôle PostCSS confirme le
périmètre privé des 166 règles.
Contrastes des principales paires de couleurs : texte 11,33:1 ; secondaire 6,94:1 ;
bouton principal 6,63:1 ; erreur 11,01:1 ; succès 10,24:1 ; placeholder 7,81:1 ;
bordure de champ 3,66:1. Ces mesures ne constituent pas un audit WCAG exhaustif.
Deux écarts repérés pendant la recette ont été corrigés : titre h2 du composant
partagé des modèles et libellé Qualification coupé sur mobile.

Avertissements de compilation non bloquants : données Browserslist anciennes et
sortie de recette placée hors du répertoire frontend.

## Préservation et activité parallèle constatée

Sauvegarde cohérente et manifeste initial :
backend/backups/visual-20261121/ (base, copies des fichiers privés et empreintes).
Instantané de l’état final : after.sqlite3 dans ce même dossier.
Les bases fictives et leurs serveurs ont été arrêtés/nettoyés. Aucun processus
tiers n’a été arrêté. Les ports 8765 et 8767 ne présentent plus d’écoute au contrôle final.

État réel final : 114 prospects, 2 campagnes, 100 analyses, 100 brouillons,
100 versions historiques, 0 journal d’envoi. SQLite integrity_check : ok.
Toutes les tables historiques, y compris leurs valeurs et dates, sont identiques
à la sauvegarde initiale, à l’exception des tables SearchJob et ServiceCache.
Schéma SQL inchangé. Réglages privés identiques par empreinte ; aucun jeton affiché.

L’empreinte du fichier SQLite a changé à cause d’une activité du lanceur réel.
Le journal backend/.desktop/service.log constate :
- 13:16:48 : GET /api/personal/today/ sur le service réel ;
- 13:16:55 : POST /api/personal/qualification/run/, réponse 202 ;
- journal modifié pour la dernière fois à 13:17:05.

Cet appel est distinct des serveurs fictifs de la recette, dont les journaux et
les données étaient isolés. L’identité de son initiateur n’est pas établie ici.
Il a ajouté 14 tâches de qualification pour les anciennes fiches non analysées :
six sont en erreur permanente, refusées par robots.txt ; huit restent queued.
Deux anciennes valeurs de cache ont évolué et six entrées ont été ajoutées.
Les 114 anciennes tâches restent identiques ; aucune preuve ou analyse n’a été
ajoutée, aucun prospect ni brouillon modifié par cette activité.
Aucune restauration, suppression ou suspension de ces tâches n’a été effectuée.
Aucune instance réelle n’est active lors du contrôle final. Un prochain démarrage
du worker réel pourrait reprendre les huit tâches en attente : leur examen est
distinct de ce lot visuel.

## Livraison et limites

Compilation finale locale : backend/backups/visual-20261121/frontend-final.
Le build actuellement servi par le lanceur habituel n’a pas été remplacé pendant
la recette. Le lanceur existant reconstruit les sources modifiées à froid.
L’application réelle n’a pas été relancée pour éviter la reprise des tâches en
attente. Aucun envoi, aucune recherche métier ni modification de permissions
déclenchés par les contrôles de recette de ce lot.

Captures avant/après et contrôles :
C:/Users/3dnat/Documents/ChatGPT/Wé/prospect-visual-20261121/
01-aujourdhui-desktop.jpg et 10-prospects-mobile.jpg donnent les aperçus principaux.
Les captures de recette ne sont pas des données de production.

Pas de publication Drive/Notion supplémentaire demandée dans ce mandat visuel.
Ce compte rendu local est prêt pour la revue de Nox, Orion et Nathaniel.
