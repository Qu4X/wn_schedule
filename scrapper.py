import requests
import re
import logging
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from icalendar import Calendar, Event

# Konfiguracja logowania
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DNI_MAPA = {"1": "PON", "2": "WT", "3": "ŚR", "4": "CZW", "5": "PT", "6": "SOB"}

SLOWNIK_PRZEDMIOTOW = {
}


def oblicz_godzine_konca(start_str, trwanie_min):
    try:
        start_dt = datetime.strptime(start_str.strip(), "%H:%M")
        koniec_dt = start_dt + timedelta(minutes=trwanie_min)
        return koniec_dt.strftime("%H:%M")
    except Exception as e:
        logger.warning(f"Błąd parsowania czasu '{start_str}': {e}")
        return start_str


def pobierz_liste_planow():
    url = "https://arktur.umg.edu.pl/planyzaj/strpza5.php"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        return {opt.get_text().strip(): opt.get("value") for opt in soup.find_all("option")}
    except Exception as e:
        logger.error(f"Nie udało się pobrać listy kierunków: {e}")
        return {}


def pobierz_dane_z_ajax(ajax_val):
    url = "https://arktur.umg.edu.pl/planyzaj/validate_sp_ka.php"
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
    payload = {"inputValue": ajax_val, "fieldID": "prowadzacy_zajecia_public"}
    try:
        r = requests.post(url, data=payload, headers=headers, timeout=5)
        r.raise_for_status()
        match = re.search(r"<komunikat>([^<]+)</komunikat>", r.text)
        if match:
            parts = match.group(1).split('_')
            if len(parts) > 1:
                return parts[1].strip()
    except Exception as e:
        logger.warning(f"Błąd AJAX dla {ajax_val}: {e}")
    return ""


