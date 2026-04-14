import requests
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from icalendar import Calendar, Event

DNI_MAPA = {"1": "PON", "2": "WT", "3": "ŚR", "4": "CZW", "5": "PT", "6": "SOB"}

SLOWNIK_PRZEDMIOTOW = {
    "ZS": "Zarządzanie statkiem",
    "JOA": "J. angielski",
    "ŁM": "Łączność morska",
    "NAW-PP": "Planowanie podróży",
    "PrM": "Przewozy morskie",
    "UN": "Urządzenia nawigacyjne",
    "ETM": "Ekonomika transportu morskiego",
    "WF1": "W. fakultatywny",
    "WF2": "W. fakultatywny",
    "WM4": "W. monograficzny"
}

def oblicz_godzine_konca(start_str, trwanie_min):
    try:
        start_dt = datetime.strptime(start_str.strip(), "%H:%M")
        koniec_dt = start_dt + timedelta(minutes=trwanie_min)
        return koniec_dt.strftime("%H:%M")
    except:
        return start_str


def pobierz_liste_planow():
    url = "https://arktur.umg.edu.pl/planyzaj/strpza5.php"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        return {opt.get_text().strip(): opt.get("value") for opt in soup.find_all("option")}
    except:
        return {}


def pobierz_dane_z_ajax(ajax_val, session):
    url = "https://arktur.umg.edu.pl/planyzaj/validate_sp_ka.php"
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
    payload = {"inputValue": ajax_val, "fieldID": "prowadzacy_zajecia_public"}
    try:
        r = session.post(url, data=payload, headers=headers, timeout=5)
        match = re.search(r"<komunikat>([^<]+)</komunikat>", r.text)
        if match:
            parts = match.group(1).split('_')
            if len(parts) > 1:
                return parts[1].strip()
    except:
        pass
    return ""


def pobierz_surowy_plan(plan_id):
    url_start = "https://arktur.umg.edu.pl/planyzaj/strpza5.php"
    url_target = "https://arktur.umg.edu.pl/planyzaj/strpza6.php"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": url_start}

    session = requests.Session()
    session.get(url_start, headers=headers)
    payload = {"id_planu_zajec": plan_id, "id_obiektu": "1", "id_grupy": "0", "nazwa_rodzaju_zestawienia": "0"}
    r = session.post(url_target, data=payload, headers=headers)

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

    def fetch_wrapper(ajax_val):
        return ajax_val, pobierz_dane_z_ajax(ajax_val, session)

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_wrapper, unique_ajax_vals)
        for ajax_val, prowadzacy in results:
            ukryty_cache_html += f'<span id="ajax_{ajax_val}">{prowadzacy}</span>'

    ukryty_cache_html += '</div>'
    html_text += ukryty_cache_html

    return html_text, grupy


