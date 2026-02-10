import streamlit as st
import folium
from streamlit_folium import st_folium
import avwx
import math
from datetime import datetime

# 1. PAGE SETUP
st.set_page_config(layout="wide", page_title="BA OCC HUD - Full Fleet", page_icon="✈️")

# 2. CSS STYLING
st.markdown("""
    <style>
    .main .block-container { padding: 0; max-width: 100%; height: 100vh; overflow: hidden; }
    [data-testid="stSidebar"] { background-color: #002366 !important; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold; }
    .top-pill {
        position: fixed; top: 15px; left: 50%; transform: translateX(-50%);
        z-index: 1001; background: rgba(0, 35, 102, 0.95); padding: 10px 30px;
        border-radius: 50px; border: 2px solid #005a9c; min-width: 550px;
        display: flex; justify-content: space-around; align-items: center; color: white;
    }
    .alert-panel {
        position: absolute; top: 100px; right: 20px; z-index: 1000;
        background: rgba(0, 35, 102, 0.9); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; width: 450px; max-height: 60vh; overflow-y: auto; color: white;
    }
    .wx-box { font-family: 'Courier New', monospace; font-size: 15px; margin-top: 8px; }
    .metar-tag { color: #ff4b4b; font-weight: bold; }
    .taf-tag { color: #3182bd; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 3. FULL BASELINE FLEET (CFE & EFW)
baseline_icao = {
    # --- CITYFLYER (CFE) ---
    "LCY": "EGLC", "AMS": "EHAM", "RTM": "EHRD", "DUB": "EIDW", "GLA": "EGPF",
    "EDI": "EGPH", "BHD": "EGAC", "STN": "EGSS", "SEN": "EGMC", "FLR": "LIRQ",
    "AGP": "LEMG", "BER": "EDDB", "FRA": "EDDF", "LIN": "LIML", "CMF": "LFLB",
    "GVA": "LSGG", "ZRH": "LSZH", "MAD": "LEMD", "IBZ": "LEIB", "PMI": "LEPA", "FAO": "LPFR",
    # --- EUROFLYER (EFW) ---
    "LGW": "EGKK", "JER": "EGJJ", "OPO": "LPPR", "LYS": "LFLL", "INN": "LOWI",
    "SZG": "LOWS", "BOD": "LFBD", "GNB": "LFLS", "NCE": "LFMN", "TRN": "LIMF",
    "VRN": "LIPX", "ALC": "LEAL", "SVQ": "LEZL", "RAK": "GMMX", "AGA": "GMAD",
    "SSH": "HESH", "PFO": "LCPH", "LCA": "LCLK", "FUE": "GCLP", "TFS": "GCTS",
    "ACE": "GCRR", "LPA": "GCLP", "IVL": "EFIV", "MLA": "LMML", "FNC": "LPMA"
}

@st.cache_data(ttl=600)
def fetch_weather(icao_dict):
    res = {}
    for iata, icao in icao_dict.items():
        try:
            m = avwx.Metar(icao)
            t = avwx.Taf(icao)
            if m.update() and t.update():
                res[icao] = {
                    "iata": iata, "m": m.raw, "t": t.raw,
                    "lat": m.station.latitude, "lon": m.station.longitude,
                    "vis": m.data.visibility.value if m.data.visibility else 9999,
                    "cig": 9999
                }
                if m.data.clouds:
                    for l in m.data.clouds:
                        if l.type in ['BKN', 'OVC']: res[icao]["cig"] = min(res[icao]["cig"], l.base * 100)
        except: continue
    return res

# 4. DATA FETCH
weather_data = fetch_weather(baseline_icao)

# 5. UI ELEMENTS
st.markdown(f"""<div class="top-pill">
    <b>CFE & EFW MONITOR: {len(weather_data)} STATIONS</b>
    <span style="border-left:1px solid #555; padding-left:15px;">{datetime.utcnow().strftime('%H:%M')} UTC</span>
</div>""", unsafe_allow_html=True)

# 6. MAP LAYER
m = folium.Map(location=[48.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter", zoom_control=False)

active_alerts = {}
for icao, d in weather_data.items():
    color = "#008000" # Default Green
    if d['vis'] < 800 or d['cig'] < 200: 
        color = "#d6001a" # Red Alert
        active_alerts[icao] = d
    elif d['vis'] < 1500 or d['cig'] < 500: 
        color = "#eb8f34" # Amber Alert
        active_alerts[icao] = d

    folium.CircleMarker(
        location=[d['lat'], d['lon']],
        radius=8, color=color, fill=True, fill_opacity=0.8,
        popup=folium.Popup(f"<b>{d['iata']} ({icao})</b><br>{d['m']}", max_width=350)
    ).add_to(m)

st_folium(m, width=2200, height=1200, key="occ_full_fleet")

# 7. ALERT OVERLAY (Right)
if active_alerts:
    with st.container():
        st.markdown('<div class="alert-panel"><h4>🚨 OPERATIONAL ALERTS</h4>', unsafe_allow_html=True)
        for icao, d in active_alerts.items():
            st.markdown(f"""
                <div style="border-bottom:1px solid #444; padding:12px 0;">
                    <b style="color:#eb8f34; font-size:16px;">{d['iata']} / {icao}</b>
                    <div class="wx-box">
                        <span class="metar-tag">METAR:</span> {d['m']}<br><br>
                        <span class="taf-tag">TAF:</span> {d['t']}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
