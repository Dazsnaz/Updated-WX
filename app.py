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

# 2. STABLE v29.2 CSS (LOCKED)
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 320px !important; border-right: 3px solid #d6001a; }
    [data-testid="stSidebar"] label p { color: #ffffff !important; font-weight: bold; }
    .stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; border: 1px solid white !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. DATA FETCH (v35.20 - Hardcoded New Token)
@st.cache_data(ttl=60)
def get_fleet_v3520():
    if not FR_AVAILABLE: return [], 0, 0, 0, []
    try:
        # THE NEW TOKEN
        api_token = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"
        fleet_list, raw_calls = [], []
        
        with Client(api_token=api_token) as client:
            # European Bounding Box
            bounds = "71.0,34.0,-15.0,35.0" 
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                for f in flights.data:
                    # Capture Callsign
                    call = getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "N/A"
                    if call != "N/A" and len(raw_calls) < 5: raw_calls.append(call)
                    
                    # Filtering Logic
                    f_type = "OTHER"
                    if "CFE" in call.upper(): f_type = "CFE"
                    elif "EFW" in call.upper(): f_type = "EFW"
                    elif "BAW" in call.upper() or "SHT" in call.upper(): f_type = "BA_MAIN"
                    
                    fleet_list.append({
                        "callsign": call, 
                        "lat": getattr(f, 'lat', 0), 
                        "lon": getattr(f, 'lon', 0), 
                        "type": f_type
                    })
                        
        cfe = [p for p in fleet_list if p['type'] == "CFE"]
        efw = [p for p in fleet_list if p['type'] == "EFW"]
        return fleet_list, len(cfe), len(efw), len(fleet_list), raw_calls
    except Exception as e:
        return [], 0, 0, 0, [str(e)[:40]]

# 4. SIDEBAR
active_fleet, cfe_n, efw_n, total_n, probe = get_fleet_v3520()

with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 FORCE REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    st.markdown("🛰️ **TOKEN STATUS: ACTIVE**")
    st.caption("Using Token: 019c7003...8666e1")
    
    st.markdown("---")
    st.metric("Cityflyer (CFE)", cfe_n)
    st.metric("Euroflyer (EFW)", efw_n)
    
    if probe:
        st.markdown("📋 **LIVE DATA PROBE**")
        for p in probe: st.code(p)
    
    st.markdown("---")
    filter_ba = st.checkbox("Show Only BA Group", value=False)

# 5. RENDER MAP
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.20 | TOKEN VERIFIED</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[51.5, 0.0], zoom_start=5, tiles="CartoDB dark_matter")

if active_fleet:
    for p in active_fleet:
        if filter_ba and p['type'] == "OTHER": continue
            
        icon_color = "gray" # Default (Others)
        if p['type'] == "CFE": icon_color = "blue"
        elif p['type'] == "EFW": icon_color = "red"
        elif p['type'] == "BA_MAIN": icon_color = "cadetblue" # Mainline BA
        
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
            tooltip=f"{p['callsign']}"
        ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_20_token_map")
