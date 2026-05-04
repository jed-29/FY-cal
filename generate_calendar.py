import re
import hashlib
from datetime import date
import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event

URL = "https://www.impots.gouv.fr/professionnel/calendrier-fiscal"
OUTPUT_FILE = "calendrier-fiscal.ics"

HEADERS = {
    "User-Agent": "Mozilla/5.0 calendrier-fiscal-outlook"
}

MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}

NOISE_EXACT = {
    "professionnel",
    "partager la page",
    "partager sur twitter",
    "partager par courriel",
    "partager sur facebook",
    "partager sur linkedin",
    "copier dans le presse-papier",
    "votre avis sur le site",
    "paramètres d’affichage",
    "paramètres d'affichage",
    "contact et prise de rdv",
    "service-public.gouv.fr",
    "stationnement.gouv.fr",
    "format attendu : prenom.nom@exemple.fr",
    "objet du message : informations du site impots.gouv",
    "votre adresse électronique",
    "tous les champs sont obligatoires.",
    "laisser ce champ vide",
    "utilise les paramètres système",
    "les engagements de la dgfip",
    "sécurité informatique",
    "collectivités locales",
    "sourds et malentendants - accéo",
}

NOISE_CONTAINS = [
    "choisissez un thème",
    "accessibilité",
    "partager sur",
    "copier dans le presse-papier",
]


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def is_noise(text):
    lower = clean_text(text).lower()

    if not lower:
        return True

    if lower in NOISE_EXACT:
        return True

    return any(noise in lower for noise in NOISE_CONTAINS)


def detect_month_year(soup):
    """
    Détecte le mois et l'année affichés sur la page.
    Exemple : Mai 2026
    """
    page_text = soup.get_text(" ")

    match = re.search(
        r"\b(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+(\d{4})\b",
        page_text,
        re.IGNORECASE,
    )

    if not match:
        raise ValueError("Impossible de détecter le mois et l'année du calendrier fiscal.")

    month_name = match.group(1).lower()
    year = int(match.group(2))
    month = MONTHS[month_name]

    return month, year


def make_uid(event_date, title):
    """
    UID stable : évite qu'Outlook voie les événements comme nouveaux à chaque génération.
    """
    raw = f"{event_date.isoformat()}-{title}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()
    return f"{digest}@calendrier-fiscal-impots"


def build_description(lines):
    """
    Nettoie les descriptions :
    - supprime les lignes parasites ;
    - supprime les doublons ;
    - conserve l'ordre.
    """
    clean_lines = []
    seen = set()

    for line in lines:
        line = clean_text(line)

        if is_noise(line):
            continue

        if line in seen:
            continue

        seen.add(line)
        clean_lines.append(line)

    clean_lines.append(f"Source : {URL}")

    return "\n".join(clean_lines)


def main():
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    month, year = detect_month_year(soup)

    calendar = Calendar()
    calendar.creator = "github.com/jed-29/FY-cal"

    main_content = soup.find("main") or soup.body

    elements = main_content.find_all(
        ["h1", "h2", "h3", "h4", "h5", "p", "li", "span"],
        recursive=True
    )

    current_day = None
    current_title = None
    current_description = []
    events = []

    def save_event():
        nonlocal current_day, current_title, current_description, events

        if current_day is None or not current_title:
            return

        title = clean_text(current_title)

        if is_noise(title):
            return

        event_date = date(year, month, current_day)
        description = build_description(current_description)

        events.append({
            "date": event_date,
            "title": title,
            "description": description,
        })

    for element in elements:
        text = clean_text(element.get_text(" "))

        if is_noise(text):
            continue

        # La vraie structure du calendrier fiscal est du type :
        # "À partir du 04"
        day_match = re.search(r"À partir du\s+(\d{1,2})", text, re.IGNORECASE)

        if day_match:
            save_event()
            current_day = int(day_match.group(1))
            current_title = None
            current_description = []
            continue

        # Ignore le nom du mois seul : "mai", "juin", etc.
        if text.lower() in MONTHS:
            continue

        # Ignore le titre global du mois : "Mai 2026"
        if re.search(
            r"\b(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+\d{4}\b",
            text,
            re.IGNORECASE,
        ):
            continue

        # Les titres d'échéances sont généralement dans h3 / h4 / h5.
        if element.name in ["h3", "h4", "h5"] and current_day is not None:
            save_event()
            current_title = text
            current_description = []
            continue

        # Les paragraphes et listes deviennent la description de l'événement courant.
        if current_day is not None and current_title:
            current_description.append(text)

    # Sauvegarde du dernier événement.
    save_event()

    # Tri logique pour faciliter la lecture du .ics dans GitHub.
    events.sort(key=lambda item: (item["date"], item["title"]))

    for item in events:
        event = Event()
        event.name = item["title"]
        event.begin = item["date"]
        event.make_all_day()
        event.uid = make_uid(item["date"], item["title"])
        event.description = item["description"]
        calendar.events.add(event)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(calendar.serialize_iter())

    print(f"Calendrier généré : {OUTPUT_FILE}")
    print(f"Mois détecté : {month}/{year}")
    print(f"Nombre d'événements générés : {len(events)}")


if __name__ == "__main__":
    main()
