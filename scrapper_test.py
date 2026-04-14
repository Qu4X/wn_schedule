import requests
from bs4 import BeautifulSoup


def uruchom_diagnostyke():
    plan_id = input("Podaj ID planu: ")
    szukana_wartosc = "542951_0_0"

    url_start = "https://arktur.umg.edu.pl/planyzaj/strpza5.php"
    url_target = "https://arktur.umg.edu.pl/planyzaj/strpza6.php"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": url_start}
    session = requests.Session()
    session.get(url_start, headers=headers)
    payload = {"id_planu_zajec": plan_id, "id_obiektu": "1", "id_grupy": "0", "nazwa_rodzaju_zestawienia": "0"}

    print(f"\n⏳ Pobieram HTML dla planu {plan_id}...")
    r = session.post(url_target, data=payload, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')

    print("\n" + "=" * 50)
    print(" SZUKAM W ZEWNĘTRZNYCH PLIKACH SKRYPTÓW")
    print("=" * 50)

    skrypty = soup.find_all('script', src=True)
    if not skrypty:
        print("Brak podpiętych skryptów zewnętrznych.")
        return

    for skrypt in skrypty:
        src = skrypt['src']
        if not src.startswith("http"):
            # Pełna ścieżka do skryptu, jeśli jest względna
            src = f"https://arktur.umg.edu.pl/planyzaj/{src}"

        print(f"Pobieram: {src} ...")
        try:
            r_skrypt = session.get(src, headers=headers)
            if szukana_wartosc in r_skrypt.text:
                print(f"\n✅ MAMY TO! Wartość znajduje się w pliku: {src}")

                # Wypiszmy linię, w której to jest, żeby zobaczyć strukturę słownika
                linie = r_skrypt.text.split('\n')
                for linia in linie:
                    if szukana_wartosc in linia:
                        print(f"Struktura kodu: {linia.strip()}")
                return
        except Exception as e:
            print(f"Błąd pobierania: {e}")

    print(
        "\n❌ Nie ma tego w żadnym skrypcie. Oznacza to, że przeglądarka musiała być na innym widoku (np. planie konkretnej grupy).")


if __name__ == "__main__":
    uruchom_diagnostyke()