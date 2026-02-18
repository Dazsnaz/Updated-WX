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

# 4. SANDBOX FLEET FETCH (v35.11 Deep Probe)
@st.cache_data(ttl=60)
def get_sandbox_fleet():
    if not FR_AVAILABLE: return [], 0, 0, 0
    try:
        # Using your Sandbox Access Token
        api_token = "019c4863-6b15-706f-bd15-685c4c23d6fa|HUsANXRxtSCFkmJRJ8zcdeTOkIUEJHyD4byicXD7d8ebf6e2"
        fleet_list = []
        raw_total = 0
        
        with Client(api_token=api_token) as client:
            # Sandbox bounds may be limited; using a standard European window
            bounds = "71.0,34.0,-15.0,35.0"
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                raw_total = len(flights.data)
                for f in flights.data:
                    # Deep probe for callsigns in sandbox data fields
                    call = getattr(f, 'callsign', "") or getattr(f, 'flight', "") or ""
                    
                    # Match CFE (Cityflyer) or EFW (Euroflyer)
                    if "CFE" in call.upper() or "EFW" in call.upper():
                        fleet_list.append({
                            "callsign": call,
                            "lat": f.latitude,
                            "lon": f.longitude,
                            "type": "EFW" if "EFW" in call.upper() else "CFE"
                        })
                    # Fallback: if list is empty, grab BAW to verify visibility
                    elif "BAW" in call.upper():
                        fleet_list.append({
                            "callsign": call,
                            "lat": f.latitude,
                            "lon": f.longitude,
                            "type": "BAW"
                        })
                        
        cfe = [p for p in fleet_list if p['type'] == "CFE"]
        efw = [p for p in fleet_list if p['type'] == "EFW"]
        return fleet_list, len(cfe), len(efw), raw_total
    except Exception as e:
        return [], 0, 0, 0

active_fleet, cfe_n, efw_n, api_total = get_sandbox_fleet()

# 5. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH HUD"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    st.markdown(f"✈️ **CFE Airborne:** {cfe_n}")
    st.markdown(f"✈️ **EFW Airborne:** {efw_n}")
    st.caption(f"Sandbox Data Feed: {api_total} flights in zone")
    show_fleet = st.checkbox("Show Aircraft on Map", value=True)
    st.markdown("---")
    show_cf = st.checkbox("Cityflyer Stations", value=True)
    show_ef = st.checkbox("Euroflyer Stations", value=True)
    xw_limit = st.slider("X-WIND LIMIT (KT)", 15, 35, 25)

# 6. RENDER MAP
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.11 (Sandbox Build)</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[52.0, 0.0], zoom_start=5, tiles="CartoDB dark_matter")

# Fleet Markers Logic
if show_fleet and active_fleet:
    for p in active_fleet:
        icon_color = "red" if p['type'] == "EFW" else ("blue" if p['type'] == "CFE" else "gray")
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
            tooltip=f"{p['callsign']}"
        ).add_to(m)

st_folium(m, width=1200, height=800, key="sandbox_fleet_map")
