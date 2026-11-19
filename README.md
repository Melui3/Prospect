# ProspectApp

Application de prospection automatique avec acces prive et demo anonymisee : trouve des commerces, associations et artisans locaux, puis facilite le suivi et la prise de contact.

## Stack

- **Backend** : Django 5 + Django REST Framework + PostgreSQL
- **Frontend** : React 18 + Vite + Tailwind CSS 3
- **Scraping** : OpenStreetMap (Overpass API) + Pages Jaunes
- **Email** : SMTP (Gmail App Password recommandé)

## Lancement rapide

### 1. Base de données (Docker)

```bash
docker-compose up -d
```

### 2. Backend Django

```bash
cd backend
python -m venv venv
# Windows :
venv\Scripts\activate
# Mac/Linux :
source venv/bin/activate

pip install -r requirements.txt

# Copier et remplir le .env
cp ../.env.example ../.env

python manage.py migrate
python manage.py createsuperuser  # optionnel
python manage.py runserver
```

### 3. Frontend React

```bash
cd frontend
npm install
npm run dev
```

Ouvre http://localhost:5173

## Appli bureau locale

Pour utiliser Prospect sans hébergement, lancez :

```powershell
.\scripts\Start-Prospect.ps1 -Build
```

Pour l'usage quotidien, double-cliquez sur `Prospect.lnk` a la racine du projet.
`Start Prospect.bat` ouvre la meme instance.

Le script construit le frontend, démarre Django uniquement sur `127.0.0.1`,
sert l'app React depuis Django, puis ouvre une fenêtre Edge ou Chrome en mode application
avec un profil dedie a Prospect.
Vos vraies données restent dans la base locale `backend/db.sqlite3`.

Le lanceur demarre egalement un worker local : les recherches longues sont
enregistrees dans SQLite et reprennent leur avancement apres un redemarrage.
Les anciennes campagnes interrompues avant cette mise a jour restent en pause
jusqu'a une reprise manuelle. Ne lancez pas le worker contre une base hebergee.

Le raccourci connecte automatiquement le navigateur avec une cle protegee par
le compte Windows courant. L'adresse locale seule ne permet pas de lire les
donnees. Si `OWNER_ACCESS_TOKEN` existe dans `.env`, cette valeur est conservee.
La cle transite dans un fragment local, retire immediatement de l'URL et absent
des journaux HTTP. Aucun acces n'est expose sur le reseau ou sur GitHub Pages.
Verrouiller la session retire la cle du navigateur ; relancer le raccourci
la reconnecte. Le compte Windows et son navigateur doivent rester prives.

Pour couper le serveur local, lancez `Stop Prospect.bat`.

Pour ajouter l'icone Prospect au bureau Windows :

```powershell
.\scripts\Install-Prospect.ps1
```

Un deuxieme lancement remet la fenetre ouverte au premier plan.
Fermer la fenetre ou lancer `Stop Prospect.bat` arrete le serveur et le worker
apres le traitement en cours. Si le port est deja utilise par un autre service,
Prospect affiche un message et laisse ce service tourner.
Internet reste necessaire pour les recherches externes et l'envoi d'emails.
La base locale conserve les donnees deja presentes sur ce PC ; les donnees
d'une ancienne base hebergee ne sont pas importees automatiquement.

### Workflow personnel

- **Aujourd'hui** : entreprises pretes a contacter, relances dues et pipeline.
- **Recherches** : presets secteur/ville, rayon de 1 a 30 km, file d'attente,
  progression, pause et reprise. Une campagne choisie peut repeter sa recherche
  chaque semaine, toutes les deux semaines ou chaque mois; chaque cycle relance
  aussi la qualification et la preparation des brouillons. Les erreurs temporaires
  sont retentees trois fois. Aucun job ne declenche l'envoi d'un email.
- **Prospects** : toutes les pistes restent visibles, meme celles avec un site
  sans email. Une meme entreprise peut appartenir a plusieurs recherches sans
  perdre son statut, ses notes ou son historique. Supprimer une campagne ne
  supprime pas ses entreprises.
