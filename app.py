import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
from datetime import datetime

# 1. PAGE CONFIG & FULL-SCREEN UI
st.set_page_config(layout="wide", page_title="BA OCC Tactical HUD", page_icon="✈️", initial_sidebar_state="collapsed")

# 2. TAC-DASHBOARD CSS (OVERLAY SYSTEM)
st.markdown("""
    <style>
    /* Force full screen and hide standard padding */
    .main .block-container { padding: 0 !important; max-width: 100% !important; height: 100vh !important; }
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Background Map Container */
    .map-container { position: absolute; top: 0; left: 0; width: 100%; height: 100vh; z-index: 0; }
    
    /* Floating Dashboard Panels */
    .hud-overlay {
        position: absolute;
        background: rgba(0, 35, 102, 0.85);
        color: white;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.2);
        backdrop-filter: blur(10px);
        z-index: 1000;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    
    /* Panel Positions */
    .top-left-panel { top: 20px; left: 20px; width: 300px; }
    .bottom-center-panel { bottom: 20px; left: 50%; transform: translateX(-50%); width: 90%; max-height: 250px; overflow-y: auto; }
    .top-right-panel { top: 20px; right: 20px; width: 350px; }
    
    /* Alert Button Styling */
    .stButton > button {
        background-color: rgba(0, 90, 156, 0.9) !important;
        color: white !important;
        border: 1px solid white !important;
        font-size: 0.6rem !important;
        height: 55px !important;
        line-height: 1.1 !important;
        font-weight: bold;
    }
    div.stButton > button[kind="primary"] { background-color: #d6001a !important; }
    div.stButton > button[kind="secondary"] { background-color: #eb8f34 !important; }
    
    /* Typography */
    .hud-title { font-size: 1.2rem; font-weight: bold; border-bottom: 2px solid #d6001a; margin-bottom: 10px; padding-bottom: 5px; }
    .handover-box textarea { background: rgba(255,255,255,0.9) !important; color: #002366 !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_xwind(wind_dir, wind_spd, rwy_hdg):
    if wind_dir is None or wind_spd is None or rwy_hdg is None: return 0
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

def bold_hazard(text):
    if not text or text == "N/A": return text
    text = re.sub(r'(\b\d{4}\b)', r'<b>\1</b>', text)
    text = re.sub(r'((BKN|OVC)\d{3})', r'<b>\1</b>', text)
    text = re.sub(r'(\b(FG|TSRA|SN|FZRA|FZDZ|RA|DZ|TS|VIS|CLOUD|FOG|WIND|XWIND)\b)', r'<b>\1</b>', text)
    text = re.sub(r'(\b\d{3}\d{2}(G\d{2})?KT\b)', r'<b>\1</b>', text)
    return text

# 4. MASTER DATABASE [cite: 103-110]
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer", "spec": True},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer", "spec": False},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "RTM": {"icao": "EHRD", "lat": 51.957, "lon": 4.440, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "Cityflyer", "spec": False},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer", "spec": True},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 180, "fleet": "Cityflyer", "spec": True},
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "fleet": "Cityflyer", "spec": False},
    "GVA": {"icao": "LSGG", "lat": 46.237, "lon": 6.109, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "BER": {"icao": "EDDB", "lat": 52.362, "lon": 13.501, "rwy": 250, "fleet": "Cityflyer", "spec": False},
    "FRA": {"icao": "EDDF", "lat": 50.033, "lon": 8.571, "rwy": 250, "fleet": "Cityflyer", "spec": False},
    "LIN": {"icao": "LIML", "lat": 45.445, "lon": 9.277, "rwy": 360, "fleet": "Cityflyer", "spec": False},
    "MAD": {"icao": "LEMD", "lat": 40.494, "lon": -3.567, "rwy": 140, "fleet": "Cityflyer", "spec": False},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "JER": {"icao": "EGJJ", "lat": 49.208, "lon": -2.195, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer", "spec": True},
    "FNC": {"icao": "LPMA", "lat": 32.694, "lon": -16.774, "rwy": 50, "fleet": "Euroflyer", "spec": True},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "OPO": {"icao": "LPPR", "lat": 41.242, "lon": -8.678, "rwy": 350, "fleet": "Euroflyer", "spec": False},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "Euroflyer", "spec": False},
    "ALG": {"icao": "DAAG", "lat": 36.691, "lon": 3.215, "rwy": 230, "fleet": "Euroflyer", "spec": False},
}

# 5. DATA ENGINE (STABLE CORE) [cite: 113-120]
@st.cache_data(ttl=600)
def get_intel_global(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
            w_vis, w_cig, w_time, w_prob = 9999, 9999, "", False
            w_issues = []
            if t.data:
                for line in t.data.forecast:
                    v = line.visibility.value if line.visibility else 9999
                    c = 9999
                    if line.clouds:
                        for lyr in line.clouds:
                            if lyr.type in ['BKN', 'OVC'] and lyr.base: c = min(c, lyr.base * 100)
                    line_issues = []
                    if v < v_lim: line_issues.append("VIS")
                    if c < c_lim: line_issues.append("CLOUD")
                    if "TSRA" in line.raw: line_issues.append("TSRA")
                    if line_issues and (v < w_vis or c < w_cig):
                        w_vis, w_cig, w_issues, w_prob = v, c, line_issues, ("PROB" in line.raw)
                        w_time = f"{line.start_time.dt.strftime('%H')}-{line.end_time.dt.strftime('%H')}Z"
                        if v < v_lim: break
            res[iata] = {
                "vis": m.data.visibility.value if (m.data and m.data.visibility) else 9999,
                "cig": 9999, "w_dir": m.data.wind_direction.value if (m.data and m.data.wind_direction) else 0,
                "w_spd": m.data.wind_speed.value if (m.data and m.data.wind_speed) else 0,
                "w_gst": m.data.wind_gust.value if (m.data and m.data.wind_gust) else 0,
                "raw_m": m.raw or "N/A", "raw_t": t.raw or "N/A", "status": "online",
                "f_issues": w_issues, "f_time": w_time, "f_prob": w_prob
            }
            if m.data and m.data.clouds:
                for lyr in m.data.clouds:
                    if lyr.type in ['BKN', 'OVC'] and lyr.base: res[iata]["cig"] = min(res[iata]["cig"], lyr.base * 100)
        except: res[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A", "f_issues": []}
    return res

weather_data = get_intel_global(base_airports)

# 6. PROCESSING & MAPPING [cite: 121-128]
metar_alerts, taf_alerts, map_markers = {}, {}, []
for iata, info in base_airports.items():
    data = weather_data.get(iata)
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    color, m_issues, actual_str, forecast_str = "#008000", [], "STABLE", "NIL"
    xw = calculate_xwind(data.get('w_dir', 0), max(data.get('w_spd', 0), data.get('w_gst', 0)), info['rwy'])
    
    if data['status'] == "online":
        if data['vis'] < v_lim: m_issues.append("VIS"); color = "#d6001a"
        if data['cig'] < c_lim: m_issues.append("CLOUD"); color = "#d6001a"
        if xw >= 25: m_issues.append("XWIND"); color = "#d6001a"
        
        if m_issues: 
            actual_str = "/".join(m_issues)
            metar_alerts[iata] = {"type": actual_str, "hex": "primary" if color == "#d6001a" else "secondary"}
        if data['f_issues']:
            forecast_str = f"{'+'.join(data['f_issues'])} @ {data['f_time']}"
            taf_alerts[iata] = {"type": forecast_str, "hex": "primary" if "VIS" in str(data['f_issues']) else "secondary"}
            if color == "#008000": color = "#eb8f34"

    # Runway & Popup [cite: 127]
    r1 = int(info['rwy']/10); r2 = int(((info['rwy']+180)%360)/10)
    rwy_str = f"{min(r1,r2):02d}/{max(r1,r2):02d}"
    pop_html = f"""<div style="width:300px; color:black;"><b>{iata} Status</b><br>RWY {rwy_str} X-Wind: {xw}KT<br><b>ACTUAL:</b> {actual_str}<br><b>FORECAST:</b> {forecast_str}</div>"""
    map_markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "popup": pop_html})

# 7. MAIN UI RENDER
# Background Map
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter", zoom_control=False)
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=8, color=mkr['color'], fill=True, popup=folium.Popup(mkr['popup'], max_width=300)).add_to(m)

st_folium(m, width="100%", height=1200, key="fullscreen_map")

# HUD OVERLAYS
# TOP LEFT: Controls
st.markdown('<div class="hud-overlay top-left-panel"><div class="hud-title">🛠️ COMMAND CONTROLS</div>', unsafe_allow_html=True)
if st.button("🔄 REFRESH DATA"): st.cache_data.clear(); st.rerun()
st.markdown("---")
show_cf = st.checkbox("Cityflyer (CFE)", value=True)
show_ef = st.checkbox("Euroflyer (EFW)", value=True)
st.markdown('</div>', unsafe_allow_html=True)

# TOP RIGHT: Handover Log
st.markdown('<div class="hud-overlay top-right-panel"><div class="hud-title">📝 SHIFT HANDOVER</div>', unsafe_allow_html=True)
h_txt = f"HANDOVER {datetime.now().strftime('%H:%M')}Z\n" + "="*25 + "\n"
for iata, d in taf_alerts.items(): h_txt += f"{iata}: {d['type']}\n"
st.text_area("Handover:", value=h_txt, height=150, label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)

# BOTTOM CENTER: Alert Feed
st.markdown('<div class="hud-overlay bottom-center-panel"><div class="hud-title">🚨 LIVE NETWORK ALERTS</div>', unsafe_allow_html=True)
alert_cols = st.columns(8)
all_combined = {**metar_alerts, **taf_alerts}
for i, (iata, d) in enumerate(all_combined.items()):
    with alert_cols[i % 8]:
        st.button(f"**{iata}**\n{d['type']}", key=f"btn_{iata}", type=d['hex'])
st.markdown('</div>', unsafe_allow_html=True)
