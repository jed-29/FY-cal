import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event

URL = "https://www.impots.gouv.fr/professionnel/calendrier-fiscal"
OUTPUT_FILE = "calendrier-fiscal.ics"

HEADERS = {
    "User-Agent": "Mozilla/5.0 calendrier-fiscal-outlook"
}


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def main():
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text("\n")

    calendar = Calendar()
    calendar.creator = "github.com/jed-29/FY-cal"

    # Version simple : elle récupère les lignes contenant une date.
    # On ajustera si besoin selon le format réel de la page.
    lines = [clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    current_date = None

    for line in lines:
        # Exemple attendu : 15 mai, 20 juin, etc.
        match = re.search(
            r"\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b",
            line,
            re.IGNORECASE,
        )

        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()

            months = {
                "janvier": 1,
                "février": 2,
                "mars": 3,
                "avril": 4,
                "mai": 5,
                "juin": 6,
                "juillet": 7,
                "août": 8,
                "septembre": 9,
                "octobre": 10,
                "novembre": 11,
                "décembre": 12,
            }

            year = datetime.now().year
            month = months[month_name]
            current_date = datetime(year, month, day).date()
            continue

        if current_date and len(line) > 20:
            event = Event()
            event.name = line[:120]
            event.begin = current_date
            event.make_all_day()
            event.description = f"Source : {URL}\n\n{line}"
            calendar.events.add(event)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(calendar.serialize_iter())

    print(f"Calendrier généré : {OUTPUT_FILE}")
    print(f"Nombre d'événements : {len(calendar.events)}")


if __name__ == "__main__":
    main()
