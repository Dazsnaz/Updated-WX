import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Express HUD", page_icon="✈️")

# 2. CSS STYLING (NAVY & RED)
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; border-radius: 8px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; border-right: 3px solid #d6001a; min-width: 350px !important; }
    .stMetric { background-color: #001a33; border-left: 5px solid #d6001a; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 3. OPENSKY DATA ENGINE
@st.cache_data(ttl=30)
def fetch_filtered_fleet():
    fleet = []
    try:
        # Broad European/UK box
        url = "https://opensky-network.org/api/states/all?lamin=35.0&lomin=-15.0&lamax=65.0&lomax=20.0"
        r = requests.get(url, timeout=5)
        data = r.json()
        
        if "states" in data and data["states"]:
            for s in data["states"]:
                call = (s[1] or "").strip().upper()
                if not call: continue
                
                f_type = None
                if call.startswith("CFE"): f_type = "CFE"
                elif call.startswith("EFW"): f_type = "EFW"
                elif call.startswith("BAW") or call.startswith("SHT"): f_type = "BAW"
                
                if f_type:
                    raw_alt = s[7] if s[7] is not None else 0
                    fleet.append({
                        "callsign": call,
                        "lat": s[6], "lon": s[5],
                        "type": f_type,
                        "alt": round(raw_alt * 3.28084),
                        "ground": s[8]
                    })
    except: pass
    return fleet

# 4. EXECUTION
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.33 | EXPRESS FILTER</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

live_data = fetch_filtered_fleet()

with st.sidebar:
    st.title("🛡️ FLEET CONTROL")
    if st.button("🔄 REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    # FILTER TOGGLE
    view_mode = st.radio("View Mode:", ["BA Express Only (CFE/EFW)", "Show All BA Group"], index=0)
    
    st.markdown("---")
    cfe_fleet = [p for p in live_data if p['type'] == "CFE"]
    efw_fleet = [p for p in live_data if p['type'] == "EFW"]
    
    st.metric("Cityflyer (CFE)", len(cfe_fleet))
    st.metric("Euroflyer (EFW)", len(efw_fleet))
    
    if live_data:
        st.markdown("### Active Callsigns")
        display_list = cfe_fleet + efw_fleet if "Express" in view_mode else live_data
        for p in display_list:
            st.code(f"{p['callsign']} @ {p['alt']}ft")

# 5. MAP RENDER
m = folium.Map(location=[52.5, 0.0], zoom_start=6, tiles="CartoDB dark_matter")

if live_data:
    for p in live_data:
        # Logic: If 'Express Only' is on, skip BAW
        if "Express" in view_mode and p['type'] == "BAW":
            continue
            
        color = "blue" if p['type'] == "CFE" else ("red" if p['type'] == "EFW" else "cadetblue")
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color=color, icon="plane", prefix="fa"),
            tooltip=f"{p['callsign']} | {p['alt']}ft"
        ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_33_filter")
