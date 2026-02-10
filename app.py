import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import requests
from datetime import datetime

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
        border-radius: 50px; border: 2px solid #005a9c; min-width: 500px;
        display: flex; justify-content: space-around; align-items: center;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.6);
    }
    
    .floating-alerts {
        position: absolute; top: 100px; right: 20px; z-index: 1000;
        background: rgba(0, 35, 102, 0.92); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; width: 480px; max-height: 65vh; overflow-y: auto;
    }
    
    .wx-text { font-size: 15px !important; font-family: 'Courier New', monospace; line-height: 1.5; margin-top: 8px; color: white; }
    .metar-label { color: #ff4b4b; font-weight: bold; font-size: 12px; }
    .taf-label { color: #3182bd; font-weight: bold; font-size: 11px; }
    .icao-header { font-size: 18px; font-weight: bold; color: #eb8f34; border-bottom: 1px solid #555; }
    </style>
    """, unsafe_allow_html=True)

# 3. STATIC BASELINE (Prevents empty map)
base_airports = {
    "LCY": "EGLC", "AMS": "EHAM", "RTM": "EHRD", "DUB": "EIDW", "GLA": "EGPF",
    "EDI": "EGPH", "BHD": "EGAC", "STN": "EGSS", "SEN": "EGMC", "FLR": "LIRQ",
    "LGW": "EGKK", "JER": "EGJJ", "INN": "LOWI", "SZG": "LOWS", "NCE": "LFMN",
    "PMI": "LEPA", "FNC": "LPMA", "IBZ": "LEIB", "AGP": "LEMG", "ALC": "LEAL"
}

@st.cache_data(ttl=900)
def fetch_network_weather(icao_dict):
    res = {}
    for iata, icao in icao_dict.items():
        try:
            m = Metar(icao); m.update()
            t = Taf(icao); t.update()
            v = m.data.visibility.value if m.data.visibility else 9999
            c = 9999
            if m.data.clouds:
                for layer in m.data.clouds:
                    if layer.type in ['BKN', 'OVC'] and layer.base: c = min(c, layer.base * 100)
            
            res[icao] = {
                "iata": iata, "vis": v, "cig": c, "m": m.raw, "t": t.raw, 
                "lat": m.data.station.latitude, "lon": m.data.station.longitude
            }
        except: continue
    return res

# 4. EXECUTION
weather_data = fetch_network_weather(base_airports)

# UI: TOP COMMAND BAR
st.markdown(f"""
<div class="top-command-bar">
    <div style="font-size:15px; font-weight:bold; color:#eb8f34 !important;">📡 BA OCC HUD: CFE & EFW MONITOR</div>
    <div style="font-size:14px; border-left: 2px solid #005a9c; padding-left: 20px;">
        STATIONS ONLINE: {len(weather_data)}
    </div>
</div>
""", unsafe_allow_html=True)

# 5. MAP LAYER (Center set to Europe)
m = folium.Map(location=[48.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter", zoom_control=False)
active_alerts = {}

for icao, d in weather_data.items():
    # Alert Logic
    color = "#008000"
    if d['vis'] < 800 or d['cig'] < 200:
        color = "#d6001a"
        active_alerts[icao] = d
    elif d['vis'] < 1500 or d['cig'] < 500:
        color = "#eb8f34"
        active_alerts[icao] = d
    
    popup_html = f"<div style='width:350px; color:black;'><b>{d['iata']} ({icao})</b><br><b>METAR:</b> {d['m']}<br><b>TAF:</b> {d['t']}</div>"
    
    # Ensuring coordinates are valid
    if d['lat'] and d['lon']:
        folium.CircleMarker(
            location=[d['lat'], d['lon']], 
            radius=10, color=color, fill=True, fill_opacity=0.8, 
            popup=folium.Popup(popup_html, max_width=400)
        ).add_to(m)

st_folium(m, width=2200, height=1200, key="fixed_map")

# 6. ENHANCED ALERT HUD
with st.container():
    st.markdown('<div class="floating-alerts">', unsafe_allow_html=True)
    st.markdown("<h3 style='margin-bottom:15px;'>🚨 OPERATIONAL ALERTS</h3>", unsafe_allow_html=True)
    if not active_alerts:
        st.write("NETWORK STABLE - NO RED/AMBER WX DETECTED")
    for icao, d in active_alerts.items():
        st.markdown(f"""
            <div class='icao-header'>{d['iata']} / {icao}</div>
            <div class='wx-text'>
                <span class='metar-label'>CURRENT:</span> {d['m']}<br>
                <span class='taf-label'>FORECAST:</span> {d['t']}
            </div><br>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