def pobierz_surowy_plan(plan_id):
    url_start = "https://arktur.umg.edu.pl/planyzaj/strpza5.php"
    url_target = "https://arktur.umg.edu.pl/planyzaj/strpza6.php"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": url_start}

    try:
        session = requests.Session()
        session.get(url_start, headers=headers, timeout=10)
        payload = {"id_planu_zajec": plan_id, "id_obiektu": "1", "id_grupy": "0", "nazwa_rodzaju_zestawienia": "0"}
        r = session.post(url_target, data=payload, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Błąd pobierania surowego planu {plan_id}: {e}")
        return "", []

    html_text = r.text
    soup = BeautifulSoup(html_text, 'html.parser')

    grupy = []
    for h in soup.find_all("td", class_="komopcji"):
        txt = h.get_text(strip=True)
        if any(x in txt for x in ["GR.", "ER", "L.", "TM"]):
            if txt in grupy: break
            grupy.append(txt)

    unique_ajax_vals = set()
    for inp in soup.find_all('input', id=re.compile(r"^id_pzz_\d+_\d+_\d+$")):
        if inp.get('value') and inp.get('value') != '0':
            numer = inp['id'].replace('id_pzz_', '')
            inp2 = soup.find('input', id=f"id_pzz_{numer}_2")
            inp3 = soup.find('input', id=f"id_pzz_{numer}_3")
            v1 = inp['value']
            v2 = inp2['value'] if inp2 else '0'
            v3 = inp3['value'] if inp3 else '0'
            unique_ajax_vals.add(f"{v1}_{v2}_{v3}")

    ukryty_cache_html = '<div id="ukryta_baza_prowadzacych" style="display:none;">'
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(lambda val: (val, pobierz_dane_z_ajax(val)), unique_ajax_vals)
        for ajax_val, prowadzacy in results:
            ukryty_cache_html += f'<span id="ajax_{ajax_val}">{prowadzacy}</span>'

    ukryty_cache_html += '</div>'
    html_text += ukryty_cache_html

    return html_text, grupy


def _wspolny_parser_html(html_text, target_idx=None, _soup=None):
    soup = _soup or BeautifulSoup(html_text, 'html.parser')
    min_slot, max_slot = 999, 0  # DODANO: Inicjalizacja zmiennych
    zajecia_dane = {d: {} for d in DNI_MAPA.values()}

    for td in soup.find_all("td", id=True):
        tid = td['id']
        if not tid.startswith("td_"): continue
        parts = tid.split('_')
        dzien_nazwa = DNI_MAPA.get(parts[1], "Inny")
        slot_start, col_start = int(parts[2]), int(parts[3])
        colspan = int(td.get('colspan', 1))

        if target_idx is not None:
            is_in_range = col_start <= target_idx < (col_start + colspan)
            # Dodatkowo sprawdzamy, czy to nie są zajęcia ogólne (np. dla całego roku)
            if not is_in_range:
                continue

        drag = td.find('div', class_='drag')
        if drag:
            info_list = [i.strip() for i in drag.get_text("|", strip=True).split("|") if i.strip()]
            rowspan = int(td.get('rowspan', 1))
            trwanie = rowspan * 5

            if slot_start < min_slot: min_slot = slot_start
            if (slot_start + rowspan) > max_slot: max_slot = (slot_start + rowspan)

            start_font = td.find('font', color='green')
            start_h = start_font.get_text() if start_font else "??:??"
            koniec_h = oblicz_godzine_konca(start_h, trwanie)

            prowadzacy = ""
            td_text = td.get_text(" ", strip=True)
            match_prow = re.search(r"\{prow:\s*([^}]+)\}", td_text)
            data_start_match = re.search(r"\[od:\s*(\d{4}-\d{2}-\d{2})\]", td_text)
            tygodnie_match = re.search(r"\[il\.tyg:\s*(\d+)\]", td_text)

            data_start = data_start_match.group(1) if data_start_match else None
            liczba_tygodni = int(tygodnie_match.group(1)) if tygodnie_match else 8

            if match_prow:
                prowadzacy = match_prow.group(1).strip()
            else:
                numer = tid.split('_', 1)[1]
                inp1 = soup.find('input', id=f"id_pzz_{numer}")
                if inp1 and inp1.get('value') != '0':
                    inp2 = soup.find('input', id=f"id_pzz_{numer}_2")
                    inp3 = soup.find('input', id=f"id_pzz_{numer}_3")
                    val1 = inp1.get('value')
                    val2 = inp2.get('value') if inp2 else '0'
                    val3 = inp3.get('value') if inp3 else '0'

                    cache_span = soup.find('span', id=f"ajax_{val1}_{val2}_{val3}")
                    if cache_span:
                        prowadzacy = cache_span.get_text(strip=True)

            if slot_start not in zajecia_dane[dzien_nazwa]:
                zajecia_dane[dzien_nazwa][slot_start] = {}

            zajecia_dane[dzien_nazwa][slot_start][col_start] = {
                "przedmiot": SLOWNIK_PRZEDMIOTOW.get(info_list[0], info_list[0]),
                "prowadzacy": prowadzacy,
                "godziny": f"{start_h} - {koniec_h}",
                "sala": td.find('font', color='darkblue').get_text() if td.find('font', color='darkblue') else "OL",
                "height": rowspan,
                "colspan": colspan,
                "data_start": data_start,
                "tygodnie": liczba_tygodni
            }

    znani = {
        info["przedmiot"]: info["prowadzacy"]
        for dzien in zajecia_dane.values()
        for slot in dzien.values()
        for info in slot.values() if info["prowadzacy"]
    }
    for dzien in zajecia_dane.values():
        for slot in dzien.values():
            for info in slot.values():
                if not info["prowadzacy"] and info["przedmiot"] in znani:
                    info["prowadzacy"] = znani[info["przedmiot"]]

    min_slot = (min_slot // 12) * 12 if min_slot != 999 else 24
    max_slot = ((max_slot // 12) + 1) * 12 if max_slot != 0 else 144
    return zajecia_dane, min_slot, max_slot


def przetworz_plan_na_grafike(html_text, wybrana_grupa, lista_grup, _soup=None):
    if wybrana_grupa not in lista_grup:
        return {}, 0, 0

    target_idx = lista_grup.index(wybrana_grupa)
    dane_z_kolumnami, min_slot, max_slot = _wspolny_parser_html(html_text, target_idx=None, _soup=_soup)

    dane_plaskie = {d: {} for d in DNI_MAPA.values()}

    for dzien, sloty in dane_z_kolumnami.items():
        for slot_start, cols in sloty.items():
            wybrane_info = None

            # SORTUJEMY KOLUMNY: Najpierw te, które są najbliżej naszej grupy
            # To zapobiegnie nadpisaniu Twoich ćwiczeń przez wykład ogólny,
            # jeśli oba są w tym samym slocie.
            posortowane_kolumny = sorted(cols.keys(), key=lambda k: abs(k - target_idx))

            for col_start in posortowane_kolumny:
                info = cols[col_start]
                colspan = info.get("colspan", 1)

                # WARUNEK 1: Dokładne przykrycie Twojej grupy
                if col_start <= target_idx < (col_start + colspan):
                    wybrane_info = info
                    break

                # WARUNEK 2: Specjalny przypadek dla "BiSS" i Auli (kolumna 0 i duży colspan)
                # Jeśli kafelek zaczyna się w kolumnie 0 i jest szeroki (np. min 5 kolumn),
                # traktujemy go jako ogólny, o ile nie mamy już nic lepszego.
                if col_start == 0 and colspan > 5:
                    wybrane_info = info
                    # Nie robimy break, bo może dalej w pętli znajdziemy coś,
                    # co jeszcze lepiej pasuje do naszej konkretnej kolumny.

            if wybrane_info:
                dane_plaskie[dzien][slot_start] = wybrane_info

    return dane_plaskie, min_slot, max_slot


def przetworz_plan_wszystkie(html_text, lista_grup):
    return _wspolny_parser_html(html_text, target_idx=None)


def generuj_ics(dane_planu, nazwa_planu):
    cal = Calendar()
    cal.add('prodid', '-//UMG Navigator//umg.edu.pl//')
    cal.add('version', '2.0')

    def _dodaj_event(info):
        if not info.get("data_start"): return
        try:
            start_dt = datetime.strptime(f"{info['data_start']} {info['godziny'].split(' - ')[0]}", "%Y-%m-%d %H:%M")
            koniec_dt = datetime.strptime(f"{info['data_start']} {info['godziny'].split(' - ')[1]}", "%Y-%m-%d %H:%M")

            for t in range(info.get("tygodnie", 1)):
                event = Event()
                event.add('summary', info['przedmiot'])
                event.add('dtstart', start_dt + timedelta(weeks=t))
                event.add('dtend', koniec_dt + timedelta(weeks=t))
                event.add('location', f"Sala: {info['sala']}")
                event.add('description', f"Prowadzący: {info['prowadzacy']}")
                cal.add_component(event)
        except Exception as e:
            logger.warning(f"ICS - pominięto wydarzenie {info.get('przedmiot')}: {e}")

    for dzien_nazwa, sloty in dane_planu.items():
        for slot, slot_data in sloty.items():
            if "przedmiot" in slot_data:
                _dodaj_event(slot_data)
            else:
                for col_idx, info in slot_data.items():
                    if isinstance(info, dict) and "przedmiot" in info:
                        _dodaj_event(info)

    return cal.to_ical()