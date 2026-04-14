import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from scrapper import pobierz_liste_planow, pobierz_surowy_plan, przetworz_plan_na_grafike, przetworz_plan_wszystkie, \
    generuj_ics

st.set_page_config(page_title="Plan zajęć WN", layout="wide", initial_sidebar_state="expanded")

# PAMIĘĆ PRZEGLĄDARKI (AUTOMATYCZNE ŁADOWANIE)
components.html("""
<script>
    const urlParams = new URLSearchParams(window.parent.location.search);
    if (urlParams.has('clear')) {
        window.parent.localStorage.removeItem('umg_plan_id');
        window.parent.location.search = '';
    } else if (urlParams.has('plan')) {
        window.parent.localStorage.setItem('umg_plan_id', urlParams.get('plan'));
    } else {
        const savedPlan = window.parent.localStorage.getItem('umg_plan_id');
        if (savedPlan) {
            window.parent.location.search = '?plan=' + savedPlan;
        }
    }
</script>
""", height=0, width=0)

STYLE_CSS = """
<style>
    .block-container { padding-top: 2rem !important; }
    .schedule-grid {
        display: grid;
        grid-template-columns: 65px repeat(VAR_COLS, 1fr);
        grid-template-rows: 40px repeat(VAR_ROWS, 4px);
        gap: 0; background-color: #0e1117; border: 1px solid #2d313a;
    }
    .grid-cell { border-right: 1px solid #1d2129; border-bottom: 1px solid #1d2129; }
    .header-cell { 
        background-color: #1a1e26; color: white; font-weight: bold; 
        display: flex; align-items: center; justify-content: center; 
        border-bottom: 2px solid #2d313a;
    }
    .time-cell { 
        grid-column: 1; display: flex; align-items: center; justify-content: flex-end; 
        padding-right: 8px; color: #fff; font-size: 1rem; font-weight: 500; 
        border-right: 2px solid #2d313a; 
    }
    .lesson-block {
        background-color: #1a4f8a; color: white; border: 1px solid #266cb7; border-radius: 4px;
        padding: 4px; display: flex; flex-direction: column; justify-content: flex-start;
        z-index: 10; line-height: 1.1; overflow: hidden;
    }
    .lesson-name { font-size: 0.85rem; font-weight: bold; margin-bottom: 2px; }
    .lesson-info { font-size: 0.75rem; opacity: 0.9; margin-bottom: 1px; }
    .lesson-teacher { font-size: 0.7rem; margin-top: auto; font-style: italic; opacity: 0.8; padding-top: 3px; border-top: 1px solid rgba(255,255,255,0.1); }
</style>
"""


@st.cache_data(show_spinner="Pobieram listę kierunków...")
def pobierz_liste_cached():
    return pobierz_liste_planow()


@st.cache_data(show_spinner="Pobieram plan z UMG...")
def pobierz_plan_cached(plan_id):
    return pobierz_surowy_plan(plan_id)


@st.cache_data(show_spinner=False)
def przetworz_grafike_cached(html_text, wybrana_grupa, lista_grup):
    return przetworz_plan_na_grafike(html_text, wybrana_grupa, lista_grup)


@st.cache_data(show_spinner=False)
def przetworz_wszystkie_cached(html_text, lista_grup):
    return przetworz_plan_wszystkie(html_text, lista_grup)


@st.cache_data(show_spinner=False)
def czy_zajecia_w_tygodniu(data_wybrana, data_start_zajec, liczba_tygodni):
    if not data_start_zajec: return True

    # Wyrównujemy obie daty do poniedziałku (początek tygodnia)
    poniedzialek_start = data_start_zajec - timedelta(days=data_start_zajec.weekday())
    poniedzialek_wybrana = data_wybrana - timedelta(days=data_wybrana.weekday())

    dni_diff = (poniedzialek_wybrana - poniedzialek_start).days
    tydzien_diff = dni_diff // 7

    return 0 <= tydzien_diff < liczba_tygodni


# ==========================================
# INICJALIZACJA ZMIENNYCH (KULOODPORNA)
# ==========================================
if 'plan_id' not in st.session_state:
    st.session_state.plan_id = None
if 'plan_name' not in st.session_state:
    st.session_state.plan_name = None
if 'last_sync' not in st.session_state:
    st.session_state.last_sync = None
if 'html_cache' not in st.session_state:
    st.session_state.html_cache = ""
if 'grupy' not in st.session_state:
    st.session_state.grupy = []

