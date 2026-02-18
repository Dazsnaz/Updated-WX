import streamlit as st
import folium
from streamlit_folium import st_folium
from fr24sdk.client import Client 
from avwx import Metar, Taf
import math
import re
from datetime import datetime, timedelta, timezone

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. STABLE v29.2 CSS (NAVY / WHITE / RED)
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; border-radius: 8px; margin-bottom: 20px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; border-right: 3px solid #d6001a; min-width: 350px !important; }
    .stMetric { background-color: #001a33; border-left: 5px solid #d6001a; padding: 10px; }
    .section-header { color: #ffffff !important; background-color: #002366; padding: 10px; border-left: 10px solid #d6001a; font-weight: bold; font-size: 1.2rem; margin-top: 20px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 3. LIVE PRODUCTION TOKEN
LIVE_TOKEN = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"

# 4. AIRPORT DATABASE
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer"},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer"},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer"},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer"},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer"},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer"},
}

# 5. UTILITIES
def calculate_xwind(wind_dir, wind_spd, rwy_hdg):
    if not all([wind_dir, wind_spd, rwy_hdg]): return 0
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

# 6. DATA ENGINES
@st.cache_data(ttl=60)
def fetch_live_fleet():
    fleet = []
    try:
        with Client(api_token=LIVE_TOKEN) as client:
            bounds = "71.0,30.0,-20.0,35.0" 
            flights = client.live.flight_positions.get_light(bounds=bounds)
            if flights and flights.data:
                for f in flights.data:
                    call = (getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "UKNOWN").upper()
                    f_tag = "OTHER"
                    if "CFE" in call: f_tag = "CFE"
                    elif "EFW" in call: f_tag = "EFW"
                    elif "BAW" in call or "SHT" in call: f_tag = "BA_GROUP"
                    
                    if f_tag != "OTHER":
                        fleet.append({"callsign": call, "lat": f.lat, "lon": f.lon, "type": f_tag})
        return fleet
    except: return []

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

# 7. EXECUTION
all_fleet = fetch_live_fleet()
wx_data = fetch_weather(base_airports)

# 8. RENDER HUD
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.26 | FULL OPS</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH ALL"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    # Metrics
    cfe_active = [p for p in all_fleet if p['type'] == "CFE"]
    efw_active = [p for p in all_fleet if p['type'] == "EFW"]
    ba_active = [p for p in all_fleet if p['type'] == "BA_GROUP"]
    
    st.metric("Cityflyer (CFE)", len(cfe_active))
    st.metric("Euroflyer (EFW)", len(efw_active))
    st.metric("BA Mainline/SHT", len(ba_active))
    
    # Watchlist
    if all_fleet:
        st.markdown('<div class="section-header">📋 ACTIVE WATCHLIST</div>', unsafe_allow_html=True)
        for p in all_fleet:
            st.code(f"{p['type']}: {p['callsign']}")
    
    st.markdown("---")
    xw_limit = st.slider("X-WIND ALERT LIMIT (KT)", 15, 35, 25)

# 9. MAP RENDER
m = folium.Map(location=[52.5, 0.0], zoom_start=5, tiles="CartoDB dark_matter")

# Add Airports with Weather Status
for iata, info in base_airports.items():
    d = wx_data.get(iata)
    color = "#008000" # Green
    if d:
        xw = calculate_xwind(d['w_dir'], max(d['w_spd'], d['w_gst']), info['rwy'])
        if xw >= xw_limit: color = "#d6001a" # Red Alert
        
        folium.CircleMarker(
            location=[info['lat'], info['lon']], 
            radius=8, color=color, fill=True, 
            popup=f"<b>{iata}</b><br>XW: {xw}KT<br>{d['raw']}"
        ).add_to(m)

# Add Fleet Icons
for p in all_fleet:
    icon_color = "blue" if p['type'] == "CFE" else ("red" if p['type'] == "EFW" else "cadetblue")
    folium.Marker(
        location=[p['lat'], p['lon']],
        icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
        tooltip=p['callsign']
    ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_26_full_ops")
