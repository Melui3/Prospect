import requests
from bs4 import BeautifulSoup
import time

# ============================================================
# OVERPASS — récupère les commerces via OpenStreetMap
# ============================================================

def search_overpass(secteur, ville):
    tags = {
        "boulangerie":  '"shop"="bakery"',
        "restaurant":   '"amenity"="restaurant"',
        "coiffeur":     '"shop"="hairdresser"',
        "pharmacie":    '"amenity"="pharmacy"',
        "plombier":     '"craft"="plumber"',
        "electricien":  '"craft"="electrician"',
        "garage":       '"shop"="car_repair"',
    }

    tag = tags.get(secteur.lower(), f'"shop"="{secteur}"')

    # D'abord on récupère les coordonnées de la ville
    geo = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": ville, "format": "json", "limit": 1},
        headers={"User-Agent": "local-audit-app"},
        timeout=10
    ).json()

    if not geo:
        print(f"❌ Ville '{ville}' introuvable.")
        return []

    lat = geo[0]["lat"]
    lon = geo[0]["lon"]
    print(f"📍 {ville} trouvée : {lat}, {lon}")

    # Ensuite on cherche dans un rayon de 5km
    query = f"""
    [out:json][timeout:25];
    node[{tag}](around:5000,{lat},{lon});
    out body;
    """

    print(f"📡 Interrogation OpenStreetMap...")

    response = requests.get(
        "https://overpass.kumi.systems/api/interpreter",
        params={"data": query},
        timeout=30
    )

    data = response.json()
    return data["elements"]

# ============================================================
# PAGES JAUNES — enrichissement email
# ============================================================

def search_pages_jaunes(nom, ville):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }

    url = f"https://www.pagesjaunes.fr/pagesblanches/recherche?quoiqui={nom}&ou={ville}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Cherche un mailto:
        for link in soup.find_all("a", href=True):
            if "mailto:" in link["href"]:
                return link["href"].replace("mailto:", "").strip()

        return None
    except:
        return None


# ============================================================
# PROSPECTION PRINCIPALE
# ============================================================

def run_prospection(secteur, ville):
    print(f"\n🔍 Recherche : {secteur}s à {ville}\n")

    elements = search_overpass(secteur, ville)

    if not elements:
        print("❌ Aucun résultat. Essaie un autre secteur ou une autre ville.")
        return

    prospects = []
    avec_site = []

    for element in elements:
        tags = element.get("tags", {})

        info = {
            "nom":       tags.get("name", "Sans nom"),
            "site":      tags.get("website", tags.get("contact:website", None)),
            "telephone": tags.get("phone", tags.get("contact:phone", None)),
            "email":     tags.get("email", tags.get("contact:email", None)),
            "adresse":   tags.get("addr:street", "Adresse inconnue"),
            "ville":     tags.get("addr:city", ville),
        }

        if not info["site"]:
            prospects.append(info)
        else:
            avec_site.append(info)

    # Enrichissement Pages Jaunes pour ceux sans email
    print(f"📖 Enrichissement Pages Jaunes ({len(prospects)} prospects)...")
    for i, prospect in enumerate(prospects):
        if not prospect["email"]:
            email = search_pages_jaunes(prospect["nom"], ville)
            if email:
                prospect["email"] = email
                print(f"   ✉️  Email trouvé pour {prospect['nom']} !")
        time.sleep(0.5)  # On est polis, on spamme pas le serveur


    # ============================================================
    # AFFICHAGE
    # ============================================================

    print(f"\n{'='*60}")
    print(f"  📊 RÉSULTATS — {secteur.upper()} à {ville.upper()}")
    print(f"{'='*60}")
    print(f"  ✅ Avec site web    : {len(avec_site)}")
    print(f"  🔥 Sans site web   : {len(prospects)} (tes prospects !)")
    print(f"{'='*60}\n")

    if prospects:
        print("🔥 PROSPECTS CHAUDS :\n")
        for p in prospects:
            print(f"  📌 {p['nom']}")
            print(f"     📍 {p['adresse']}, {p['ville']}")
            print(f"     📞 {p['telephone'] or '❌ Pas de téléphone'}")
            print(f"     📧 {p['email']    or '❌ Pas email trouvé'}")
            print()
    else:
        print("👏 Tout le monde a un site ici. Essaie une autre ville !")

    return prospects, avec_site


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    secteur = input("Secteur d'activité (ex: boulangerie) : ")
    ville   = input("Ville : ")
    run_prospection(secteur, ville)