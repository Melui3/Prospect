# ProspectApp

Application de prospection automatique : trouve les commerces locaux sans site web et contacte-les par email.

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

1. **Templates** → Créez un template email avec `{nom}`, `{ville}`, `{secteur}`
2. **Campagnes** → Créez une campagne (secteur + ville + rayon), cliquez **Lancer**
3. **Prospects** → Parcourez les prospects trouvés, envoyez des emails en un clic
4. **Dashboard** → Suivez vos stats

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
