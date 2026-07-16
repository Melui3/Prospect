# ProspectApp

Application privee de prospection automatique : trouve des commerces, associations et artisans locaux, puis facilite le suivi et la prise de contact.

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

## Utilisation

1. **Acces prive** : configurez `OWNER_ACCESS_TOKEN`, puis entrez le token dans la sidebar.
2. **Campagnes** : lancez un preset ou creez une recherche secteur + ville + rayon.
3. **Prospects** : filtrez les resultats, ouvrez les sites, envoyez ou preparez les emails.
4. **Dashboard** : suivez vos stats.

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
