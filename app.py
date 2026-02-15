import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
import pandas as pd
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. HUD STYLING
st.markdown("""
    <style>
    .section-header { color: #002366 !important; font-weight: bold; font-size: 1.5rem; margin-top: 20px; border-bottom: 2px solid #d6001a; padding-bottom: 5px; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    [data-testid="stTextArea"] textarea { color: #002366 !important; background-color: #ffffff !important; font-weight: bold; font-family: 'Courier New', monospace; }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 300px !important; border-right: 2px solid #d6001a; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold !important; }
    div[data-baseweb="input"], div[data-baseweb="select"], input, .stSelectbox div, .stDateInput div {
        background-color: #ffffff !important; color: #002366 !important; font-weight: bold !important;
    }
    .stButton > button { 
        background-color: #005a9c !important; color: white !important; border: 1px solid white !important; 
        width: 100%; text-transform: uppercase; font-size: 0.72rem !important; height: 50px !important; 
    }
    div.stButton > button[kind="primary"] { background-color: #d6001a !important; }
    div.stButton > button[kind="secondary"] { background-color: #eb8f34 !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_xwind(wind_dir, wind_spd, rwy_hdg):
    if wind_dir is None or wind_spd is None or rwy_hdg is None: return 0
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

def bold_hazard(text):
    if not text or text == "N/A": return text
    # Added FZRA, FZDZ, SN, and -SN to bolding logic
    text = re.sub(r'(\b(FG|TSRA|SN|-SN|FZRA|FZDZ|RA|DZ|TS|VIS|CLOUD|FOG|XWIND|WIND)\b)', r'<b>\1</b>', text)
    text = re.sub(r'((BKN|OVC)\d{3})', r'<b>\1</b>', text)
    return text

# 4. MASTER DATABASE
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer", "spec": True},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer", "spec": False},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "RTM": {"icao": "EHRD", "lat": 51.957, "lon": 4.440, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "Cityflyer", "spec": False},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer", "spec": True},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 180, "fleet": "Cityflyer", "spec": True},
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "fleet": "Cityflyer", "spec": False},
    "GVA": {"icao": "LSGG", "lat": 46.237, "lon": 6.109, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "BER": {"icao": "EDDB", "lat": 52.362, "lon": 13.501, "rwy": 250, "fleet": "Cityflyer", "spec": False},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "JER": {"icao": "EGJJ", "lat": 49.208, "lon": -2.195, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "ALC": {"icao": "LEAL", "lat": 38.282, "lon": -0.558, "rwy": 100, "fleet": "Euroflyer", "spec": False},
}

# 5. SIDEBAR & MISSIONS
with st.sidebar:
    st.title("🛠️ MISSION CONTROL")
    uploaded_file = st.file_uploader("Upload report.csv", type="csv")
    selected_date = st.date_input("Select Date", datetime(2026, 2, 12))
    
    station_flights = {}
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file, skiprows=2)
            df.columns = df.columns.str.strip().str.upper()
            df = df.dropna(subset=['DATE', 'FLT'])
            df['DATE_DT'] = pd.to_datetime(df['DATE'], dayfirst=True, errors='coerce').dt.date
            day_flights = df[df['DATE_DT'] == selected_date]
            for _, row in day_flights.iterrows():
                for p in [str(row['DEP']).strip().upper(), str(row['ARR']).strip().upper()]:
                    if p not in station_flights: station_flights[p] = []
                    if row['FLT'] not in station_flights[p]: station_flights[p].append(row['FLT'])
            st.success(f"Linked {len(day_flights)} Flights")
        except: st.error("Schedule Link Error.")

    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)
    if st.button("🔄 REFRESH"): st.cache_data.clear(); st.rerun()

# 6. WEATHER ENGINE
@st.cache_data(ttl=600)
def get_weather(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            res[iata] = {"raw_m": m.raw, "raw_t": t.raw, "status": "online",
                         "vis": m.data.visibility.value if m.data.visibility else 9999,
                         "w_dir": m.data.wind_direction.value if m.data.wind_direction else 0,
                         "w_spd": m.data.wind_speed.value or 0, "w_gst": m.data.wind_gust.value or 0}
        except: res[iata] = {"status": "offline"}
    return res

weather_data = get_weather(base_airports)

# 7. LOGIC & UI
metar_alerts, taf_alerts, map_markers = {}, {}, []
for iata, info in base_airports.items():
    data = weather_data.get(iata)
    if not data or data['status'] == "offline": continue
    
    is_shown = (info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)
    v_lim = 1500 if info['spec'] else 800
    color, m_issues, t_issues = "#008000", [], []
    
    # METAR ALERTS
    raw_m = data['raw_m'].upper()
    xw = calculate_xwind(data['w_dir'], max(data['w_spd'], data['w_gst']), info['rwy'])
    if data['vis'] < v_lim: m_issues.append("VIS")
    if xw >= 25: m_issues.append("XWIND")
    if " SN " in raw_m or " -SN " in raw_m: m_issues.append("SNOW")
    if "FZRA" in raw_m: m_issues.append("FZRA")
    if "FZDZ" in raw_m: m_issues.append("FZDZ")
    
    # TAF ALERTS
    raw_t = data['raw_t'].upper()
    if " SN " in raw_t or " -SN " in raw_t: t_issues.append("SNOW")
    if "FZRA" in raw_t: t_issues.append("FZRA")
    if "FZDZ" in raw_t: t_issues.append("FZDZ")
    if "FG" in raw_t: t_issues.append("FOG")
    if "TS" in raw_t: t_issues.append("TSRA")

    if is_shown:
        if m_issues: color = "#d6001a"; metar_alerts[iata] = {"type": "/".join(m_issues)}
        if t_issues:
            color = "#eb8f34" if color == "#008000" else color
            taf_alerts[iata] = {"type": "/".join(t_issues)}

        flights = ", ".join(station_flights.get(iata, ["No Missions"]))
        popup_html = f"""<div style="width:500px; color:black; font-family:monospace;">
            <b style="font-size:16px;">{iata} STATUS</b><br>
            <div style="border-left:5px solid {color}; padding:5px; background:#f0f0f0;">
            <b>MISSIONS:</b> {flights}<br>
            <b>METAR:</b> {"/".join(m_issues) if m_issues else "GREEN"}<br>
            <b>TAF:</b> {"/".join(t_issues) if t_issues else "NIL"}</div>
            <hr><b>RAW METAR:</b><br>{bold_hazard(data['raw_m'])}<br><br><b>RAW TAF:</b><br>{bold_hazard(data['raw_t'])}</div>"""
        map_markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "popup": popup_html})

# 8. RENDER
st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter")
for mk in map_markers:
    folium.CircleMarker([mk['lat'], mk['lon']], radius=7, color=mk['color'], fill=True, popup=folium.Popup(mk['popup'], max_width=600)).add_to(m)
st_folium(m, width=1200, height=1200)

st.markdown("### 🔴 METAR ALERTS")
if metar_alerts:
    cols = st.columns(5)
    for i, (iata, d) in enumerate(metar_alerts.items()):
        cols[i%5].button(f"{iata}: {d['type']}", type="primary")

st.markdown("### 🟠 TAF ALERTS")
if taf_alerts:
    cols = st.columns(5)
    for i, (iata, d) in enumerate(taf_alerts.items()):
        cols[i%5].button(f"{iata}: {d['type']}", type="secondary")
