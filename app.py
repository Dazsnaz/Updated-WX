import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import requests
from datetime import datetime, timedelta

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Live HUD", page_icon="✈️")

# 2. HUD CSS STYLING
st.markdown("""
    <style>
    .main .block-container { padding: 0; max-width: 100%; height: 100vh; overflow: hidden; }
    [data-testid="stSidebar"] { background-color: #002366 !important; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold; }
    
    .top-command-bar {
        position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
        z-index: 1001; background: rgba(0, 35, 102, 0.95); padding: 12px 40px;
        border-radius: 50px; border: 2px solid #005a9c; min-width: 550px;
        display: flex; justify-content: space-around; align-items: center;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.6);
    }
    
    .floating-alerts {
        position: absolute; top: 100px; right: 20px; z-index: 1000;
        background: rgba(0, 35, 102, 0.92); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; width: 480px; max-height: 65vh; overflow-y: auto;
    }
    
    .wx-text { font-size: 15px !important; font-family: 'Courier New', monospace; line-height: 1.5; color: white; }
    .metar-label { color: #ff4b4b; font-weight: bold; font-size: 12px; }
    .taf-label { color: #3182bd; font-weight: bold; font-size: 12px; }
    .icao-header { font-size: 18px; font-weight: bold; color: #eb8f34; border-bottom: 1px solid #555; }
    </style>
    """, unsafe_allow_html=True)

# 3. BASELINE DESTINATIONS (Prevents Empty Map)
baseline_icao = ["EGLC", "EGKK", "EHAM", "EIDW", "EGJJ", "LFMN", "LEPA", "LOWI", "LPMA", "LEIB", "LIRQ", "EGPF", "EGPH", "EHRD", "EGSS"]

# 4. LIVE FLEET SCANNER (CFE & EFW)
def get_live_fleet_destinations():
    """Attempts to find current destinations for CFE/EFW aircraft"""
    # Note: AeroDataBox often requires specific airport lookups. 
    # This function is a placeholder for your RapidAPI integration logic.
    return ["EGLC", "EGKK", "EHAM", "EIDW", "EGJJ"]

@st.cache_data(ttl=900)
def fetch_weather(icao_list):
    res = {}
    for icao in icao_list:
        try:
            m = Metar(icao); m.update()
            t = Taf(icao); t.update()
            v = m.data.visibility.value if m.data.visibility else 9999
            c = 9999
            if m.data.clouds:
                for layer in m.data.clouds:
                    if layer.type in ['BKN', 'OVC'] and layer.base: c = min(c, layer.base * 100)
            res[icao] = {"vis": v, "cig": c, "m": m.raw, "t": t.raw, 
                         "lat": m.data.station.latitude, "lon": m.data.station.longitude}
        except: continue
    return res

# 5. EXECUTION
active_fleet_icao = get_live_fleet_destinations()
# Combine baseline and active for full visibility
weather_data = fetch_weather(list(set(baseline_icao + active_fleet_icao)))

# UI: TOP COMMAND BAR
st.markdown(f"""
<div class="top-command-bar">
    <div style="font-size:15px; font-weight:bold; color:#eb8f34 !important;">📡 LIVE HUD: CFE & EFW</div>
    <div style="font-size:14px; border-left: 2px solid #005a9c; padding-left: 20px;">STATIONS MONITORED: {len(weather_data)}</div>
</div>
""", unsafe_allow_html=True)

# 6. MAP LAYER
m = folium.Map(location=[48.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter", zoom_control=False)
active_alerts = {}

for icao, d in weather_data.items():
    # Only show logic for alerts
    color = "#008000"
    is_active_fleet = icao in active_fleet_icao
    
    if d['vis'] < 800 or d['cig'] < 200:
        color = "#d6001a"
        active_alerts[icao] = d
    elif d['vis'] < 1500 or d['cig'] < 500:
        color = "#eb8f34"
        active_alerts[icao] = d

    popup_html = f"<div style='width:350px; color:black;'><b>{icao}</b><br><b>METAR:</b> {d['m']}<br><b>TAF:</b> {d['t']}</div>"
    
    # Draw Station
    folium.CircleMarker(
        location=[d['lat'], d['lon']], 
        radius=12 if is_active_fleet else 7, # Make active fleet airports larger
        color=color, fill=True, fill_opacity=0.8,
        popup=folium.Popup(popup_html, max_width=400)
    ).add_to(m)

st_folium(m, width=2200, height=1200, key="live_map_v9")

# 7. ENHANCED ALERT HUD (Right Side)
with st.container():
    st.markdown('<div class="floating-alerts">', unsafe_allow_html=True)
    st.markdown("<h3 style='margin-bottom:15px;'>🚨 LIVE NETWORK ALERTS</h3>", unsafe_allow_html=True)
    if not active_alerts:
        st.write("NETWORK STABLE")
    for icao, d in active_alerts.items():
        st.markdown(f"""
            <div class='icao-header'>{icao}</div>
            <div class='wx-text'>
                <span class='metar-label'>CURRENT:</span> {d['m']}<br>
                <span class='taf-label'>FORECAST:</span> {d['t']}
            </div><br>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
