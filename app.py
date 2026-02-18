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
    .stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; border: 1px solid white !important; }
    .reason-box { background-color: #ffffff !important; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; }
    .reason-box * { color: #002366 !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. MASTER DATABASE & UTILS
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer"},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer"},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer"},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer"},
}

def calculate_xwind(wind_dir, wind_spd, rwy_hdg):
    if not all([wind_dir, wind_spd, rwy_hdg]): return 0
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

# 4. ENHANCED FLEET FETCH (v35.10 Visibility Patch)
@st.cache_data(ttl=60)
def get_official_fleet():
    if not FR_AVAILABLE: return [], 0, 0, 0
    try:
        api_token = "019c6fb5-bd21-725e-a31e-f9814df70712|CYYoXrBCOBJGJuwfTFq28JBhypNfIOC729Mke8bza542008f"
        fleet_list = []
        with Client(api_token=api_token) as client:
            # Expanded Bounds (UK & Europe)
            bounds = "75.0,30.0,-30.0,45.0"
            flights = client.live.flight_positions.get_light(bounds=bounds)
            if not flights or not flights.data: return [], 0, 0, 0
            
            raw_total = len(flights.data)
            for f in flights.data:
                # Try multiple attributes for callsign identification
                call = getattr(f, 'callsign', None) or getattr(f, 'flight', None) or ""
                
                # Filter for CFE, EFW and Mainline BAW/SHT for testing visibility
                if any(call.startswith(prefix) for prefix in ["CFE", "EFW", "BAW", "SHT"]):
                    fleet_list.append({
                        "callsign": call if call else "UNTITLED",
                        "lat": f.latitude, "lon": f.longitude,
                        "type": "EFW" if call.startswith("EFW") else ("CFE" if call.startswith("CFE") else "BAW")
                    })
        
        cfe = [p for p in fleet_list if p['type'] == "CFE"]
        efw = [p for p in fleet_list if p['type'] == "EFW"]
        return fleet_list, len(cfe), len(efw), raw_total
    except:
        return [], 0, 0, 0

active_fleet, cfe_n, efw_n, raw_api_n = get_official_fleet()

# 5. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    st.markdown(f"✈️ **CFE Airborne:** {cfe_n}")
    st.markdown(f"✈️ **EFW Airborne:** {efw_n}")
    st.caption(f"API Zone Traffic: {raw_api_n} flights")
    show_fleet = st.checkbox("Show Aircraft on Map", value=True)
    st.markdown("---")
    show_cf = st.checkbox("Cityflyer Stations", value=True)
    show_ef = st.checkbox("Euroflyer Stations", value=True)
    xw_limit = st.slider("X-WIND LIMIT (KT)", 15, 35, 25)

# 6. WEATHER LOGIC (Simplified for v35.10)
@st.cache_data(ttl=1800)
def fetch_wx(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update()
            res[iata] = {"raw_m": m.raw, "w_dir": getattr(m.data.wind_direction, 'value', 0), "w_spd": getattr(m.data.wind_speed, 'value', 0), "w_gst": getattr(m.data.wind_gust, 'value', 0)}
        except: pass
    return res

weather_data = fetch_wx(base_airports)

# 7. RENDER MAP
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.10</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[52.0, 0.0], zoom_start=5, tiles="CartoDB dark_matter")

# Station Markers
for iata, info in base_airports.items():
    if not ((info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)): continue
    d = weather_data.get(iata)
    if d:
        xw = calculate_xwind(d['w_dir'], max(d['w_spd'], d['w_gst']), info['rwy'])
        color = "#d6001a" if xw >= xw_limit else "#008000"
        folium.CircleMarker(location=[info['lat'], info['lon']], radius=7, color=color, fill=True, popup=f"{iata}: {xw}KT XW").add_to(m)

# Fleet Markers (Including BAW/SHT for Visibility Testing)
if show_fleet and active_fleet:
    for p in active_fleet:
        icon_color = "red" if p['type'] == "EFW" else ("blue" if p['type'] == "CFE" else "gray")
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
            tooltip=f"{p['callsign']}"
        ).add_to(m)

st_folium(m, width=1200, height=800, key="fr24_vis_v3510")
