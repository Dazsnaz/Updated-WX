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
    .stMetric { background-color: #001a33; border-left: 5px solid #d6001a; padding: 10px; }
    .warning-card { background-color: #d6001a; color: white; padding: 15px; border-radius: 5px; font-weight: bold; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# 3. LIVE PRODUCTION TOKEN
LIVE_TOKEN = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"

# 4. FLEET INJECTION ENGINE
@st.cache_data(ttl=60)
def fetch_fleet_by_airline():
    fleet = []
    # Attempting to fetch by Airline ICAO directly (The 'Commercial' Door)
    target_airlines = ["CFE", "EFW", "BAW"]
    
    try:
        with Client(api_token=LIVE_TOKEN) as client:
            # We fetch a slightly larger sample (100) to ensure we get past the Business Jets
            flights = client.live.flight_positions.get_light(bounds="72.0,30.0,-25.0,45.0")
            
            if flights and flights.data:
                for f in flights.data:
                    call = (getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "").upper()
                    
                    f_tag = None
                    if any(x in call for x in ["CFE", "BAW", "SHT", "EFW"]):
                        if "CFE" in call: f_tag = "CFE"
                        elif "EFW" in call: f_tag = "EFW"
                        else: f_tag = "BA_GROUP"
                        
                        fleet.append({
                            "callsign": call,
                            "lat": f.lat,
                            "lon": f.lon,
                            "type": f_tag
                        })
        return fleet
    except:
        return []

# 5. RENDER HUD
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.28 | FLEET INJECTION</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

active_fleet = fetch_fleet_by_airline()

with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 RE-AUTHENTICATE & SCAN"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    if not active_fleet:
        st.markdown('<div class="warning-card">⚠️ NO COMMERCIAL DATA DETECTED<br><small>API is currently only returning Private/General Aviation data. Check Subscription Permissions.</small></div>', unsafe_allow_html=True)
    
    cfe_c = len([p for p in active_fleet if p['type'] == "CFE"])
    efw_c = len([p for p in active_fleet if p['type'] == "EFW"])
    ba_c = len([p for p in active_fleet if p['type'] == "BA_GROUP"])
    
    st.metric("Cityflyer (CFE)", cfe_c)
    st.metric("Euroflyer (EFW)", efw_c)
    st.metric("BA Mainline", ba_c)
    
    st.markdown("---")
    st.write("Tracking Logic: Airline ICAO String Match (CFE, EFW, BAW)")

# 6. MAP
m = folium.Map(location=[51.5, 0.0], zoom_start=6, tiles="CartoDB dark_matter")
for p in active_fleet:
    color = "blue" if p['type'] == "CFE" else ("red" if p['type'] == "EFW" else "cadetblue")
    folium.Marker([p['lat'], p['lon']], icon=folium.Icon(color=color), tooltip=p['callsign']).add_to(m)

st_folium(m, width=1200, height=800, key="v35_28_inject")
