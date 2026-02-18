import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Hybrid HUD")

# 2. CSS STYLING (NAVY/RED)
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; border-radius: 8px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; border-right: 3px solid #d6001a; min-width: 400px !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. OPENSKY ENGINE (Free Commercial Data)
@st.cache_data(ttl=30)
def fetch_opensky_fleet():
    fleet = []
    try:
        # Tighter box over UK/Europe for faster loading: N, S, W, E
        url = "https://opensky-network.org/api/states/all?lamin=48.0&lamin=30.0&lamax=60.0&lomin=-15.0&lomax=10.0"
        r = requests.get(url, timeout=5)
        data = r.json()
        
        if "states" in data and data["states"]:
            for s in data["states"]:
                call = (s[1] or "").strip().upper()
                if not call: continue
                
                f_type = None
                if call.startswith("CFE"): f_type = "CFE"
                elif call.startswith("EFW"): f_type = "EFW"
                elif call.startswith("BAW"): f_type = "BAW"
                
                if f_type:
                    fleet.append({
                        "callsign": call,
                        "lat": s[6],
                        "lon": s[5],
                        "type": f_type,
                        "alt": s[7] # Altitude in meters
                    })
    except: pass
    return fleet

# 4. EXECUTION
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.31 | HYBRID DATA</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

live_fleet = fetch_opensky_fleet()

with st.sidebar:
    st.title("🛡️ HYBRID FEED")
    if st.button("🔄 REFRESH FLEET"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    cfe_c = len([p for p in live_fleet if p['type'] == "CFE"])
    efw_c = len([p for p in live_fleet if p['type'] == "EFW"])
    
    st.metric("Cityflyer (OpenSky)", cfe_c)
    st.metric("Euroflyer (OpenSky)", efw_c)
    
    st.markdown("---")
    st.info("Note: OpenSky data is crowdsourced. If an aircraft is out of range of a ground station, it may disappear for a few minutes.")

# 5. MAP RENDER
m = folium.Map(location=[52.5, -1.0], zoom_start=6, tiles="CartoDB dark_matter")

if live_fleet:
    for p in live_fleet:
        color = "blue" if p['type'] == "CFE" else ("red" if p['type'] == "EFW" else "cadetblue")
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color=color, icon="plane", prefix="fa"),
            tooltip=f"{p['callsign']} | Alt: {round(p['alt']*3.28084)}ft"
        ).add_to(m)
else:
    st.warning("Scanning for CFE/EFW transponders via OpenSky... No matches in UK airspace currently.")

st_folium(m, width=1200, height=800, key="v35_31_hybrid")
