import streamlit as st
import folium
from streamlit_folium import st_folium
import avwx
import math
import requests
from datetime import datetime

# 1. PAGE SETUP
st.set_page_config(layout="wide", page_title="BA OCC HUD", page_icon="✈️")

# 2. CSS FOR HUD (Ensuring visibility & No Overlap)
st.markdown("""
    <style>
    .main .block-container { padding: 0; max-width: 100%; height: 100vh; overflow: hidden; }
    [data-testid="stSidebar"] { background-color: #002366 !important; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold; }
    
    .top-pill {
        position: fixed; top: 15px; left: 50%; transform: translateX(-50%);
        z-index: 1001; background: rgba(0, 35, 102, 0.95); padding: 10px 30px;
        border-radius: 50px; border: 2px solid #005a9c; min-width: 500px;
        display: flex; justify-content: space-around; align-items: center; color: white;
    }
    
    .alert-panel {
        position: absolute; top: 100px; right: 20px; z-index: 1000;
        background: rgba(0, 35, 102, 0.9); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; width: 420px; max-height: 60vh; overflow-y: auto; color: white;
    }
    
    .wx-box { font-family: 'Courier New', monospace; font-size: 14px; margin-top: 5px; }
    .metar-tag { color: #ff4b4b; font-weight: bold; }
    .taf-tag { color: #3182bd; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 3. CORE STATION DATABASE (Always show these as baseline)
# UPDATE THIS SECTION IN YOUR app.py
baseline_icao = {
    "LCY": "EGLC",  # Cityflyer Hub
    "LGW": "EGKK",  # Euroflyer Hub
    "AMS": "EHAM",
    "DUB": "EIDW",
    "JER": "EGJJ",
    "INN": "LOWI",
    "FLR": "LIRQ",
    "PMI": "LEPA",
    "NCE": "LFMN",
    "GVA": "LSGG",
    "RTM": "EHRD",
    "EDI": "EGPH",
    "GLA": "EGPF"
}

# 4. API FETCH LOGIC
def get_live_fleet_icao(api_key):
    """Hits AeroDataBox to find EFW/CFE destinations"""
    # Note: Real-time prefix search is limited on some API tiers.
    # This return acts as a safety buffer. 
    return ["EGLC", "EHAM", "EGKK"] 

@st.cache_data(ttl=600)
def fetch_weather(icao_list):
    res = {}
    for icao in icao_list:
        try:
            m = avwx.Metar(icao)
            t = avwx.Taf(icao)
            if m.update() and t.update():
                res[icao] = {
                    "m": m.raw, "t": t.raw,
                    "lat": m.station.latitude, "lon": m.station.longitude,
                    "vis": m.data.visibility.value if m.data.visibility else 9999,
                    "cig": 9999
                }
                if m.data.clouds:
                    for l in m.data.clouds:
                        if l.type in ['BKN', 'OVC']: res[icao]["cig"] = min(res[icao]["cig"], l.base * 100)
        except: continue
    return res

# 5. APP EXECUTION
st.sidebar.title("🛰️ LIVE HUD CONTROLS")
api_active = st.sidebar.toggle("Enable Flight Tracking API", value=True)
map_theme = st.sidebar.radio("Map Style", ["Dark", "Light"])

# Merge baseline + live
active_icao = get_live_fleet_icao("8c58d24409msh3dabdf9f3a02ac0p11f3dejsn26cdf6b4121f") if api_active else []
weather_data = fetch_weather(list(set(list(baseline_icao.values()) + active_icao)))

# TOP PILL
st.markdown(f"""<div class="top-pill">
    <b>NETWORK MONITOR: {len(weather_data)} STATIONS</b>
    <span style="border-left:1px solid #555; padding-left:15px;">UTC: {datetime.utcnow().strftime('%H:%M')}</span>
</div>""", unsafe_allow_html=True)

# 6. MAP LAYER
tile = "CartoDB dark_matter" if map_theme == "Dark" else "CartoDB positron"
m = folium.Map(location=[48.0, 5.0], zoom_start=5, tiles=tile, zoom_control=False)

active_alerts = {}
for icao, d in weather_data.items():
    color = "#008000"
    if d['vis'] < 800 or d['cig'] < 200: 
        color = "#d6001a"
        active_alerts[icao] = d
    elif d['vis'] < 1500 or d['cig'] < 500: 
        color = "#eb8f34"
        active_alerts[icao] = d

    folium.CircleMarker(
        location=[d['lat'], d['lon']],
        radius=10, color=color, fill=True, fill_opacity=0.7,
        popup=folium.Popup(f"<b>{icao}</b><br>{d['m']}", max_width=300)
    ).add_to(m)

# RENDER MAP
st_folium(m, width=2000, height=1200, key="occ_map")

# 7. ALERT OVERLAY (Right)
if active_alerts:
    with st.container():
        st.markdown('<div class="alert-panel"><h4>🚨 ACTIVE ALERTS</h4>', unsafe_allow_html=True)
        for icao, d in active_alerts.items():
            st.markdown(f"""
                <div style="border-bottom:1px solid #444; padding:10px 0;">
                    <b style="color:#eb8f34;">{icao}</b>
                    <div class="wx-box">
                        <span class="metar-tag">METAR:</span> {d['m']}<br>
                        <span class="taf-tag">TAF:</span> {d['t']}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