# Odzyskiwanie z linku
if st.session_state.plan_id is None and "plan" in st.query_params:
    plan_id = st.query_params["plan"]
    st.session_state.plan_id = plan_id

    plany = pobierz_liste_cached()
    znaleziona_nazwa = "Nieznany plan"
    for nazwa, p_id in plany.items():
        if p_id == plan_id:
            znaleziona_nazwa = nazwa
            break

    st.session_state.plan_name = znaleziona_nazwa
    st.session_state.html_cache, st.session_state.grupy = pobierz_plan_cached(plan_id)
    st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Awaryjne dociągnięcie danych (jeśli sesja wyparowała, a ID zostało)
if st.session_state.plan_id is not None and not st.session_state.grupy:
    st.session_state.html_cache, st.session_state.grupy = pobierz_plan_cached(st.session_state.plan_id)
# ==========================================

# EKRAN STARTOWY
if st.session_state.plan_id is None:
    st.title("Plany zajęć WN")
    plany = pobierz_liste_cached()
    if plany:
        wybor = st.selectbox("Wybierz kierunek:", list(plany.keys()))
        if st.button("Załaduj"):
            st.query_params["plan"] = plany[wybor]
            html_text, grupy = pobierz_plan_cached(plany[wybor])
            st.session_state.html_cache = html_text
            st.session_state.grupy = grupy
            st.session_state.plan_id = plany[wybor]
            st.session_state.plan_name = wybor
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.rerun()

