import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import math
from avwx import Metar
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. STABLE v29.2 CSS (NAVY & RED)
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { 
        background-color: #002366 !important; color: #ffffff !important; 
        padding: 20px; border-radius: 8px; margin-bottom: 20px; 
        border: 2px solid #d6001a; display: flex; justify-content: space-between;
    }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 350px !important; border-right: 3px solid #d6001a; }
    [data-testid="stSidebar"] label p { color: #ffffff !important; font-weight: bold; }
    .stMetric { background-color: #001a33; border-left: 5px solid #d6001a; padding: 10px; }
    .section-header { color: #ffffff !important; background-color: #002366; padding: 10px; border-left: 10px solid #d6001a; font-weight: bold; font-size: 1.2rem; margin-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

# 3. MASTER DATABASE (Airports & Runway Data)
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer"},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer"},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer"},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer"},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer"},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer"},
}

# 4. UTILITIES
def calculate_xwind(wind_dir, wind_spd, rwy_hdg):
    if not all([wind_dir, wind_spd, rwy_hdg]): return 0
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

# 5. DATA ENGINES
@st.cache_data(ttl=30)
def fetch_live_fleet():
    fleet = []
    try:
        # OpenSky European Box
        url = "https://opensky-network.org/api/states/all?lamin=35.0&lomin=-15.0&lamax=65.0&lomax=20.0"
        r = requests.get(url, timeout=5)
        data = r.json()
        if "states" in data and data["states"]:
            for s in data["states"]:
                call = (s[1] or "").strip().upper()
                f_type = None
                if call.startswith("CFE"): f_type = "CFE"
                elif call.startswith("EFW"): f_type = "EFW"
                
                if f_type:
                    raw_alt = s[7] if s[7] is not None else 0
                    fleet.append({
                        "callsign": call, "lat": s[6], "lon": s[5],
                        "type": f_type, "alt": round(raw_alt * 3.28084)
                    })
    except: pass
    return fleet

@st.cache_data(ttl=1800)
def fetch_weather(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update()
            res[iata] = {
                "raw": m.raw, 
                "w_dir": getattr(m.data.wind_direction, 'value', 0),
                "w_spd": getattr(m.data.wind_speed, 'value', 0),
                "w_gst": getattr(m.data.wind_gust, 'value', 0)
            }
        except: pass
    return res

# 6. EXECUTION
fleet_data = fetch_live_fleet()
weather_data = fetch_weather(base_airports)

# 7. RENDER HEADER
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.34 | INTEGRATED OPS</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

# 8. SIDEBAR CONTROL
with st.sidebar:
    st.title("🛡️ COMMAND HUD")
    if st.button("🔄 REFRESH ALL"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    # Live Counts
    cfe_n = len([p for p in fleet_data if p['type'] == "CFE"])
    efw_n = len([p for p in fleet_data if p['type'] == "EFW"])
    st.metric("Cityflyer (CFE) Airborne", cfe_n)
    st.metric("Euroflyer (EFW) Airborne", efw_n)
    
    st.markdown('<div class="section-header">📋 ACTIVE FLEET</div>', unsafe_allow_html=True)
    for p in fleet_data:
        st.code(f"{p['callsign']} @ {p['alt']}ft")
    
    st.markdown("---")
    xw_limit = st.slider("X-WIND ALERT LIMIT (KT)", 15, 35, 25)

# 9. MAP RENDER
m = folium.Map(location=[52.0, 0.0], zoom_start=5, tiles="CartoDB dark_matter")

# Add Airports with METAR Alert Logic
for iata, info in base_airports.items():
    d = weather_data.get(iata)
    color = "#008000" # Default Green
    popup_text = f"<b>{iata}</b><br>Weather Online"
    
    if d:
        xw = calculate_xwind(d['w_dir'], max(d['w_spd'], d['w_gst']), info['rwy'])
        if xw >= xw_limit: color = "#d6001a" # Red Alert
        popup_text = f"<b>{iata}</b><br>X-WIND: {xw}KT<br><br><code>{d['raw']}</code>"

    folium.CircleMarker(
        location=[info['lat'], info['lon']], 
        radius=8, color=color, fill=True, 
        popup=folium.Popup(popup_text, max_width=300)
    ).add_to(m)

# Add Live Aircraft Icons
for p in fleet_data:
    icon_color = "blue" if p['type'] == "CFE" else "red"
    folium.Marker(
        location=[p['lat'], p['lon']],
        icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
        tooltip=f"{p['callsign']} | {p['alt']}ft"
    ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_34_map")
