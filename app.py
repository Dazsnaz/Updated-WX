import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. HUD STYLING
st.markdown("""
    <style>
    .section-header { color: #002366 !important; font-weight: bold; font-size: 1.5rem; margin-top: 20px; border-bottom: 2px solid #d6001a; padding-bottom: 5px; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    [data-testid="stTextArea"] textarea { color: #002366 !important; background-color: #ffffff !important; font-weight: bold; font-family: 'Courier New', monospace; }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 280px !important; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold !important; }
    
    /* Input visibility */
    div[data-baseweb="select"] > div, .stSelectbox div, input {
        background-color: #ffffff !important; color: #002366 !important; font-weight: bold !important;
    }

    /* CONCISE ALERT BUTTONS */
    .stButton > button { 
        background-color: #005a9c !important; color: white !important; border: 1px solid white !important; 
        width: 100%; text-transform: uppercase; font-size: 0.72rem !important; height: 50px !important; 
        line-height: 1.1 !important; white-space: nowrap !important; overflow: hidden;
        text-overflow: ellipsis; display: flex; align-items: center; justify-content: center; 
        text-align: center; padding: 2px 10px !important;
    }
    
    .ba-header { background-color: #002366; padding: 20px; border-radius: 5px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
    div.stButton > button[kind="primary"] { background-color: #d6001a !important; }
    div.stButton > button[kind="secondary"] { background-color: #eb8f34 !important; }
    .reason-box { background-color: #ffffff; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; color: #002366 !important; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .limits-table { width: 100%; font-size: 0.8rem; border-collapse: collapse; margin-top: 10px; color: white !important; }
    .limits-table td, .limits-table th { border: 1px solid rgba(255,255,255,0.2); padding: 4px; text-align: left; }
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
    # Highlight specific hazards only (No Rain/Drizzle)
    text = re.sub(r'(\b(FG|TSRA|SN|-SN|FZRA|FZDZ|TS|VIS|CLOUD|FOG|XWIND|WIND)\b)', r'<b>\1</b>', text)
    text = re.sub(r'(\b\d{3}\d{2}(G\d{2})?KT\b)', r'<b>\1</b>', text)
    return text

# 4. MASTER DATABASE
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
    "MAD": {"icao": "LEMD", "lat": 40.494, "lon": -3.567, "rwy": 140, "fleet": "Cityflyer", "spec": False},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "JER": {"icao": "EGJJ", "lat": 49.208, "lon": -2.195, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "ALC": {"icao": "LEAL", "lat": 38.282, "lon": -0.558, "rwy": 100, "fleet": "Euroflyer", "spec": False},
}

# 5. SESSION STATE
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

# 6. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND SETTINGS")
    if st.button("🔄 MANUAL DATA REFRESH"):
        st.cache_data.clear(); st.rerun()
    st.markdown("---")
    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)
    map_theme = st.radio("MAP THEME", ["Dark Mode", "Light Mode"])
    st.markdown("---")
    st.markdown("📊 **FLEET X-WIND LIMITS**")
    st.markdown("""<table class="limits-table"><tr><th>FLEET</th><th>DRY</th><th>WET</th></tr><tr><td><b>A320/321</b></td><td>38 kt</td><td>33 kt</td></tr><tr><td><b>E190/170</b></td><td>30 kt</td><td>25 kt</td></tr></table>""", unsafe_allow_html=True)

# 7. BACKGROUND FETCH
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
                    l_raw = line.raw.upper()
                    l_issues = []
                    v = line.visibility.value if line.visibility else 9999
                    c = 9999
                    if line.clouds:
                        for lyr in line.clouds:
                            if lyr.type in ['BKN', 'OVC'] and lyr.base: c = min(c, lyr.base * 100)
                    
                    # WINTER/FOG TRIGGER (NO RA/DZ)
                    if any(x in l_raw for x in ["SN", "FZRA", "FZDZ"]): l_issues.append("WINTER")
                    if "FG" in l_raw: l_issues.append("FOG")
                    if "TS" in l_raw: l_issues.append("TSRA")
                    if v < v_lim: l_issues.append("VIS")
                    if c < c_lim: l_issues.append("CLOUD")
                    
                    if l_issues:
                        if not w_issues or v < w_vis or c < w_cig or "WINTER" in l_issues:
                            w_vis, w_cig, w_issues, w_prob = v, c, l_issues, ("PROB" in l_raw)
                            w_time = f"{line.start_time.dt.strftime('%H')}-{line.end_time.dt.strftime('%H')}Z"
            
            res[iata] = {
                "raw_m": m.raw or "N/A", "raw_t": t.raw or "N/A", "status": "online",
                "vis": m.data.visibility.value if (m.data and m.data.visibility) else 9999,
                "w_dir": m.data.wind_direction.value if (m.data and m.data.wind_direction) else 0,
                "w_spd": m.data.wind_speed.value or 0, "w_gst": m.data.wind_gust.value or 0,
                "f_issues": w_issues, "f_time": w_time, "f_prob": w_prob
            }
            if m.data and m.data.clouds:
                for lyr in m.data.clouds:
                    if lyr.type in ['BKN', 'OVC'] and lyr.base: res[iata]["cig"] = min(res[iata].get("cig", 9999), lyr.base * 100)
        except: res[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A", "f_issues": []}
    return res

weather_data = get_intel_global(base_airports)

# 8. FILTER & UI LOOP
metar_alerts, taf_alerts, green_stations, map_markers = {}, {}, [], []
for iata, info in base_airports.items():
    data = weather_data.get(iata)
    if not data: continue
    
    # Pre-Initialize popup variables to prevent NameError
    is_shown = (info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    color, m_issues, actual_str, forecast_str = "#008000", [], "STABLE", "NIL"
    xw = 0
    r1, r2 = int(info['rwy']/10), int(((info['rwy']+180)%360)/10)

    if data['status'] == "online":
        xw = calculate_xwind(data.get('w_dir', 0), max(data.get('w_spd', 0), data.get('w_gst', 0)), info['rwy'])
        raw_m = data['raw_m'].upper()
        
        # ACTUAL ALERTS (Explicit Hazards Only)
        if any(x in raw_m for x in [" SN ", "-SN ", "FZRA", "FZDZ"]): m_issues.append("WINTER"); color = "#d6001a"
        if "FG" in raw_m: m_issues.append("FOG"); color = "#d6001a" if data['vis'] < v_lim else "#eb8f34"
        if data['vis'] < v_lim: m_issues.append("VIS"); color = "#d6001a"
        if data.get("cig", 9999) < c_lim: m_issues.append("CLOUD"); color = "#d6001a"
        if xw >= 25: m_issues.append("XWIND"); color = "#d6001a"
        
        if is_shown:
            if m_issues: 
                actual_str = "/".join(m_issues)
                metar_alerts[iata] = {"type": actual_str, "hex": "primary"}
            else: green_stations.append(iata)
            
            if data['f_issues']:
                p_tag = " prob" if data['f_prob'] else ""
                forecast_str = f"{'+'.join(data['f_issues'])}{p_tag} @ {data['f_time']}"
                taf_alerts[iata] = {"type": "+".join(data['f_issues']), "time": data['f_time'], "prob": data['f_prob'], "hex": "secondary"}
                if color == "#008000": color = "#eb8f34"

    if is_shown:
        m_bold, t_bold = bold_hazard(data.get('raw_m', 'N/A')), bold_hazard(data.get('raw_t', 'N/A'))
        popup_html = f"""<div style="width:600px; color:black !important; font-family:monospace; font-size:14px;"><b style="color:#002366; font-size:18px;">{iata} STATUS</b><div style="margin-top:8px; padding:10px; border-left:6px solid {color}; background:#f9f9f9; font-size:16px;"><b style="color:#002366;">RWY {r1:02d}/{r2:02d} Live X-Wind:</b> <span style="color:{'#d6001a' if xw >= 25 else 'black'}; font-weight:bold;">{xw} KT</span><br><b>ACTUAL:</b> {actual_str}<br><b>FORECAST:</b> {forecast_str}</div><hr><div style="display:flex; gap:12px;"><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>METAR</b><br>{m_bold}</div><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>TAF</b><br>{t_bold}</div></div></div>"""
        map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "popup": popup_html})

# --- UI ---
st.markdown(f'<div class="ba-header"><div>OCC WINTER HUD (V14.2 STABLE ENGINE)</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter", scrollWheelZoom=False)
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(mkr['popup'], max_width=700)).add_to(m)
st_folium(m, width=1200, height=1200, key="map_v187")

st.markdown('<div class="section-header">🔴 Actual Alerts (METAR)</div>', unsafe_allow_html=True)
if metar_alerts:
    cols = st.columns(5)
    for i, (iata, d) in enumerate(metar_alerts.items()):
        with cols[i % 5]:
            if st.button(f"{iata} NOW {d['type']}", key=f"m_{iata}", type="primary"): st.session_state.investigate_iata = iata

st.markdown('<div class="section-header">🟠 Forecast Alerts (TAF)</div>', unsafe_allow_html=True)
if taf_alerts:
    cols_f = st.columns(5)
    for i, (iata, d) in enumerate(taf_alerts.items()):
        with cols_f[i % 5]:
            p_tag = " prob" if d['prob'] else ""
            if st.button(f"{iata} {d['time']} {d['type']}{p_tag}", key=f"f_{iata}", type="secondary"): st.session_state.investigate_iata = iata

# 11. ANALYSIS
if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d, info = weather_data.get(iata, {}), base_airports.get(iata, {"rwy": 0, "lat": 0, "lon": 0})
    issue_desc = (taf_alerts.get(iata, {}) or metar_alerts.get(iata, {}) or {}).get('type', "STABLE")
    xw_val = calculate_xwind(d.get('w_dir', 0), max(d.get('w_spd', 0), d.get('w_gst', 0)), info['rwy'])
    impact = "Standard operations."
    if "VIS" in issue_desc or "CLOUD" in issue_desc: impact = "LVP procedures likely. CAT III currency required."
    elif "WINTER" in issue_desc: impact = "Winter precipitation hazards. Embraer/Airbus de-icing required."
    elif "XWIND" in issue_desc: impact = "Critical crosswind (>=25kt). Check runway state."

    alt_iata, min_dist = "None", 9999
    for g in green_stations:
        if g != iata:
            dist = calculate_dist(info['lat'], info['lon'], base_airports[g]['lat'], base_airports[g]['lon'])
            if dist < min_dist: min_dist = dist; alt_iata = g
    st.markdown(f"""<div class="reason-box"><h3>{iata} Strategy Brief: {issue_desc}</h3><p><b>WX Summary:</b> Live crosswind <b>{xw_val}kt</b> for RWY {info['rwy']}°. <b>Impact:</b> {impact}</p><p style="color:#d6001a !important; font-size:1.1rem;"><b>✈️ Strategic Alternate:</b> {alt_iata} ({min_dist} NM).</p><hr><div style="display:flex; gap:20px;"><div style="flex:1;"><b>METAR:</b><br><small>{bold_hazard(d.get('raw_m'))}</small></div><div style="flex:1;"><b>TAF:</b><br><small>{bold_hazard(d.get('raw_t'))}</small></div></div></div>""", unsafe_allow_html=True)
    if st.button("Close Analysis"): st.session_state.investigate_iata = "None"; st.rerun()