# WIDOK PLANU
else:
    with st.sidebar:
        st.header("Opcje")
        st.markdown(f"**Kierunek:**<br>{st.session_state.plan_name}", unsafe_allow_html=True)

        lista_opcji = ["WSZYSTKIE GRUPY"] + st.session_state.grupy
        wybrana_g = st.selectbox("Wybierz widok:", lista_opcji)

        st.write("---")
        st.header("Kalendarz")
        wybrana_data = st.date_input("Pokaż tydzień dla daty:", datetime.now())

        # Przycisk eksportu (widoczny tylko gdy plan jest załadowany)
        if st.session_state.plan_id:
            if wybrana_g != "WSZYSTKIE GRUPY":
                dane_do_eksportu, _, _ = przetworz_grafike_cached(st.session_state.html_cache, wybrana_g,
                                                                  tuple(st.session_state.grupy))
                ics_data = generuj_ics(dane_do_eksportu, st.session_state.plan_name)
                st.download_button(
                    label=f"📅 Eksportuj {wybrana_g} (.ics)",
                    data=ics_data,
                    file_name=f"plan_{wybrana_g}.ics",
                    mime="text/calendar",
                    use_container_width=True
                )
            else:
                st.info("Wybierz konkretną grupę wyżej, aby wyeksportować jej plan do pliku .ics")

        st.write("---")
        if st.button("🔄 Odśwież dane z serwera", use_container_width=True):
            pobierz_plan_cached.clear(st.session_state.plan_id)
            html_text, grupy = pobierz_plan_cached(st.session_state.plan_id)
            st.session_state.html_cache = html_text
            st.session_state.grupy = grupy
            st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.rerun()

        if st.session_state.last_sync:
            st.caption(f"Ostatnia synchronizacja:<br>{st.session_state.last_sync}", unsafe_allow_html=True)

        st.write("---")
        if st.button("⬅️ Zmień kierunek", use_container_width=True):
            st.query_params.clear()
            st.query_params["clear"] = "1"  # Flaga dla JS
            st.session_state.plan_id = None
            st.session_state.last_sync = None
            st.rerun()

    # ==========================================
    # RYSOWANIE GRAFIKI - WIDOK WSZYSTKICH GRUP
    # ==========================================
    if wybrana_g == "WSZYSTKIE GRUPY":
        dane_all, min_s, max_s = przetworz_wszystkie_cached(st.session_state.html_cache, tuple(st.session_state.grupy))
        if min_s <= max_s:
            dni = ["PON", "WT", "ŚR", "CZW", "PT"]
            rows_count = max_s - min_s + 1
            css = STYLE_CSS.replace("VAR_ROWS", str(rows_count)).replace("VAR_COLS", str(len(st.session_state.grupy)))
            st.markdown(css, unsafe_allow_html=True)

            st.subheader("Plan dla wszystkich grup")
            tabs = st.tabs(dni)

            for tab_idx, d_name in enumerate(dni):
                with tabs[tab_idx]:
                    html = '<div class="schedule-grid">'
                    html += '<div class="grid-cell header-cell">Czas</div>'
                    for g in st.session_state.grupy:
                        html += f'<div class="grid-cell header-cell" title="{g}">{g[:5]}</div>'

                    # Siatka tła
                    for s in range(min_s, max_s + 1):
                        row = s - min_s + 2
                        if (s * 5) % 60 == 0:
                            h = 7 + (s * 5 // 60)
                            html += f'<div class="grid-cell time-cell" style="grid-row: {row} / span 12;">{h:02}:00</div>'
                        for g_idx in range(len(st.session_state.grupy)):
                            if (s - min_s) % 6 == 0:
                                html += f'<div class="grid-cell" style="grid-column: {g_idx + 2}; grid-row: {row} / span 6;"></div>'

                    # Wrzucanie kafelków
                    if d_name in dane_all:
                        for start_slot, slots_data in dane_all[d_name].items():
                            r_start = start_slot - min_s + 2
                            for col_start, info in slots_data.items():
                                start_date_obj = datetime.strptime(info["data_start"], "%Y-%m-%d").date() if info.get(
                                    "data_start") else None

                                if czy_zajecia_w_tygodniu(wybrana_data, start_date_obj, info.get("tygodnie", 1)):
                                    col = col_start + 2
                                    width = min(info["colspan"], len(st.session_state.grupy) - col_start)

                                    tooltip = f"{info['przedmiot']} | {info['godziny']} | Sala: {info['sala']}"
                                    if info.get("prowadzacy"): tooltip += f" | {info['prowadzacy']}"

                                    html += f'<div class="lesson-block" style="grid-column: {col} / span {width}; grid-row: {r_start} / span {info["height"]};" title="{tooltip}">'
                                    html += f'<div class="lesson-name">{info["przedmiot"]}</div>'
                                    html += f'<div class="lesson-info">{info["godziny"]}</div>'
                                    if info["height"] > 9:
                                        html += f'<div class="lesson-info">Sala: {info["sala"]}</div>'
                                        if info.get(
                                            "prowadzacy"): html += f'<div class="lesson-teacher">{info["prowadzacy"]}</div>'
                                    html += '</div>'

                    html += '</div>'  # Zamknięcie głównego div'a grida!
                    st.markdown(html, unsafe_allow_html=True)

    # ==========================================
    # RYSOWANIE GRAFIKI - WIDOK POJEDYNCZEJ GRUPY
    # ==========================================
    else:
        dane, min_s, max_s = przetworz_grafike_cached(st.session_state.html_cache, wybrana_g,
                                                      tuple(st.session_state.grupy))
        if min_s <= max_s:
            dni = ["PON", "WT", "ŚR", "CZW", "PT"]
            rows_count = max_s - min_s + 1
            css = STYLE_CSS.replace("VAR_ROWS", str(rows_count)).replace("VAR_COLS", "5")
            st.markdown(css, unsafe_allow_html=True)

            st.subheader(f"Plan dla {wybrana_g}")

            html = '<div class="schedule-grid">'
            html += '<div class="grid-cell header-cell">Czas</div>'
            for d in dni: html += f'<div class="grid-cell header-cell">{d}</div>'

            for s in range(min_s, max_s + 1):
                row = s - min_s + 2
                if (s * 5) % 60 == 0:
                    h = 7 + (s * 5 // 60)
                    html += f'<div class="grid-cell time-cell" style="grid-row: {row} / span 12;">{h:02}:00</div>'
                for d_idx in range(len(dni)):
                    if (s - min_s) % 6 == 0:
                        html += f'<div class="grid-cell" style="grid-column: {d_idx + 2}; grid-row: {row} / span 6;"></div>'

            for d_idx, d_name in enumerate(dni):
                col = d_idx + 2
                if d_name in dane:
                    for start_slot, info in dane[d_name].items():
                        start_date_obj = datetime.strptime(info["data_start"], "%Y-%m-%d").date() if info.get(
                            "data_start") else None

                        if czy_zajecia_w_tygodniu(wybrana_data, start_date_obj, info.get("tygodnie", 1)):
                            r_start = start_slot - min_s + 2
                            tooltip = f"{info['przedmiot']} | {info['godziny']} | Sala: {info['sala']}"
                            if info.get("prowadzacy"): tooltip += f" | {info['prowadzacy']}"

                            html += f'<div class="lesson-block" style="grid-column: {col}; grid-row: {r_start} / span {info["height"]};" title="{tooltip}">'
                            html += f'<div class="lesson-name">{info["przedmiot"]}</div>'
                            html += f'<div class="lesson-info">{info["godziny"]}</div>'

                            if info["height"] > 9:
                                html += f'<div class="lesson-info">Sala: {info["sala"]}</div>'
                                if info.get(
                                    "prowadzacy"): html += f'<div class="lesson-teacher">{info["prowadzacy"]}</div>'
                            html += '</div>'

            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)