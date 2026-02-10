import streamlit as st
import folium
from streamlit_folium import st_folium
import avwx
import math
from datetime import datetime

# 1. PAGE SETUP
st.set_page_config(layout="wide", page_title="BA OCC HUD - Command", page_icon="✈️")

# 2. CSS STYLING
st.markdown("""
    <style>
    .main .block-container { padding: 0; max-width: 100%; height: 100vh; overflow: hidden; }
    [data-testid="stSidebar"] { background-color: #002366 !important; }
    
    .top-pill {
        position: fixed; top: 15px; left: 50%; transform: translateX(-50%);
        z-index: 1001; background: rgba(0, 35, 102, 0.95); padding: 10px 30px;
        border-radius: 50px; border: 2px solid #005a9c; min-width: 550px;
        display: flex; justify-content: space-around; align-items: center; color: white;
    }
    
    .alert-panel {
        position: absolute; top: 100px; right: 20px; z-index: 1000;
        background: rgba(0, 35, 102, 0.85); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; width: 320px; max-height: 60vh; overflow-y: auto;
    }

    /* Base button style for HUD */
    .stButton > button {
        color: white !important;
        font-weight: bold !important;
        width: 100%;
        margin-bottom: 8px;
        border: 1px solid rgba(255,255,255,0.3) !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .floating-analysis {
        position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%);
        z-index: 1001; background: rgba(255, 255, 255, 0.98); padding: 25px; 
        border-radius: 8px; width: 85%; max-width: 1150px; 
        border-top: 12px solid #002366; color: #002366 !important;
        box-shadow: 0px 10px 30px rgba(0,0,0,0.5);
    }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def get_dist(lat1, lon1, lat2, lon2):
    R = 3440.065 # Nautical Miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 0)

# 4. FLEET STATIONS (CFE & EFW)
baseline_icao = {
    "LCY": "EGLC", "AMS": "EHAM", "RTM": "EHRD", "DUB": "EIDW", "GLA": "EGPF",
    "EDI": "EGPH", "BHD": "EGAC", "STN": "EGSS", "SEN": "EGMC", "FLR": "LIRQ",
    "LGW": "EGKK", "JER": "EGJJ", "INN": "LOWI", "SZG": "LOWS", "NCE": "LFMN",
    "PMI": "LEPA", "FNC": "LPMA", "IBZ": "LEIB", "AGP": "LEMG", "ALC": "LEAL"
}

@st.cache_data(ttl=600)
def fetch_weather(icao_dict):
    res = {}
    for iata, icao in icao_dict.items():
        try:
            m = avwx.Metar(icao); t = avwx.Taf(icao)
            if m.update() and t.update():
                v = m.data.visibility.value if m.data.visibility else 9999
                c = 9999
                if m.data.clouds:
                    for l in m.data.clouds:
                        if l.type in ['BKN', 'OVC']: c = min(c, l.base * 100)
                
                wx_type = "GENERAL"
                if any(x in m.raw for x in ["SN", "SG", "IC"]): wx_type = "SNOW"
                elif "FG" in m.raw: wx_type = "FOG"
                elif v < 1500: wx_type = "VIS"
                elif c < 500: wx_type = "CLOUDBASE"
                elif (m.data.wind_speed.value or 0) > 20: wx_type = "X-WIND"

                res[icao] = {
                    "iata": iata, "m": m.raw, "t": t.raw, "lat": m.station.latitude, 
                    "lon": m.station.longitude, "vis": v, "cig": c, "type": wx_type,
                    "w_spd": m.data.wind_speed.value or 0, "w_dir": m.data.wind_direction.value or 0
                }
        except: continue
    return res

# 5. SIDEBAR
st.sidebar.title("🔧 HUD SETTINGS")
map_theme = st.sidebar.radio("MAP THEME", ["Dark Mode", "Light Mode"])

weather_data = fetch_weather(baseline_icao)

# 6. PROCESSING
if 'investigate_icao' not in st.session_state: st.session_state.investigate_icao = "None"

active_alerts = {}; green_stations = []
for icao, d in weather_data.items():
    if d['vis'] < 1500 or d['cig'] < 500 or d['w_spd'] > 20:
        active_alerts[icao] = d
    else:
        green_stations.append(icao)

# 7. UI RENDER
st.markdown(f'<div class="top-pill"><b>BA OCC NETWORK MONITOR</b><span>{datetime.utcnow().strftime("%H:%M")} UTC</span></div>', unsafe_allow_html=True)

tile_style = "CartoDB dark_matter" if map_theme == "Dark Mode" else "CartoDB positron"
m = folium.Map(location=[48.0, 5.0], zoom_start=5, tiles=tile_style, zoom_control=False)
for icao, d in weather_data.items():
    color = "#008000"
    if icao in active_alerts: color = "#d6001a" if d['vis'] < 800 or d['cig'] < 200 else "#eb8f34"
    folium.CircleMarker(location=[d['lat'], d['lon']], radius=8, color=color, fill=True, fill_opacity=0.8).add_to(m)
st_folium(m, width=2200, height=1200, key="occ_map")

# 8. COLOR-CODED ALERT LIST (RIGHT)
with st.container():
    st.markdown('<div class="alert-panel"><h4 style="color:white; margin-bottom:15px;">🚨 LIVE ALERTS</h4>', unsafe_allow_html=True)
    for icao, d in active_alerts.items():
        # Determine Color
        btn_color = "#d6001a" if d['vis'] < 800 or d['cig'] < 200 else "#eb8f34"
        
        # Unique CSS for each button to force specific color
        st.markdown(f"""
            <style>
            div[data-testid="stVerticalBlock"] > div:nth-child(n) button[key="btn_{icao}"] {{
                background-color: {btn_color} !important;
            }}
            </style>
            """, unsafe_allow_html=True)
        
        if st.button(f"{d['iata']} - {d['type']}", key=f"btn_{icao}"):
            st.session_state.investigate_icao = icao
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# 9. IMPACT BOX (BOTTOM)
if st.session_state.investigate_icao in active_alerts:
    d = active_alerts[st.session_state.investigate_icao]
    alt_iata = "N/A"; alt_dist = 9999
    for g_icao in green_stations:
        dist = get_dist(d['lat'], d['lon'], weather_data[g_icao]['lat'], weather_data[g_icao]['lon'])
        if dist < alt_dist: alt_dist = dist; alt_iata = weather_data[g_icao]['iata']

    st.markdown(f"""
    <div class="floating-analysis">
        <h3 style="color:#002366;">{d['iata']} / {st.session_state.investigate_icao} OPERATIONAL IMPACT</h3>
        <div style="display:flex; gap:30px; margin-top:15px; color:#002366;">
            <div style="flex:1.2;">
                <p><b>WEATHER OVERVIEW:</b> Observed {d['vis']}m visibility and {d['cig']}ft ceiling. Winds at {d['w_dir']}°/{d['w_spd']}kt.</p>
                <p><b>DIVERSION PLANNING:</b> Closest Green station is <b>{alt_iata}</b> ({alt_dist} NM).</p>
                <p><b>IMPACT STATEMENT:</b> Possible <b>ATC holding or diversions</b>. Low visibility procedures (LVP) may be in effect, reducing flow rates.</p>
            </div>
            <div style="flex:1; background:#f4f4f4; padding:15px; border-radius:5px; font-family:monospace; font-size:12px; border-left: 5px solid #d6001a;">
                <b>METAR:</b><br>{d['m']}<br><br>
                <b>TAF:</b><br>{d['t']}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("✖ CLOSE ANALYSIS", key="close_box"):
        st.session_state.investigate_icao = "None"; st.rerun()
