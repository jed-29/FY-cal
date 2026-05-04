import re
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

NOISE_WORDS = [
    "partager par courriel",
    "partager sur facebook",
    "partager sur linkedin",
    "copier dans le presse-papier",
    "votre avis sur le site",
    "paramètres d’affichage",
    "paramètres d'affichage",
    "accessibilité",
    "contact et prise de rdv",
    "service-public.gouv.fr",
    "stationnement.gouv.fr",
    "format attendu",
    "objet du message",
    "votre adresse électronique",
    "tous les champs sont obligatoires",
    "laisser ce champ vide",
    "choisissez un thème",
    "utilise les paramètres système",
    "les engagements de la dgfip",
    "sécurité informatique",
    "collectivités locales",
    "sourds et malentendants",
]


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def is_noise(text):
    lower = text.lower()
    return any(word in lower for word in NOISE_WORDS)


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
    safe_title = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return f"{event_date.isoformat()}-{safe_title[:80]}@calendrier-fiscal-impots"


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
    events_count = 0

    def save_event():
        nonlocal current_day, current_title, current_description, events_count

        if current_day is None or not current_title:
            return

        title = clean_text(current_title)

        if not title or is_noise(title):
            return

        description_lines = []

        for line in current_description:
            line = clean_text(line)

            if not line:
                continue

            if is_noise(line):
                continue

            if line == title:
                continue

            description_lines.append(line)

        event_date = date(year, month, current_day)

        event = Event()
        event.name = title
        event.begin = event_date
        event.make_all_day()
        event.uid = make_uid(event_date, title)
        event.description = "\n".join(description_lines + [f"Source : {URL}"])

        calendar.events.add(event)
        events_count += 1

    for element in elements:
        text = clean_text(element.get_text(" "))

        if not text:
            continue

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

    save_event()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(calendar.serialize_iter())

    print(f"Calendrier généré : {OUTPUT_FILE}")
    print(f"Mois détecté : {month}/{year}")
    print(f"Nombre d'événements générés : {events_count}")


if __name__ == "__main__":
    main()
