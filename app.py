import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
from datetime import datetime, timedelta, timezone

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. HUD STYLING (V29.2 CSS BASE + REINFORCED SIDEBAR WHITE)
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    
    .ba-header { 
        background-color: #002366 !important; color: #ffffff !important; 
        padding: 20px; border-radius: 8px; margin-bottom: 20px; 
        border: 2px solid #d6001a; display: flex; justify-content: space-between;
    }

    /* SIDEBAR - FORCED WHITE */
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 320px !important; border-right: 3px solid #d6001a; }
    [data-testid="stSidebar"] label p, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span { color: #ffffff !important; font-weight: bold !important; }

    /* DROPDOWNS - NAVY ON WHITE */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] { background-color: white !important; }
    div[data-testid="stSelectbox"] * { color: #002366 !important; font-weight: 800 !important; }
    [data-baseweb="popover"] * { color: #002366 !important; background-color: white !important; font-weight: bold !important; }

    /* ALERT TABS - v29.2 SHADES */
    .stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; border: 1px solid white !important; }
    .stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; border: 1px solid white !important; }

    /* STRATEGY BRIEF - CONTAINER ONLY */
    .reason-box { 
        background-color: #ffffff !important; 
        border: 1px solid #ddd; padding: 25px; border-radius: 5px; 
        margin-top: 20px; border-top: 10px solid #d6001a; 
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    
    /* UNIVERSAL NAVY FORCE FOR HTML BLOCKS */
    .navy-force { color: #002366 !important; }
    .navy-force * { color: #002366 !important; }

    .section-header { color: #ffffff !important; background-color: #002366; padding: 10px; border-left: 10px solid #d6001a; font-weight: bold; font-size: 1.5rem; margin-top: 30px; }
    .leaflet-tooltip, .leaflet-popup-content-wrapper { background: white !important; border: 2px solid #002366 !important; padding: 0 !important; opacity: 1 !important; box-shadow: 0 10px 30px rgba(0,0,0,0.5) !important; min-width: 580px !important; white-space: normal !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_dist(lat1, lon1, lat2, lon2):
    R = 3440.065 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)

def get_xw_component(wind_dir, wind_spd, rwy_hdg):
    if wind_dir is None or wind_spd is None or rwy_hdg is None: return 0
    return round(abs(wind_spd * math.sin(math.radians(wind_dir - rwy_hdg))))

def calculate_best_xwind(wind_dir, wind_spd, rwy_hdg_base):
    xw1 = get_xw_component(wind_dir, wind_spd, rwy_hdg_base)
    xw2 = get_xw_component(wind_dir, wind_spd, (rwy_hdg_base + 180) % 360)
    return min(xw1, xw2)

def bold_hazard(text):
    if not text or text == "N/A": return text
    text = re.sub(r'\b(TEMPO|BECMG|PROB\d{2}|NOSIG|CAVOK)\b', r'<b>\1</b>', text)
    text = re.sub(r'(\b\d{4}/\d{4}\b)', r'<b>\1</b>', text)
    text = re.sub(r'(\b\d{3}\d{2}G\d{2,3}KT\b)', r'<b>\1</b>', text)
    text = re.sub(r'(\b(FG|TSRA|SN|-SN|FZRA|FZDZ|TS|FOG)\b)', r'<b>\1</b>', text)
    text = re.sub(r'\b((?:BKN|OVC)00[0-9])\b', r'<b>\1</b>', text)
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
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer", "spec": True},
    "FNC": {"icao": "LPMA", "lat": 32.694, "lon": -16.774, "rwy": 50, "fleet": "Euroflyer", "spec": True},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "Euroflyer", "spec": False},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    # STRATEGIC ALTS (Background Only)
    "PSA": {"icao": "LIRP", "lat": 43.683, "lon": 10.395, "rwy": 220, "fleet": "Special", "hide_map": True},
    "BLQ": {"icao": "LIPE", "lat": 44.535, "lon": 11.288, "rwy": 300, "fleet": "Special", "hide_map": True},
    "MUC": {"icao": "EDDM", "lat": 48.353, "lon": 11.786, "rwy": 260, "fleet": "Special", "hide_map": True},
    "PSO": {"icao": "LPPS", "lat": 33.071, "lon": -16.350, "rwy": 360, "fleet": "Special", "hide_map": True},
}

# 5. SESSION STATE
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

# 6. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 MANUAL DATA REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    time_horizon = st.radio("SCAN WINDOW", ["Next 6 Hours", "Next 12 Hours", "Next 24 Hours"])
    xw_limit = st.slider("X-WIND ALERT (KT)", 15, 35, 25)
    hazard_filter = st.selectbox("ISOLATE HAZARD", ["Show All Network", "Any Amber/Red Alert", "XWIND", "WINDY", "FOG", "WINTER", "TSRA", "VIS", "LOW CLOUD"])
    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)
    map_theme = st.radio("MAP THEME", ["Dark Mode", "Light Mode"])

# 7. DATA FETCH
@st.cache_data(ttl=1800)
def get_raw_weather_master(airport_dict):
    raw_res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            raw_res[iata] = {"m_obj": m, "t_obj": t, "status": "online"}
        except: raw_res[iata] = {"status": "offline"}
    return raw_res

raw_weather_bundle = get_raw_weather_master(base_airports)

# 8. PROCESSOR
def process_weather_for_horizon(bundle, airport_dict, horizon_limit, xw_threshold):
    processed = {}
    cutoff_time = datetime.now(timezone.utc) + timedelta(hours=horizon_limit)
    for iata, data in bundle.items():
        if data['status'] == "offline" or "m_obj" not in data:
            processed[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A", "f_issues": [], "f_wind_spd":0, "f_wind_dir":0, "f_prob": False}
            continue
        m, t, info = data['m_obj'], data['t_obj'], airport_dict[iata]
        m_vis = getattr(m.data.visibility, 'value', 9999) if (m.data and m.data.visibility) else 9999
        m_w_dir = getattr(m.data.wind_direction, 'value', 0) if (m.data and m.data.wind_direction) else 0
        m_w_spd = getattr(m.data.wind_speed, 'value', 0) if (m.data and m.data.wind_speed) else 0
        m_w_gst = getattr(m.data.wind_gust, 'value', 0) if (m.data and m.data.wind_gust) else 0
        
        w_issues, f_wind_spd, f_wind_dir, w_time, w_prob = [], 0, 0, "", False
        if t.data:
            for line in t.data.forecast:
                if not line.start_time or not hasattr(line.start_time, 'dt'): continue
                if line.start_time.dt > cutoff_time: continue
                l_raw = line.raw.upper()
                l_issues_local = []
                l_dir = getattr(line.wind_direction, 'value', info.get('rwy',0)) if line.wind_direction else info.get('rwy',0)
                l_spd = getattr(line.wind_speed, 'value', 0) if line.wind_speed else 0
                l_gst = getattr(line.wind_gust, 'value', 0) if line.wind_gust else 0
                peak = max(l_spd, l_gst)
                if calculate_best_xwind(l_dir, peak, info.get('rwy',0)) >= xw_threshold: l_issues_local.append("XWIND")
                if re.search(r'\bSN\b|\bFZ|\bPL\b', l_raw): l_issues_local.append("WINTER")
                if l_issues_local:
                    for iss in l_issues_local:
                        if iss not in w_issues: w_issues.append(iss)
                    f_wind_spd, f_wind_dir = peak, l_dir
                    w_time = f"{line.start_time.dt.strftime('%H')}Z"
                    if "PROB" in l_raw: w_prob = True

        processed[iata] = {"vis": m_vis, "status": "online", "w_dir": m_w_dir, "w_spd": m_w_spd, "w_gst": m_w_gst, "raw_m": m.raw or "N/A", "raw_t": t.raw or "N/A", "f_issues": w_issues, "f_time": w_time, "f_wind_spd": f_wind_spd, "f_wind_dir": f_wind_dir, "f_prob": w_prob}
    return processed

weather_data = process_weather_for_horizon(raw_weather_bundle, base_airports, 6, xw_limit)

# 9. UI LOOP
metar_alerts, taf_alerts, green_stations, map_markers = {}, {}, [], []
for iata, info in base_airports.items():
    data = weather_data.get(iata)
    if not data or info.get('hide_map'): continue
    cur_xw = calculate_best_xwind(data.get('w_dir', 0), max(data.get('w_spd', 0), data.get('w_gst', 0)), info['rwy'])
    m_issues = []
    if re.search(r'\bSN\b|\bFZ|\bPL\b', data['raw_m'].upper()): m_issues.append("WINTER")
    if re.search(r'\bFG\b', data['raw_m'].upper()): m_issues.append("FOG")
    if cur_xw >= xw_limit: m_issues.append("XWIND")
    
    actual_haz, fore_haz = len(m_issues) > 0, len(data['f_issues']) > 0
    color = "#008000"
    if actual_haz: color = "#d6001a" if any(x in m_issues for x in ["WINTER","FOG","XWIND"]) else "#eb8f34"
    elif fore_haz: color = "#eb8f34"
    if not actual_haz and not fore_haz: green_stations.append(iata)
    if not ((info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)): continue

    trend_icon = "📈" if (not actual_haz and fore_haz) else ("📉" if (actual_haz and not fore_haz) else "➡️")
    rwy_text = f"RWY {int(info['rwy']/10):02d}/{int(((info['rwy']+180)%360)/10):02d}"
    if actual_haz: metar_alerts[iata] = {"type": "/".join(m_issues), "hex": "primary" if color == "#d6001a" else "secondary"}
    if fore_haz: taf_alerts[iata] = {"type": "+".join(data['f_issues']), "time": data['f_time'], "hex": "secondary"}
    m_bold, t_bold = bold_hazard(data['raw_m']), bold_hazard(data['raw_t'])
    shared_content = f"""<div style="width:580px; background:white; padding:15px; border-radius:5px; color:#002366 !important;"><b style="font-size:18px;">{iata} STATUS {trend_icon}</b><div style="margin-top:8px; padding:10px; border-left:6px solid {color}; background:#f9f9f9; font-size:16px;"><b>{rwy_text} Best XW:</b> <b>{cur_xw} KT</b><br><b>ACTUAL:</b> {"/".join(m_issues) if m_issues else "STABLE"}<br><b>FORECAST:</b> {"+".join(data['f_issues']) if data['f_issues'] else "NIL"}</div><hr style="border:1px solid #ddd;"><div style="display:flex; gap:12px;"><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; white-space: pre-wrap; word-wrap: break-word;"><b>METAR</b><br>{m_bold}</div><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; white-space: pre-wrap; word-wrap: break-word;"><b>TAF</b><br>{t_bold}</div></div></div>"""
    map_markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "content": shared_content, "iata": iata, "trend": trend_icon})

