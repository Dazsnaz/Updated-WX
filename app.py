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

# 2. STABLE v29.2 CSS
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

# 3. DATA FETCH (v35.18 - Live Production Logic)
@st.cache_data(ttl=60)
def get_production_fleet():
    if not FR_AVAILABLE: return [], 0, 0, 0, []
    try:
        # UPDATED TOKEN: Production/Live Token
        api_token = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"
        fleet_list, raw_calls = [], []
        
        with Client(api_token=api_token) as client:
            # Broad European Bounds for Live Fleet Tracking
            bounds = "72.0,34.0,-16.0,40.0" 
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                for f in flights.data:
                    call = getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "N/A"
                    if call != "N/A" and len(raw_calls) < 5: raw_calls.append(call)
                    
                    # PRIORITY IDENTIFICATION: Cityflyer & Euroflyer
                    f_type = "OTHER"
                    if call.upper().startswith("CFE"): f_type = "CFE"
                    elif call.upper().startswith("EFW"): f_type = "EFW"
                    elif call.upper().startswith("BAW"): f_type = "BAW" # Mainline for context
                    
                    fleet_list.append({
                        "callsign": call, 
                        "lat": getattr(f, 'lat', 0), 
                        "lon": getattr(f, 'lon', 0), 
                        "type": f_type
                    })
                        
        cfe = [p for p in fleet_list if p['type'] == "CFE"]
        efw = [p for p in fleet_list if p['type'] == "EFW"]
        return fleet_list, len(cfe), len(efw), len(fleet_list), raw_calls
    except:
        return [], 0, 0, 0, []

# 4. SIDEBAR
active_fleet, cfe_n, efw_n, total_n, probe = get_production_fleet()

with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH HUD"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    st.markdown("✈️ **LIVE FLEET STATUS**")
    st.write(f"Cityflyer (CFE): **{cfe_n}**")
    st.write(f"Euroflyer (EFW): **{efw_n}**")
    st.caption(f"Total Traffic in Zone: {total_n}")
    
    st.markdown("---")
    show_only_ba = st.checkbox("Filter: BA Group Only", value=False)
    st.markdown("---")
    st.caption("Probe (First 5):")
    for p in probe: st.code(p)

# 5. RENDER MAP
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.18 | LIVE PRODUCTION</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")

if active_fleet:
    for p in active_fleet:
        # If "Filter" is ON, skip non-BA aircraft
        if show_only_ba and p['type'] == "OTHER": continue
        
        # COLOR KEY: CFE=Blue, EFW=Red, BAW=Cyan, Others=Gray
        icon_color = "gray"
        if p['type'] == "CFE": icon_color = "blue"
        elif p['type'] == "EFW": icon_color = "red"
        elif p['type'] == "BAW": icon_color = "cadetblue"
        
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
            tooltip=f"{p['callsign']}"
        ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_18_prod_map")
