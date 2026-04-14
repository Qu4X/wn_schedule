import streamlit as st
import html
from datetime import datetime, timedelta, time
from scrapper import pobierz_liste_planow, pobierz_surowy_plan, przetworz_plan_na_grafike, przetworz_plan_wszystkie, \
    generuj_ics

st.set_page_config(page_title="Plan zajęć WN", page_icon="⚓", layout="wide", initial_sidebar_state="expanded")

STYLE_CSS = """
<style>
    .block-container { padding-top: 2rem !important; }

    .schedule-grid {
        display: grid;
        grid-template-columns: 65px repeat(var(--grid-cols, 1), 1fr);
        grid-template-rows: 40px repeat(var(--grid-rows, 1), 4px);
        gap: 0 !important; 
        background-color: var(--background-color) !important;
        /* Wyraźna ramka zewnętrzna całości */
        box-shadow: 0 0 0 2px var(--secondary-background-color);
        color: var(--text-color) !important;
    }

    /* Wszystkie komórki siatki */
    .grid-cell { 
        border-right: 1px solid rgba(128, 128, 128, 0.2) !important; 
        border-bottom: 1px solid rgba(128, 128, 128, 0.2) !important; 
    }

    /* Nagłówki dni (PON, WT...) */
    .header-cell { 
        background-color: var(--secondary-background-color) !important;
        color: var(--text-color) !important; 
        font-weight: bold !important; 
        display: flex; align-items: center; justify-content: center; 
        /* KLUCZOWA LINIA POZIOMA */
        border-bottom: 2px solid rgba(128, 128, 128, 0.5) !important;
        border-right: 1px solid rgba(128, 128, 128, 0.2) !important;
        z-index: 20;
    }

    /* Kolumna z godzinami */
    .time-cell { 
        grid-column: 1; 
        display: flex; align-items: top; justify-content: flex-end; 
        padding-right: 8px; 
        color: var(--text-color) !important; 
        font-size: 0.85rem !important; 
        font-weight: 600 !important; 
        background-color: var(--secondary-background-color) !important;
        /* KLUCZOWA LINIA PIONOWA */
        border-right: 2px solid rgba(128, 128, 128, 0.5) !important;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2) !important;
        z-index: 15;
    }

    /* Kafelki zajęć */
    .lesson-block {
        background-color: #1a4f8a !important; 
        color: white !important; 
        border: 1px solid #003366 !important; 
        border-radius: 4px !important;
        padding: 4px; 
        display: flex; flex-direction: column; justify-content: flex-start;
        z-index: 10; 
        line-height: 1.1; 
        overflow: hidden;
        margin: 1px !important;
    }

.lesson-name { 
        font-size: 0.8rem !important; 
        font-weight: bold !important; 
        margin-bottom: 2px !important; 
        color: white !important; 
    }
    .lesson-info { 
        font-size: 0.7rem !important; 
        opacity: 0.9 !important; 
        margin-bottom: 1px !important; 
        color: white !important; 
    }
    .lesson-teacher { 
        font-size: 0.65rem !important; /* Wymuszamy mały rozmiar */
        margin-top: auto !important; 
        font-style: italic !important; 
        opacity: 0.8 !important; 
        padding-top: 3px !important; 
        border-top: 1px solid rgba(255,255,255,0.2) !important; 
        color: white !important;
        line-height: 1.0 !important;
    }
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
    poniedzialek_start = data_start_zajec - timedelta(days=data_start_zajec.weekday())
    poniedzialek_wybrana = data_wybrana - timedelta(days=data_wybrana.weekday())
    dni_diff = (poniedzialek_wybrana - poniedzialek_start).days
    tydzien_diff = dni_diff // 7
    return 0 <= tydzien_diff < liczba_tygodni


# ==========================================
# INICJALIZACJA ZMIENNYCH
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

if st.session_state.plan_id is not None and not st.session_state.grupy:
    st.session_state.html_cache, st.session_state.grupy = pobierz_plan_cached(st.session_state.plan_id)

st.markdown(STYLE_CSS, unsafe_allow_html=True)

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

        lista_opcji = st.session_state.grupy + ["WSZYSTKIE GRUPY"]
        wybrana_g = st.selectbox("Wybierz grupę:", lista_opcji)

        st.write("---")
        st.header("Kalendarz")
        wybrana_data = st.date_input("Pokaż tydzień dla daty:", datetime.now())

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
            cols_count = len(st.session_state.grupy)

            st.subheader("Plan dla wszystkich grup")
            tabs = st.tabs(dni)

            for tab_idx, d_name in enumerate(dni):
                with tabs[tab_idx]:
                    zajecia_w_tym_tygodniu = False
                    html_str = f'<div class="schedule-grid" style="--grid-rows: {rows_count}; --grid-cols: {cols_count};">'
                    html_str += '<div class="grid-cell header-cell">Czas</div>'

                    for g in st.session_state.grupy:
                        safe_g = html.escape(g)
                        html_str += f'<div class="grid-cell header-cell" title="{safe_g}">{safe_g[:5]}</div>'

                    for s in range(min_s, max_s + 1):
                        row = s - min_s + 2
                        if (s * 5) % 60 == 0:
                            h = 7 + (s * 5 // 60)
                            html_str += f'<div class="grid-cell time-cell" style="grid-row: {row} / span 12;">{h:02}:00</div>'
                        for g_idx in range(len(st.session_state.grupy)):
                            if (s - min_s) % 6 == 0:
                                html_str += f'<div class="grid-cell" style="grid-column: {g_idx + 2}; grid-row: {row} / span 6;"></div>'

                    if d_name in dane_all:
                        for start_slot, slots_data in dane_all[d_name].items():
                            r_start = start_slot - min_s + 2
                            for col_start, info in slots_data.items():
                                start_date_obj = datetime.strptime(info["data_start"], "%Y-%m-%d").date() if info.get(
                                    "data_start") else None

                                if czy_zajecia_w_tygodniu(wybrana_data, start_date_obj, info.get("tygodnie", 1)):
                                    zajecia_w_tym_tygodniu = True
                                    col = col_start + 2
                                    width = min(info["colspan"], len(st.session_state.grupy) - col_start)

                                    safe_przed = html.escape(info['przedmiot'])
                                    safe_godz = html.escape(info['godziny'])
                                    safe_sala = html.escape(info['sala'])
                                    safe_prow = html.escape(info.get('prowadzacy', ''))

                                    tooltip = html.escape(
                                        f"{info['przedmiot']} | {info['godziny']} | {info['sala']}")
                                    if safe_prow: tooltip += html.escape(f" | {info['prowadzacy']}")

                                    html_str += f'<div class="lesson-block" style="grid-column: {col} / span {width}; grid-row: {r_start} / span {info["height"]};" title="{tooltip}">'
                                    html_str += f'<div class="lesson-name">{safe_przed}</div>'
                                    html_str += f'<div class="lesson-info">{safe_godz}</div>'
                                    if info["height"] > 9:
                                        html_str += f'<div class="lesson-info">Sala: {safe_sala}</div>'
                                        if safe_prow:
                                            html_str += f'<div class="lesson-teacher">{safe_prow}</div>'
                                    html_str += '</div>'

                    html_str += '</div>'

                    if not zajecia_w_tym_tygodniu:
                        st.info("Brak zajęć w tym tygodniu")
                    else:
                        st.markdown(html_str, unsafe_allow_html=True)

    # ==========================================
    # RYSOWANIE GRAFIKI - WIDOK POJEDYNCZEJ GRUPY
    # ==========================================
    else:
        dane, min_s, max_s = przetworz_grafike_cached(st.session_state.html_cache, wybrana_g,
                                                      tuple(st.session_state.grupy))
        if min_s <= max_s:
            dni = ["PON", "WT", "ŚR", "CZW", "PT"]
            rows_count = max_s - min_s + 1
            zajecia_w_tym_tygodniu = False

            st.subheader(f"Plan dla {wybrana_g}")

            html_str = f'<div class="schedule-grid" style="--grid-rows: {rows_count}; --grid-cols: 5;">'
            html_str += '<div class="grid-cell header-cell">Czas</div>'
            for d in dni: html_str += f'<div class="grid-cell header-cell">{d}</div>'

            for s in range(min_s, max_s + 1):
                row = s - min_s + 2
                if (s * 5) % 60 == 0:
                    h = 7 + (s * 5 // 60)
                    html_str += f'<div class="grid-cell time-cell" style="grid-row: {row} / span 12;">{h:02}:00</div>'
                for d_idx in range(len(dni)):
                    if (s - min_s) % 6 == 0:
                        html_str += f'<div class="grid-cell" style="grid-column: {d_idx + 2}; grid-row: {row} / span 6;"></div>'

            for d_idx, d_name in enumerate(dni):
                col = d_idx + 2
                if d_name in dane:
                    for start_slot, info in dane[d_name].items():
                        start_date_obj = datetime.strptime(info["data_start"], "%Y-%m-%d").date() if info.get(
                            "data_start") else None

                        if czy_zajecia_w_tygodniu(wybrana_data, start_date_obj, info.get("tygodnie", 1)):
                            zajecia_w_tym_tygodniu = True
                            r_start = start_slot - min_s + 2

                            safe_przed = html.escape(info['przedmiot'])
                            safe_godz = html.escape(info['godziny'])
                            safe_sala = html.escape(info['sala'])
                            safe_prow = html.escape(info.get('prowadzacy', ''))

                            tooltip = html.escape(f"{info['przedmiot']} | {info['godziny']} | Sala: {info['sala']}")
                            if safe_prow: tooltip += html.escape(f" | {info['prowadzacy']}")

                            html_str += f'<div class="lesson-block" style="grid-column: {col}; grid-row: {r_start} / span {info["height"]};" title="{tooltip}">'
                            html_str += f'<div class="lesson-name">{safe_przed}</div>'
                            html_str += f'<div class="lesson-info">{safe_godz}</div>'

                            if info["height"] > 9:
                                html_str += f'<div class="lesson-info">Sala: {safe_sala}</div>'
                                if safe_prow:
                                    html_str += f'<div class="lesson-teacher">{safe_prow}</div>'
                            html_str += '</div>'

            html_str += '</div>'

            if not zajecia_w_tym_tygodniu:
                st.info("Brak zajęć w tym tygodniu")
            else:
                st.markdown(html_str, unsafe_allow_html=True)