# 10. UI RENDER
st.markdown(f'<div class="ba-header"><div>OCC HUD v32.0</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles=("CartoDB dark_matter" if map_theme == "Dark Mode" else "CartoDB positron"), scrollWheelZoom=False)
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(mkr['content'], max_width=650, auto_pan=True, auto_pan_padding=(150, 150)), tooltip=folium.Tooltip(mkr['content'], direction='top', sticky=False)).add_to(m)
st_folium(m, width=1200, height=1200, key="map_final_build_v32")

# 11. ALERTS
st.markdown('<div class="section-header">🔴 Actual Alerts (METAR)</div>', unsafe_allow_html=True)
if metar_alerts:
    cols = st.columns(5)
    for i, (iata, d) in enumerate(metar_alerts.items()):
        with cols[i % 5]:
            if st.button(f"{iata} NOW {d['type']}", key=f"m_{iata}", type=d['hex']): st.session_state.investigate_iata = iata
st.markdown(f'<div class="section-header">🟠 Forecast Alerts</div>', unsafe_allow_html=True)
if taf_alerts:
    cols_f = st.columns(5)
    for i, (iata, d) in enumerate(taf_alerts.items()):
        with cols_f[i % 5]:
            if st.button(f"{iata} {d['time']} {d['type']}", key=f"f_{iata}", type="secondary"): st.session_state.investigate_iata = iata

