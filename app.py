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
    [data-testid="stSidebar"] .stButton > button { background-color: #005a9c !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }

    div[data-testid="stSelectbox"] div[data-baseweb="select"] { background-color: white !important; }
    div[data-testid="stSelectbox"] * { color: #002366 !important; font-weight: 800 !important; }

    .stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }

    .reason-box { background-color: #ffffff !important; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .reason-box * { color: #002366 !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_xwind(wind_dir, wind_spd, rwy_hdg):
    if not all([wind_dir, wind_spd, rwy_hdg]): return 0
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

# 4. DATA FETCH (v35.17 - All-Traffic Logic)
@st.cache_data(ttl=60)
def get_fleet_v35_17(search_query):
    if not FR_AVAILABLE: return [], 0, 0, 0, []
    try:
        api_token = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"
        fleet_list, raw_calls = [], []
        
        with Client(api_token=api_token) as client:
            # Use the box that we know returns 20 flights
            bounds = "71.0,35.0,-15.0,25.0" 
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                for f in flights.data:
                    # Capture identifying info
                    call = getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "N/A"
                    if call != "N/A" and len(raw_calls) < 5: raw_calls.append(call)
                    
                    # Tagging logic
                    f_type = "OTHER"
                    if "CFE" in call.upper(): f_type = "CFE"
                    elif "EFW" in call.upper(): f_type = "EFW"
                    elif search_query and len(search_query) > 1 and search_query.upper() in call.upper():
                        f_type = "SEARCH"
                    
                    # V35.17 CHANGE: Add EVERY flight to the list regardless of type
                    fleet_list.append({
                        "callsign": call, 
                        "lat": getattr(f, 'lat', 0), 
                        "lon": getattr(f, 'lon', 0), 
                        "type": f_type
                    })
                        
        cfe = [p for p in fleet_list if p['type'] == "CFE"]
        efw = [p for p in fleet_list if p['type'] == "EFW"]
        return fleet_list, len(cfe), len(efw), len(fleet_list), raw_calls
    except Exception:
        return [], 0, 0, 0, []

# 5. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    st.markdown("🔍 **QUICK SEARCH**")
    search_input = st.text_input("Highlight Callsign (e.g. ELG):", value="")
    
    active_fleet, cfe_n, efw_n, total_n, probe = get_fleet_v35_17(search_input)
    
    st.markdown(f"✈️ **CFE Airborne:** {cfe_n}")
    st.markdown(f"✈️ **EFW Airborne:** {efw_n}")
    st.caption(f"Sandbox Feed: {total_n} total flights")
    
    if probe:
        st.write("Current Sandbox IDs:")
        for p in probe: st.code(p)
    
    st.markdown("---")
    show_all = st.checkbox("Show Non-Fleet Traffic", value=True)

# 6. RENDER MAP
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.17</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")

# Add Fleet & Search Markers
if active_fleet:
    for p in active_fleet:
        # Hide "OTHER" only if the checkbox is unchecked
        if p['type'] == "OTHER" and not show_all: continue
        
        # Color Logic
        icon_color = "gray"
        if p['type'] == "CFE": icon_color = "blue"
        elif p['type'] == "EFW": icon_color = "red"
        elif p['type'] == "SEARCH": icon_color = "orange"
        
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
            tooltip=f"Callsign: {p['callsign']}"
        ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_17_map")
