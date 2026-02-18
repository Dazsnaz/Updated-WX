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

# 2. STABLE v29.2 CSS RESTORATION (LOCKED)
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
    [data-testid="stSidebar"] .stButton > button { background-color: #005a9c !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }

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
    if not all([wind_dir, wind_spd, rwy_hdg]): return 0
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

# 4. MASTER DATABASE (STABLE v29.2)
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer"},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer"},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer"},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer"},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer"},
}

# 5. DATA FETCH (Official SDK + Debug Search)
@st.cache_data(ttl=60)
def get_fleet_with_search(search_query):
    if not FR_AVAILABLE: return [], 0, 0, 0, []
    try:
        api_token = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"
        fleet_list, raw_calls = [], []
        
        with Client(api_token=api_token) as client:
            bounds = "71.0,35.0,-15.0,25.0" # UK & Europe Box
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                for f in flights.data:
                    call = getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "N/A"
                    if call != "N/A" and len(raw_calls) < 5: raw_calls.append(call)
                    
                    # Logic: Identify CFE, EFW, or anything matching the user search
                    f_type = "OTHER"
                    if "CFE" in call.upper(): f_type = "CFE"
                    elif "EFW" in call.upper(): f_type = "EFW"
                    elif search_query and search_query.upper() in call.upper(): f_type = "SEARCH"
                    
                    if f_type != "OTHER":
                        fleet_list.append({
                            "callsign": call, "lat": f.lat, "lon": f.lon, "type": f_type
                        })
                        
        cfe = [p for p in fleet_list if p['type'] == "CFE"]
        efw = [p for p in fleet_list if p['type'] == "EFW"]
        return fleet_list, len(cfe), len(efw), len(flights.data), raw_calls
    except:
        return [], 0, 0, 0, []

# 6. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    st.markdown("🔍 **FLEET SEARCH**")
    search_input = st.text_input("Search for Callsign (e.g. PHV):", value="")
    
    active_fleet, cfe_n, efw_n, total_n, probe = get_fleet_with_search(search_input)
    
    st.markdown(f"✈️ **CFE Airborne:** {cfe_n}")
    st.markdown(f"✈️ **EFW Airborne:** {efw_n}")
    st.caption(f"Sandbox Data Feed: {total_n} flights detected")
    
    if probe:
        st.write("First 5 IDs found:")
        for p in probe: st.code(p)
    
    st.markdown("---")
    show_fleet = st.checkbox("Show Targeted Fleet", value=True)
    xw_limit = st.slider("X-WIND LIMIT (KT)", 15, 35, 25)

# 7. WEATHER & MAP RENDER
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.16</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")

# Add Stations (Stable v29.2 Style)
for iata, info in base_airports.items():
    folium.CircleMarker(location=[info['lat'], info['lon']], radius=7, color="#008000", fill=True, popup=iata).add_to(m)

# Add Fleet Markers (CFE/EFW/Search)
if show_fleet and active_fleet:
    for p in active_fleet:
        icon_color = "blue" if p['type'] == "CFE" else ("red" if p['type'] == "EFW" else "orange")
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
            tooltip=f"{p['callsign']}"
        ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_16_map")
