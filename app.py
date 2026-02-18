import streamlit as st
import folium
from streamlit_folium import st_folium
from fr24sdk.client import Client 
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. STABLE v29.2 CSS (NAVY & RED THEME)
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; border-radius: 8px; margin-bottom: 20px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; border-right: 3px solid #d6001a; min-width: 300px !important; }
    [data-testid="stSidebar"] label p { font-weight: bold; font-size: 1.1rem; }
    .stMetric { background-color: #003366; padding: 15px; border-radius: 5px; border-left: 5px solid #d6001a; }
    </style>
    """, unsafe_allow_html=True)

# 3. LIVE PRODUCTION TOKEN
# Verified Live API Key
LIVE_TOKEN = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"

# 4. DATA ENGINE
@st.cache_data(ttl=60)
def fetch_live_fleet():
    fleet = []
    try:
        with Client(api_token=LIVE_TOKEN) as client:
            # European Bounding Box for CFE/EFW Operations
            bounds = "72.0,32.0,-18.0,40.0" 
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                for f in flights.data:
                    call = getattr(f, 'callsign', "") or getattr(f, 'flight', "") or ""
                    
                    # Target CFE (Cityflyer) and EFW (Euroflyer)
                    f_type = None
                    if call.upper().startswith("CFE"): f_type = "CFE"
                    elif call.upper().startswith("EFW"): f_type = "EFW"
                    
                    if f_type:
                        fleet.append({
                            "callsign": call, 
                            "lat": getattr(f, 'lat', 0), 
                            "lon": getattr(f, 'lon', 0), 
                            "type": f_type
                        })
        return fleet
    except Exception:
        return []

# 5. RENDER HUD
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.22 | LIVE OPS</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

# Sidebar Stats
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH FLEET"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    live_data = fetch_live_fleet()
    cfe_fleet = [p for p in live_data if p['type'] == "CFE"]
    efw_fleet = [p for p in live_data if p['type'] == "EFW"]
    
    st.metric("Cityflyer (CFE) Airborne", len(cfe_fleet))
    st.metric("Euroflyer (EFW) Airborne", len(efw_fleet))
    
    st.markdown("---")
    st.caption(f"Last Update: {datetime.now().strftime('%H:%M:%S')}Z")
    st.caption("Data Source: FlightRadar24 Live API")

# Map Visualization
# Centered on LCY/LGW area initially
m = folium.Map(location=[51.5, 0.0], zoom_start=6, tiles="CartoDB dark_matter")

if live_data:
    for p in live_data:
        # CFE is BA Blue, EFW is Red
        icon_color = "blue" if p['type'] == "CFE" else "red"
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
            tooltip=f"<b>{p['callsign']}</b>"
        ).add_to(m)
else:
    st.info("No CFE or EFW aircraft detected in the European zone at this time.")

st_folium(m, width=1200, height=800, key="v35_22_live_map")