# 12. STRATEGY BRIEF (v32.0 ABSOLUTE HTML LOCK)
if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d, info = weather_data.get(iata, {}), base_airports.get(iata, {"rwy": 0, "lat": 0, "lon": 0})
    r1, r2 = int(info['rwy']/10), int(((info['rwy']+180)%360)/10)
    
    st.markdown('<div class="reason-box">', unsafe_allow_html=True)
    st.markdown(f'<div class="navy-force" style="font-size:24px; font-weight:900; margin-bottom:15px;">{iata} Strategic Intelligence Brief</div>', unsafe_allow_html=True)
    
    # Selection Toggle (The ONLY streamlit widget - uses specific CSS to keep label navy)
    sel_rwy = st.radio("Toggle Runway Direction:", [f"RWY {r1:02d}", f"RWY {r2:02d}"], horizontal=True)
    target_hdg = info['rwy'] if f"{r1:02d}" in sel_rwy else (info['rwy']+180)%360
    final_xw = get_xw_component(d.get('w_dir', 0), max(d.get('w_spd', 0), d.get('w_gst', 0)), target_hdg)
    
    # Forced HTML Body
    brief_html = f"""
    <div class="navy-force" style="display:flex; gap:40px; margin-top:20px;">
        <div style="flex:1;">
            <p style="font-size:16px;"><b>Active Hazards:</b> {(taf_alerts.get(iata, {}) or metar_alerts.get(iata, {}) or {{'type': 'STABLE'}}).get('type')}</p>
            <p style="font-size:16px;"><b>Current Selection:</b> {sel_rwy} | <b>Crosswind Component: {final_xw}kt</b></p>
            <p style="margin-top:15px; font-weight:bold;">Network Preferred Alternates:</p>
            <table class="alt-table">
                <tr><th>Alternate</th><th>Dist (NM)</th><th>Best XW</th><th>Status</th></tr>
                {"".join([f'<tr><td><b>{g}</b></td><td>{calculate_dist(info["lat"], info["lon"], base_airports[g]["lat"], base_airports[g]["lon"])} NM</td><td>{weather_data[g].get("w_spd",0)} kt</td><td>OK</td></tr>' for g in green_stations[:3]])}
            </table>
        </div>
        <div style="flex:1;">
            <b style="display:block; margin-bottom:5px;">LIVE METAR DATA</b>
            <div class="wx-container" style="background:#f0f2f6; padding:10px; border-radius:5px; border-left:5px solid #002366; font-family:monospace;">{bold_hazard(d.get('raw_m'))}</div>
            <b style="display:block; margin-top:15px; margin-bottom:5px;">LIVE TAF DATA</b>
            <div class="wx-container" style="background:#f0f2f6; padding:10px; border-radius:5px; border-left:5px solid #002366; font-family:monospace;">{bold_hazard(d.get('raw_t'))}</div>
        </div>
    </div>"""
    st.markdown(brief_html, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    if st.button("Close Strategy Brief"): st.session_state.investigate_iata = "None"; st.rerun()

# 13. LOG
st.markdown('<div class="section-header">📝 Shift Handover Log</div>', unsafe_allow_html=True)
h_txt = f"HANDOVER {datetime.now().strftime('%H:%M')}Z\n" + "="*50 + "\n"
for i_ata, d_taf in taf_alerts.items(): h_txt += f"{i_ata}: {d_taf['type']} ({d_taf['time']})\n"
st.text_area("Log:", value=h_txt, height=200, key="log_v32", label_visibility="collapsed")
