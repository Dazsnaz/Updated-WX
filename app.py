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
    .reason-box { background-color: #ffffff !important; padding: 25px; border-top: 10px solid #d6001a; }
    .reason-box * { color: #002366 !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. DATA FETCH (v35.14 - Multi-Zone Probe)
@st.cache_data(ttl=60)
def get_fleet_multi_zone():
    if not FR_AVAILABLE: return [], 0, 0, 0, [], "Driver Not Found"
    
    api_token = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"
    fleet_list = []
    raw_calls = []
    error_msg = "None"
    
    try:
        with Client(api_token=api_token) as client:
            # TRY ZONE 1: UK & WESTERN EUROPE (Most likely for BA)
            bounds = "71.0,35.0,-15.0,25.0"
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            # TRY ZONE 2: SDK DOCUMENTATION BOX (Fallback if Zone 1 is empty)
            if not flights or not flights.data:
                bounds = "50.682,46.218,14.422,22.243"
                flights = client.live.flight_positions.get_light(bounds=bounds)

            if flights and flights.data:
                for f in flights.data:
                    call = getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "N/A"
                    if call != "N/A" and len(raw_calls) < 5:
                        raw_calls.append(call)
                    
                    f_type = "OTHER"
                    if "CFE" in call.upper(): f_type = "CFE"
                    elif "EFW" in call.upper(): f_type = "EFW"
                    
                    fleet_list.append({
                        "callsign": call, "lat": f.latitude, "lon": f.longitude, "type": f_type
                    })
            else:
                error_msg = "API returned empty list for both UK and SDK zones."
                
        cfe = [p for p in fleet_list if p['type'] == "CFE"]
        efw = [p for p in fleet_list if p['type'] == "EFW"]
        return fleet_list, len(cfe), len(efw), len(fleet_list), raw_calls, error_msg
    except Exception as e:
        return [], 0, 0, 0, [], str(e)

active_fleet, cfe_n, efw_n, total_n, probe, err = get_fleet_multi_zone()

# 4. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    st.markdown("📡 **API STATUS**")
    if err != "None": st.error(f"Status: {err}")
    else: st.success("Connected to FR24")
    
    if probe:
        st.write("Recent Callsigns:")
        for p in probe: st.code(p)

    st.markdown("---")
    st.markdown(f"✈️ **CFE Airborne:** {cfe_n}")
    st.markdown(f"✈️ **EFW Airborne:** {efw_n}")
    st.caption(f"Total flights in current zone: {total_n}")
    show_all = st.checkbox("Show All Traffic", value=True)

# 5. RENDER MAP
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.14</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter")

if active_fleet:
    for p in active_fleet:
        if not show_all and p['type'] == "OTHER": continue
        color = "blue" if p['type'] == "CFE" else ("red" if p['type'] == "EFW" else "gray")
        folium.Marker(location=[p['lat'], p['lon']], icon=folium.Icon(color=color, icon="plane", prefix="fa"), tooltip=p['callsign']).add_to(m)

st_folium(m, width=1200, height=800, key="v35_14_map")
