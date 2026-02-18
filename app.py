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

# 3. UTILITIES
def calculate_xwind(wind_dir, wind_spd, rwy_hdg):
    if not all([wind_dir, wind_spd, rwy_hdg]): return 0
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

# 4. UPDATED DATA FETCH (v35.13 - New Token & Probe)
@st.cache_data(ttl=60)
def get_fleet_with_probe():
    if not FR_AVAILABLE: return [], 0, 0, 0, []
    try:
        # Using your latest provided token
        api_token = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"
        fleet_list = []
        raw_names = []
        
        with Client(api_token=api_token) as client:
            # Global Bounds to ensure data capture
            bounds = "85.0,-85.0,-180.0,180.0"
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                for f in flights.data:
                    # Capture identifying info
                    call = getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "N/A"
                    if call != "N/A" and len(raw_names) < 5:
                        raw_names.append(call)
                    
                    # Filtering Logic
                    f_type = "OTHER"
                    if "CFE" in call.upper(): f_type = "CFE"
                    elif "EFW" in call.upper(): f_type = "EFW"
                    
                    fleet_list.append({
                        "callsign": call,
                        "lat": f.latitude,
                        "lon": f.longitude,
                        "type": f_type
                    })
                        
        cfe = [p for p in fleet_list if p['type'] == "CFE"]
        efw = [p for p in fleet_list if p['type'] == "EFW"]
        return fleet_list, len(cfe), len(efw), len(fleet_list), raw_names
    except Exception:
        return [], 0, 0, 0, []

active_fleet, cfe_n, efw_n, api_total, probe_calls = get_fleet_with_probe()

# 5. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH HUD"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    # DATA PROBE DISPLAY
    st.markdown("📡 **API DATA PROBE**")
    if probe_calls:
        st.write("Found Callsigns:")
        for c in probe_calls:
            st.code(c)
    else:
        st.write("No active callsigns found.")
    
    st.markdown("---")
    st.markdown(f"✈️ **CFE Airborne:** {cfe_n}")
    st.markdown(f"✈️ **EFW Airborne:** {efw_n}")
    st.caption(f"Total flights in API packet: {api_total}")
    show_all = st.checkbox("Show All Traffic (Debug)", value=True)
    st.markdown("---")
    show_cf = st.checkbox("Cityflyer Stations", value=True)
    show_ef = st.checkbox("Euroflyer Stations", value=True)

# 6. RENDER MAP
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.13</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[52.0, 0.0], zoom_start=4, tiles="CartoDB dark_matter")

if active_fleet:
    for p in active_fleet:
        if not show_all and p['type'] == "OTHER": continue
        
        icon_color = "blue" if p['type'] == "CFE" else ("red" if p['type'] == "EFW" else "gray")
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
            tooltip=f"{p['callsign']}"
        ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_13_map")