- **Fiche** : notes, priorite, statut commercial, prochaine relance, recherche
  d'email et source de l'adresse trouvee.
- **Email** : message libre ou modele editable, destinataire visible, historique
  des envois et protection contre les doubles clics. Ouvrir Gmail ne marque rien
  comme envoye : il faut confirmer l'envoi apres l'avoir effectue dans Gmail.
- **Liste** : recherche textuelle, pagination, tri et filtres favoris conserves
  dans ce navigateur.

La recherche d'email analyse jusqu'a cinq pages d'un site, en priorisant les
vrais liens contact/mentions legales. Les resultats trouves sont mis en cache
14 jours, les absences confirmees 24 heures. Une recherche manuelle sur une fiche
ignore ce cache. Une panne de site n'est pas consideree comme une absence d'email.
Cela ne garantit pas qu'une adresse soit publique ou accepte les messages.

### Brevo et sauvegardes

Dans **Reglages**, renseignez l'expediteur autorise dans Brevo et une cle **API**
Brevo, pas une cle SMTP. Le stockage local utilise Windows DPAPI : les valeurs
sont chiffrees pour le compte Windows courant et ne sont jamais renvoyees au
navigateur. Sans cle API, l'envoi conserve la configuration SMTP de `.env`.

Les nouveaux envois API enregistrent le `messageId` Brevo. Tant que le worker
tourne, les evenements de livraison sont synchronises toutes les cinq minutes.
Le statut "accepte" ne signifie pas "delivre". Les anciens envois sans identifiant
ne peuvent pas toujours etre rapproches des logs Brevo. Les reponses aux mails
restent a renseigner manuellement : aucune boite Gmail n'est lue par l'app.

Une sauvegarde SQLite coherente est faite avant une migration, puis chaque jour
ou le worker fonctionne. Les 14 dernieres sauvegardes automatiques sont gardees.
Les sauvegardes manuelles et de securite restent dans `backend/backups/`.
**Reglages** permet de sauvegarder et restaurer. La restauration exige de mettre
les recherches en pause, attend qu'aucune operation soit active et conserve une
copie de l'etat precedent. Les sauvegardes contiennent des donnees personnelles :
ne les publiez pas et prevoyez aussi une copie hors de ce disque.

### Verification

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py test prospection
```

Pour tester l'interface avec uniquement de fausses entreprises et des envois
en memoire, dans une base separee ignoree par Git :

```powershell
backend\.venv\Scripts\python.exe scripts\preview-personal.py --port 8767
```

Ouvrez ensuite `http://127.0.0.1:8767/`. Cette verification n'utilise ni les
contacts ni les cles de l'application personnelle. Aucun worker externe n'est
lance pour cette base de test.

## Demo GitHub Pages

La version publique est une demo statique autonome, avec uniquement des donnees
fictives embarquees. Elle n'appelle aucune API de prospection et n'a aucun acces
a la base locale, meme si un ancien token existe dans le navigateur.
Les modifications sont simulees en memoire et disparaissent au rechargement.
Aucun email reel ni recherche externe n'est lance.

Le workflow GitHub Pages construit cette version avec `npm run build:demo`.
Le build du bureau utilise `npm run build` avec `VITE_STATIC_DEMO=false`.

## Utilisation

1. **Acces prive** : configurez `OWNER_ACCESS_TOKEN`, puis entrez le token dans la sidebar.
2. **Demo portfolio** : partagez la version GitHub Pages, qui s'ouvre directement en demo.
3. **Campagnes** : lancez un preset ou creez une recherche secteur + ville + rayon.
4. **Prospects** : filtrez les resultats, ouvrez les sites, envoyez ou preparez les emails.
5. **Dashboard** : suivez vos stats.

La demo du portfolio est independante de l'application privee. Le mode demo de
l'ancienne API reste optionnel via `DEMO_MODE=True` et `?demo=1` ; le lanceur
bureau le desactive.

## Configuration email Gmail

1. Activez l'authentification 2 facteurs sur votre compte Google
2. Allez dans Sécurité → Mots de passe d'application
3. Générez un mot de passe pour "Mail"
4. Renseignez-le dans `.env` sous `EMAIL_HOST_PASSWORD`