def przetworz_plan_na_grafike(html_text, wybrana_grupa, lista_grup):
    soup = BeautifulSoup(html_text, 'html.parser')
    target_idx = -1 if wybrana_grupa == "WSZYSTKIE" else lista_grup.index(wybrana_grupa)
    min_slot, max_slot = 999, 0
    zajecia_dane = {d: {} for d in DNI_MAPA.values()}

    for td in soup.find_all("td", id=True):
        tid = td['id']
        if not tid.startswith("td_"): continue
        parts = tid.split('_')
        dzien_nazwa = DNI_MAPA.get(parts[1], "Inny")
        slot_start, col_start = int(parts[2]), int(parts[3])
        colspan = int(td.get('colspan', 1))

        if target_idx == -1 or (col_start <= target_idx < col_start + colspan):
            drag = td.find('div', class_='drag')
            if drag:
                info_list = [i.strip() for i in drag.get_text("|", strip=True).split("|") if i.strip()]
                rowspan = int(td.get('rowspan', 1))
                trwanie = rowspan * 5

                if slot_start < min_slot: min_slot = slot_start
                if (slot_start + rowspan) > max_slot: max_slot = (slot_start + rowspan)

                start_h = td.find('font', color='green').get_text() if td.find('font', color='green') else "??:??"
                koniec_h = oblicz_godzine_konca(start_h, trwanie)

                prowadzacy = ""
                td_text = td.get_text(" ", strip=True)
                match_prow = re.search(r"\{prow:\s*([^}]+)\}", td_text)
                data_start_match = re.search(r"\[od:\s*(\d{4}-\d{2}-\d{2})\]", td_text)
                tygodnie_match = re.search(r"\[il\.tyg:\s*(\d+)\]", td_text)

                data_start = data_start_match.group(1) if data_start_match else None
                liczba_tygodni = int(tygodnie_match.group(1)) if tygodnie_match else 1

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
                        ajax_val = f"{val1}_{val2}_{val3}"

                        cache_span = soup.find('span', id=f"ajax_{ajax_val}")
                        if cache_span:
                            prowadzacy = cache_span.get_text(strip=True)

                zajecia_dane[dzien_nazwa][slot_start] = {
                    "przedmiot": SLOWNIK_PRZEDMIOTOW.get(info_list[0], info_list[0]),
                    "prowadzacy": prowadzacy,
                    "godziny": f"{start_h} - {koniec_h}",
                    "sala": td.find('font', color='darkblue').get_text() if td.find('font', color='darkblue') else "OL",
                    "height": rowspan,
                    "data_start": data_start,
                    "tygodnie": liczba_tygodni
                }

    znani_prowadzacy = {}
    for dzien in zajecia_dane.values():
        for info in dzien.values():
            if info["prowadzacy"]:
                znani_prowadzacy[info["przedmiot"]] = info["prowadzacy"]

    for dzien in zajecia_dane.values():
        for info in dzien.values():
            if not info["prowadzacy"] and info["przedmiot"] in znani_prowadzacy:
                info["prowadzacy"] = znani_prowadzacy[info["przedmiot"]]

    min_slot = (min_slot // 12) * 12 if min_slot != 999 else 24
    max_slot = ((max_slot // 12) + 1) * 12 if max_slot != 0 else 144
    return zajecia_dane, min_slot, max_slot


def przetworz_plan_wszystkie(html_text, lista_grup):
    soup = BeautifulSoup(html_text, 'html.parser')
    min_slot, max_slot = 999, 0
    zajecia_dane = {d: {} for d in DNI_MAPA.values()}

    for td in soup.find_all("td", id=True):
        tid = td['id']
        if not tid.startswith("td_"): continue
        parts = tid.split('_')
        dzien_nazwa = DNI_MAPA.get(parts[1], "Inny")
        slot_start, col_start = int(parts[2]), int(parts[3])
        colspan = int(td.get('colspan', 1))

        drag = td.find('div', class_='drag')
        if drag:
            info_list = [i.strip() for i in drag.get_text("|", strip=True).split("|") if i.strip()]
            rowspan = int(td.get('rowspan', 1))
            trwanie = rowspan * 5

            if slot_start < min_slot: min_slot = slot_start
            if (slot_start + rowspan) > max_slot: max_slot = (slot_start + rowspan)

            start_h = td.find('font', color='green').get_text() if td.find('font', color='green') else "??:??"
            koniec_h = oblicz_godzine_konca(start_h, trwanie)

            prowadzacy = ""
            td_text = td.get_text(" ", strip=True)
            match_prow = re.search(r"\{prow:\s*([^}]+)\}", td_text)
            data_start_match = re.search(r"\[od:\s*(\d{4}-\d{2}-\d{2})\]", td_text)
            tygodnie_match = re.search(r"\[il\.tyg:\s*(\d+)\]", td_text)

            data_start = data_start_match.group(1) if data_start_match else None
            liczba_tygodni = int(tygodnie_match.group(1)) if tygodnie_match else 1

            if match_prow:
                prowadzacy = match_prow.group(1).strip()
            else:
                numer = tid.split('_', 1)[1]
                inp1 = soup.find('input', id=f"id_pzz_{numer}")
                if inp1 and inp1.get('value') != '0':
                    inp2 = soup.find('input', id=f"id_pzz_{numer}_2")
                    inp3 = soup.find('input', id=f"id_pzz_{numer}_3")
                    ajax_val = f"{inp1['value']}_{inp2.get('value', '0') if inp2 else '0'}_{inp3.get('value', '0') if inp3 else '0'}"
                    cache_span = soup.find('span', id=f"ajax_{ajax_val}")
                    if cache_span: prowadzacy = cache_span.get_text(strip=True)

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

    znani = {info["przedmiot"]: info["prowadzacy"] for dzien in zajecia_dane.values() for slot in dzien.values() for
             info in slot.values() if info["prowadzacy"]}
    for dzien in zajecia_dane.values():
        for slot in dzien.values():
            for info in slot.values():
                if not info["prowadzacy"] and info["przedmiot"] in znani:
                    info["prowadzacy"] = znani[info["przedmiot"]]

    min_slot = (min_slot // 12) * 12 if min_slot != 999 else 24
    max_slot = ((max_slot // 12) + 1) * 12 if max_slot != 0 else 144
    return zajecia_dane, min_slot, max_slot

def generuj_ics(dane_planu, nazwa_planu):
    cal = Calendar()
    cal.add('prodid', '-//UMG Navigator//umg.edu.pl//')
    cal.add('version', '2.0')

    for dzien_nazwa, sloty in dane_planu.items():
        for slot, info in sloty.items():
            if not info.get("data_start"): continue

            if isinstance(info, dict) and "przedmiot" in info:
                start_dt = datetime.strptime(f"{info['data_start']} {info['godziny'].split(' - ')[0]}", "%Y-%m-%d %H:%M")
                koniec_dt = datetime.strptime(f"{info['data_start']} {info['godziny'].split(' - ')[1]}", "%Y-%m-%d %H:%M")

                for t in range(info.get("tygodnie", 1)):
                    event = Event()
                    e_start = start_dt + timedelta(weeks=t)
                    e_end = koniec_dt + timedelta(weeks=t)

                    event.add('summary', info['przedmiot'])
                    event.add('dtstart', e_start)
                    event.add('dtend', e_end)
                    event.add('location', f"Sala: {info['sala']}")
                    event.add('description', f"Prowadzący: {info['prowadzacy']}")
                    cal.add_component(event)

    return cal.to_ical()