import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
from datetime import datetime, timedelta, timezone

# --- OFFICIAL FR24 SDK INTEGRATION ---
try:
    from fr24sdk.client import Client
    FR_AVAILABLE = True
except ImportError:
    FR_AVAILABLE = False

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. STABLE v29.2 CSS RESTORATION
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { 
        background-color: #002366 !important; color: #ffffff !important; 
        padding: 20px; border-radius: 8px; margin-bottom: 20px; 
        border: 2px solid #d6001a; display: flex; justify-content: space-between;
    }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 320px !important; border-right: 3px solid #d6001a; }
    [data-testid="stSidebar"] label p { color: #ffffff !important; font-weight: bold; }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] { background-color: white !important; }
    div[data-testid="stSelectbox"] * { color: #002366 !important; font-weight: 800 !important; }
    .stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }
    .stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }
    .reason-box { background-color: #ffffff !important; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .reason-box * { color: #002366 !important; }
    .section-header { color: #ffffff !important; background-color: #002366; padding: 10px; border-left: 10px solid #d6001a; font-weight: bold; font-size: 1.5rem; margin-top: 30px; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_xwind(wind_dir, wind_spd, rwy_hdg):
    if wind_dir is None or wind_spd is None or rwy_hdg is None: return 0
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

# 4. MASTER DATABASE
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer", "spec": True},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer", "spec": False},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "Cityflyer", "spec": False},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer", "spec": True},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer", "spec": True},
    "FNC": {"icao": "LPMA", "lat": 32.694, "lon": -16.774, "rwy": 50, "fleet": "Euroflyer", "spec": True},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "Euroflyer", "spec": False},
}

if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

# 6. UPDATED FLEET FETCH (v35.9 Fix)
@st.cache_data(ttl=60)
def get_official_fleet():
    if not FR_AVAILABLE: return [], 0, 0, 0
    try:
        api_token = "019c6fb5-bd21-725e-a31e-f9814df70712|CYYoXrBCOBJGJuwfTFq28JBhypNfIOC729Mke8bza542008f"
        fleet_list = []
        raw_count = 0
        
        with Client(api_token=api_token) as client:
            # Expanded Bounds covering UK and Europe: North, South, West, East
            bounds = "75.0,30.0,-30.0,45.0" 
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                raw_count = len(flights.data)
                for f in flights.data:
                    call = getattr(f, 'callsign', "") or ""
                    if call.startswith("CFE") or call.startswith("EFW"):
                        fleet_list.append({
                            "callsign": call,
                            "lat": f.latitude,
                            "lon": f.longitude,
                            "dest": getattr(f, 'destination', "???"),
                            "type": "EFW" if call.startswith("EFW") else "CFE"
                        })
        
        cfe = [p for p in fleet_list if p['type'] == "CFE"]
        efw = [p for p in fleet_list if p['type'] == "EFW"]
        return fleet_list, len(cfe), len(efw), raw_count
    except Exception as e:
        return [], 0, 0, 0

# 7. SIDEBAR DATA
active_fleet, cfe_n, efw_n, raw_api_n = get_official_fleet()

with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    st.markdown(f"✈️ **CFE Airborne:** {cfe_n}")
    st.markdown(f"✈️ **EFW Airborne:** {efw_n}")
    if raw_api_n > 0:
        st.caption(f"API Debug: Detected {raw_api_n} total flights in zone.")
    show_fleet = st.checkbox("Show Fleet on Map", value=True)
    st.markdown("---")
    show_cf = st.checkbox("Cityflyer Stations", value=True)
    show_ef = st.checkbox("Euroflyer Stations", value=True)
    xw_limit = st.slider("X-WIND LIMIT (KT)", 15, 35, 25)

# 8. WEATHER (LOCKED v29.2 Logic)
@st.cache_data(ttl=1800)
def fetch_wx(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            res[iata] = {"raw_m": m.raw, "w_dir": getattr(m.data.wind_direction, 'value', 0), "w_spd": getattr(m.data.wind_speed, 'value', 0), "w_gst": getattr(m.data.wind_gust, 'value', 0), "status": "online"}
        except: res[iata] = {"status": "offline"}
    return res

weather_data = fetch_wx(base_airports)

# 10. RENDER
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.9</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter")

# Stations Marker Logic
metar_alerts = {}
for iata, info in base_airports.items():
    d = weather_data.get(iata)
    if not d or d['status'] == "offline": continue
    if not ((info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)): continue
    
    xw = calculate_xwind(d['w_dir'], max(d['w_spd'], d['w_gst']), info['rwy'])
    color = "#d6001a" if xw >= xw_limit else "#008000"
    if color == "#d6001a": metar_alerts[iata] = f"{xw}KT XW"

    folium.CircleMarker(location=[info['lat'], info['lon']], radius=7, color=color, fill=True, popup=f"<b>{iata}</b><br>{d['raw_m']}").add_to(m)

# Fleet Marker Logic (Expanded Bounds)
if show_fleet and active_fleet:
    for p in active_fleet:
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color="red" if p['type'] == "EFW" else "blue", icon="plane", prefix="fa"),
            tooltip=f"{p['callsign']} -> {p['dest']}"
        ).add_to(m)

st_folium(m, width=1200, height=800, key="fr24_map_v359")

if metar_alerts:
    st.markdown('<div class="section-header">🔴 Actual Alerts</div>', unsafe_allow_html=True)
    cols = st.columns(5)
    for i, (iata, msg) in enumerate(metar_alerts.items()):
        with cols[i % 5]:
            st.button(f"{iata}: {msg}", key=f"m_{iata}", type="primary")