## Variables de template

| Variable    | Valeur remplacée          |
|-------------|--------------------------|
| `{nom}`     | Nom du commerce          |
| `{ville}`   | Ville du prospect        |
| `{secteur}` | Secteur (boulangerie…)   |


### Découverte automatique et preuves (Lot 2)

Les qualifications issues des recherches passent par une découverte bornée. Une
requête sur le moteur public Brave existant fournit au plus quatre candidats.
Le moteur examine au plus douze pages, contrôle robots.txt et son Crawl-delay,
puis recoupe le nom, la commune, l'activité et le domaine. Les consultations,
délais et caches utilisent le Lot 1. Une source indisponible, un format inconnu
ou une identité ambiguë produit un blocage ou des preuves insuffisantes.

Les domaines d'annuaires reconnus sont configurés par
DISCOVERY_DIRECTORY_HOSTS (annuaire-restos.fr, restaurantguru.com et
pagesjaunes.fr par défaut). Un lien explicite vers un site officiel y est
recoupé sur le site cible. Les champs DISCOVERY_MAX_CANDIDATES,
DISCOVERY_EXTRA_PAGES et DISCOVERY_SEARCH_MAX_QUERIES bornent les consultations.
Les variantes d'accents, de ponctuation et de formes juridiques sont normalisées.
Les identités incomplètes restent à examiner.

Chaque observation conserve l'entreprise, la source, la date de consultation,
la méthode, les limites et l'origine automatique ou humaine. Les preuves sont
visibles dans Qualification et dans les détails des tâches d'Aujourd'hui.
Sur une ancienne fiche non décidée, « Rechercher automatiquement les preuves »
programme une nouvelle tâche explicite, en conservant les preuves antérieures
et le brouillon enregistré.

Les oppositions sont conservées sous des clés d'établissement, d'email et de
domaine propre dans le stockage local. Une suppression de fiche ne les efface
pas. Les correspondances sont conservatrices et peuvent bloquer un contact
partagé. La délivrabilité des adresses reste à vérifier avant envoi autorisé.

La recette du Lot 2 emploie des entreprises fictives et des réponses HTTP
simulées. La disponibilité réelle de Brave et la compatibilité de son HTML
restent à valider lors d'un essai autorisé. La production complète d'une
sélection commerciale et de nouveaux textes personnalisés relève des lots
suivants.

### Sélection commerciale (Lot 3)

L’onglet Sélection commerciale de Qualification présente au plus cinq
opportunités à examiner. Il est calculé en lecture seule à partir des preuves
actives, de leur date et du contact corroboré. La limite de fraîcheur est de
30 jours par défaut, configurable par SELECTION_EVIDENCE_MAX_AGE_DAYS.

L’ordre privilégie une carte publiée chez un tiers, puis des informations
pratiques dispersées, puis un indicateur HTML limité à vérifier. Les égalités
sont départagées par le nombre de sources distinctes hors moteur de recherche,
la fraîcheur de la plus ancienne preuve nécessaire et l’identifiant de fiche.
Les raisons, limites et liens de preuve sont affichés avec la prestation
NateOS correspondante, vérifiée sur le portfolio le 19 novembre 2026.

Les fiches déjà décidées, opposées ou contactées sont écartées. Les doublons
sont regroupés pour la sélection par nom/commune, contact, identifiant externe,
domaine propre et liens de fusion existants. Le regroupement est transitif et
préserve les fiches. Une décision humaine sur un doublon protège également ses
alias. Les annuaires et plateformes partagées sont exclus du regroupement par
domaine. Ces règles conservatrices peuvent limiter des établissements ayant
un contact ou un domaine commun.

Une carte ou des informations pratiques chez un tiers peuvent justifier
l’examen d’une page dédiée ou d’un site vitrine. L’absence de viewport justifie
une vérification ciblée du responsive, avec sa limite affichée. Les preuves
insuffisantes, périmées ou non traçables ne servent pas à compléter les places.
Les autres onglets conservent l’accès aux analyses et aux décisions existantes.
