import streamlit as st
import folium
from streamlit_folium import st_folium
from fr24sdk.client import Client 
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. STABLE v29.2 CSS
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; border-radius: 8px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; border-right: 3px solid #d6001a; min-width: 400px !important; }
    .debug-box { background-color: #000; color: #0f0 !important; padding: 10px; font-family: monospace; font-size: 0.75rem; border: 1px solid #333; height: 250px; overflow-y: scroll; }
    </style>
    """, unsafe_allow_html=True)

# 3. LIVE PRODUCTION TOKEN
LIVE_TOKEN = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"

# 4. MEGA-ZONE DATA ENGINE
@st.cache_data(ttl=60)
def fetch_mega_zone():
    fleet = []
    all_calls = []
    try:
        with Client(api_token=LIVE_TOKEN) as client:
            # MEGA-ZONE: North, South, West, East (Covers all of Europe)
            # 72°N (Norway) to 30°N (North Africa), -25°W (Atlantic) to 45°E (Turkey)
            bounds = "72.0,30.0,-25.0,45.0" 
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                for f in flights.data:
                    call = (getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "UKNOWN").upper()
                    all_calls.append(call)
                    
                    # Search for CFE/EFW/BAW/SHT anywhere in the callsign
                    f_tag = "OTHER"
                    if "CFE" in call: f_tag = "CFE"
                    elif "EFW" in call: f_tag = "EFW"
                    elif "BAW" in call or "SHT" in call: f_tag = "BA_GROUP"
                    
                    fleet.append({"callsign": call, "lat": f.lat, "lon": f.lon, "type": f_tag})
        return fleet, sorted(list(set(all_calls)))
    except Exception as e:
        return [], [f"Error: {str(e)}"]

# 5. RENDER HUD
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.27 | MEGA-ZONE OPS</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

active_fleet, call_probe = fetch_mega_zone()

with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH EUROPEAN FEED"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    # Operational Metrics
    cfe_c = len([p for p in active_fleet if p['type'] == "CFE"])
    efw_c = len([p for p in active_fleet if p['type'] == "EFW"])
    ba_c = len([p for p in active_fleet if p['type'] == "BA_GROUP"])
    
    st.metric("Cityflyer (CFE) Active", cfe_c)
    st.metric("Euroflyer (EFW) Active", efw_c)
    st.metric("BA Mainline/SHT", ba_c)
    
    st.markdown("---")
    st.markdown("📋 **LIVE CALLSIGN PROBE (All Detected)**")
    # This box will show us every single callsign the API is seeing
    probe_txt = "\n".join(call_probe) if call_probe else "No data"
    st.markdown(f'<div class="debug-box">{probe_txt}</div>', unsafe_allow_html=True)

# 6. MAP
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter")
for p in active_fleet:
    if p['type'] != "OTHER": # Focus only on BA Group for now to clean the map
        color = "blue" if p['type'] == "CFE" else ("red" if p['type'] == "EFW" else "cadetblue")
        folium.Marker([p['lat'], p['lon']], icon=folium.Icon(color=color), tooltip=p['callsign']).add_to(m)

st_folium(m, width=1200, height=800, key="v35_27_mega")
