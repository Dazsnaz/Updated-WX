import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Hybrid HUD", page_icon="✈️")

# 2. CSS STYLING
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; border-radius: 8px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; border-right: 3px solid #d6001a; min-width: 400px !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. OPENSKY ENGINE (Safe Altitude Logic)
@st.cache_data(ttl=30)
def fetch_opensky_fleet():
    fleet = []
    try:
        # Bounding box for UK/Europe: min lat, min lon, max lat, max lon
        # Using a direct URL parameter format
        url = "https://opensky-network.org/api/states/all?lamin=45.0&lomin=-15.0&lamax=62.0&lomax=15.0"
        r = requests.get(url, timeout=5)
        data = r.json()
        
        if "states" in data and data["states"]:
            for s in data["states"]:
                # OpenSky Index Map: 1=Callsign, 5=Lon, 6=Lat, 7=GeoAlt, 8=OnGround
                call = (s[1] or "").strip().upper()
                if not call: continue
                
                f_type = None
                if call.startswith("CFE"): f_type = "CFE"
                elif call.startswith("EFW"): f_type = "EFW"
                elif call.startswith("BAW"): f_type = "BAW"
                
                if f_type:
                    # SAFE ALTITUDE CHECK: Fallback to 0 if None
                    raw_alt = s[7] if s[7] is not None else 0
                    alt_ft = round(raw_alt * 3.28084)
                    
                    fleet.append({
                        "callsign": call,
                        "lat": s[6],
                        "lon": s[5],
                        "type": f_type,
                        "alt": alt_ft,
                        "ground": s[8]
                    })
    except Exception as e:
        pass 
    return fleet

# 4. EXECUTION
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.32 | FLEET RECOVERY</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

live_fleet = fetch_opensky_fleet()

with st.sidebar:
    st.title("🛡️ HYBRID FEED")
    if st.button("🔄 REFRESH FLEET"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    cfe_c = len([p for p in live_fleet if p['type'] == "CFE"])
    efw_c = len([p for p in live_fleet if p['type'] == "EFW"])
    ba_c = len([p for p in live_fleet if p['type'] == "BAW"])
    
    st.metric("Cityflyer (CFE)", cfe_c)
    st.metric("Euroflyer (EFW)", efw_c)
    st.metric("Mainline (BAW)", ba_c)
    
    if live_fleet:
        st.markdown("### Active Callsigns")
        for p in live_fleet:
            status = "✈️" if not p['ground'] else "🚧"
            st.code(f"{status} {p['callsign']} @ {p['alt']}ft")

# 5. MAP RENDER
m = folium.Map(location=[52.5, -1.0], zoom_start=6, tiles="CartoDB dark_matter")

for p in live_fleet:
    color = "blue" if p['type'] == "CFE" else ("red" if p['type'] == "EFW" else "cadetblue")
    folium.Marker(
        location=[p['lat'], p['lon']],
        icon=folium.Icon(color=color, icon="plane", prefix="fa"),
        tooltip=f"{p['callsign']} | Alt: {p['alt']}ft"
    ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_32_hybrid")
