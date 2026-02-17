import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
from datetime import datetime, timedelta, timezone

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. STABLE v29.2 CSS
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    
    .ba-header { 
        background-color: #002366 !important; color: #ffffff !important; 
        padding: 20px; border-radius: 8px; margin-bottom: 20px; 
        border: 2px solid #d6001a; display: flex; justify-content: space-between;
    }

    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 320px !important; border-right: 3px solid #d6001a; }
    [data-testid="stSidebar"] label p { color: #ffffff !important; font-weight: bold; }

    div[data-testid="stSelectbox"] div[data-baseweb="select"] { background-color: white !important; }
    div[data-testid="stSelectbox"] * { color: #002366 !important; font-weight: 800 !important; }
    [data-baseweb="popover"] * { color: #002366 !important; background-color: white !important; font-weight: bold !important; }

    .stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }
    .stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }

    .reason-box { background-color: #ffffff !important; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .reason-box * { color: #002366 !important; }
    
    /* v34.0 Specific Radio Lock for Runway Selection */
    .reason-box [data-testid="stWidgetLabel"] p, .reason-box .stRadio label p { color: #002366 !important; font-weight: bold !important; }

    .section-header { color: #ffffff !important; background-color: #002366; padding: 10px; border-left: 10px solid #d6001a; font-weight: bold; font-size: 1.5rem; margin-top: 30px; }
    .leaflet-tooltip, .leaflet-popup-content-wrapper { background: white !important; border: 2px solid #002366 !important; padding: 0 !important; opacity: 1 !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_dist(lat1, lon1, lat2, lon2):
    R = 3440.065 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)

def calculate_xwind(wind_dir, wind_spd, rwy_hdg):
    if wind_dir is None or wind_spd is None or rwy_hdg is None: return 0
    return round(abs(wind_spd * math.sin(math.radians(wind_dir - rwy_hdg))))

def bold_hazard(text):
    if not text or text == "N/A": return text
    text = re.sub(r'\b(TEMPO|BECMG|PROB\d{2}|NOSIG|CAVOK)\b', r'<b>\1</b>', text)
    text = re.sub(r'(\b\d{3}\d{2}G\d{2,3}KT\b)', r'<b>\1</b>', text)
    text = re.sub(r'(\b(FG|TSRA|SN|-SN|FZRA|FZDZ|TS|FOG)\b)', r'<b>\1</b>', text)
    return text

# 4. FULL DATABASE (47+ Network)
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
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "fleet": "Cityflyer", "spec": False},
    "GVA": {"icao": "LSGG", "lat": 46.237, "lon": 6.109, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer", "spec": True},
    "FNC": {"icao": "LPMA", "lat": 32.694, "lon": -16.774, "rwy": 50, "fleet": "Euroflyer", "spec": True},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "Euroflyer", "spec": False},
    # Diversion Network
    "PSA": {"icao": "LIRP", "lat": 43.683, "lon": 10.395, "rwy": 220, "fleet": "Special", "hide": True},
    "MUC": {"icao": "EDDM", "lat": 48.353, "lon": 11.786, "rwy": 260, "fleet": "Special", "hide": True},
    "PSO": {"icao": "LPPS", "lat": 33.071, "lon": -16.350, "rwy": 360, "fleet": "Special", "hide": True},
}

# 5. SESSION STATE
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

# 6. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 MANUAL DATA REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    time_horizon = st.radio("SCAN WINDOW", ["Next 6 Hours", "Next 12 Hours", "Next 24 Hours"], index=0)
    horizon_hours = 6 if "6" in time_horizon else (12 if "12" in time_horizon else 24)
    xw_limit = st.slider("X-WIND LIMIT (KT)", 15, 35, 25)
    hazard_filter = st.selectbox("ISOLATE HAZARD", ["Show All", "XWIND", "FOG", "WINTER"])
    show_cf = st.checkbox("Cityflyer", value=True)
    show_ef = st.checkbox("Euroflyer", value=True)

# 7. DATA FETCH
@st.cache_data(ttl=1800)
def get_weather(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            res[iata] = {"m_obj": m, "t_obj": t, "status": "online"}
        except: res[iata] = {"status": "offline"}
    return res

weather_bundle = get_weather(base_airports)

# 8. PROCESSOR (Resilience Patch)
def process_data(bundle, airport_dict, horizon, xw_thresh):
    proc = {}
    cutoff = datetime.now(timezone.utc) + timedelta(hours=horizon)
    for iata, data in bundle.items():
        if data['status'] == "offline": continue
        m, t, info = data['m_obj'], data['t_obj'], airport_dict[iata]
        
        m_w_dir = getattr(m.data.wind_direction, 'value', 0) if (m.data and m.data.wind_direction) else 0
        m_w_spd = getattr(m.data.wind_speed, 'value', 0) if (m.data and m.data.wind_speed) else 0
        m_w_gst = getattr(m.data.wind_gust, 'value', 0) if (m.data and m.data.wind_gust) else 0
        
        f_issues, f_time = [], ""
        if t.data:
            for line in t.data.forecast:
                l_issues = []
                if not line.start_time or line.start_time.dt > cutoff: continue
                l_dir = getattr(line.wind_direction, 'value', info.get('rwy', 0)) if line.wind_direction else info.get('rwy', 0)
                peak = max(getattr(line.wind_speed, 'value', 0), getattr(line.wind_gust, 'value', 0))
                if calculate_xwind(l_dir, peak, info.get('rwy', 0)) >= xw_thresh: l_issues.append("XWIND")
                if re.search(r'\bSN\b|\bFZ', line.raw.upper()): l_issues.append("WINTER")
                if l_issues:
                    for iss in l_issues:
                        if iss not in f_issues: f_issues.append(iss)
                    f_time = f"{line.start_time.dt.strftime('%H')}Z"

        proc[iata] = {"w_dir": m_w_dir, "w_spd": m_w_spd, "w_gst": m_w_gst, "raw_m": m.raw, "raw_t": t.raw, "f_issues": f_issues, "f_time": f_time}
    return proc

weather_data = process_data(weather_bundle, base_airports, horizon_hours, xw_limit)

# 9. UI LOOP
metar_alerts, taf_alerts, markers, green_stations = {}, {}, [], []
for iata, info in base_airports.items():
    d = weather_data.get(iata)
    if not d: continue
    xw = calculate_xwind(d['w_dir'], max(d['w_spd'], d['w_gst']), info.get('rwy', 0))
    m_issues = []
    if xw >= xw_limit: m_issues.append("XWIND")
    if re.search(r'\bSN\b|\bFZ', d['raw_m'].upper()): m_issues.append("WINTER")
    
    color = "#008000"
    if m_issues: color = "#d6001a" if any(x in m_issues for x in ["WINTER","XWIND"]) else "#eb8f34"
    elif d['f_issues']: color = "#eb8f34"
    if color == "#008000": green_stations.append(iata)

    if info.get('hide'): continue
    if not ((info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)): continue
    if m_issues: metar_alerts[iata] = {"type": "/".join(m_issues), "hex": "primary" if color == "#d6001a" else "secondary"}
    if d['f_issues']: taf_alerts[iata] = {"type": "+".join(d['f_issues']), "time": d['f_time']}

    content = f"""<div style="width:580px; background:white; padding:15px; border-radius:5px; color:#002366 !important;"><b>{iata} STATUS</b><hr><b>Actual XW:</b> {xw} KT<br><b>METAR:</b> {bold_hazard(d['raw_m'])}<br><b>TAF:</b> {bold_hazard(d['raw_t'])}</div>"""
    markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "content": content})

# 10. RENDER
st.markdown(f'<div class="ba-header"><div>OCC HUD v34.0</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter")
for mkr in markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(mkr['content'], max_width=600)).add_to(m)
st_folium(m, width=1200, height=800)

st.markdown('<div class="section-header">🔴 Actual Alerts</div>', unsafe_allow_html=True)
if metar_alerts:
    cols = st.columns(5)
    for i, (iata, al) in enumerate(metar_alerts.items()):
        with cols[i % 5]:
            if st.button(f"{iata}: {al['type']}", key=f"m_{iata}", type=al['hex']): st.session_state.investigate_iata = iata

# 11. STRATEGY BRIEF (v29.2 Foundation + Selection Fix)
if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d, info = weather_data.get(iata), base_airports.get(iata)
    
    if info and 'rwy' in info:
        r1, r2 = int(info['rwy']/10), int(((info['rwy']+180)%360)/10)
        st.markdown('<div class="reason-box">', unsafe_allow_html=True)
        st.markdown(f'<h3>{iata} Strategic Brief</h3>', unsafe_allow_html=True)
        
        # Selection using st.radio with forced navy CSS label visibility
        sel_rwy = st.radio("Manual Runway Selection:", [f"RWY {r1:02d}", f"RWY {r2:02d}"], horizontal=True)
        target_hdg = info['rwy'] if f"{r1:02d}" in sel_rwy else (info['rwy']+180)%360
        final_xw = calculate_xwind(d['w_dir'], max(d['w_spd'], d['w_gst']), target_hdg)
        
        st.markdown(f"""
            <div style="display:flex; gap:40px; margin-top:15px; color:#002366 !important;">
                <div style="flex:1;">
                    <p><b>Active Hazards:</b> {(taf_alerts.get(iata, {}) or metar_alerts.get(iata, {}) or {'type':'STABLE'})['type']}</p>
                    <p><b>Selected Crosswind ({sel_rwy}): {final_xw}kt</b></p>
                    <p style="margin-top:15px; font-weight:bold;">Tactical Alternates:</p>
                    <table style="width:100%; border-collapse:collapse; color:#002366 !important;">
                        <tr style="border-bottom:2px solid #002366; text-align:left;"><th>Alternate</th><th>NM</th><th>Best XW</th></tr>
                        {"".join([f"<tr><td><b>{g}</b></td><td>{calculate_dist(info['lat'], info['lon'], base_airports[g]['lat'], base_airports[g]['lon'])}</td><td>{calculate_xwind(weather_data[g]['w_dir'], weather_data[g]['w_spd'], base_airports[g]['rwy'])} kt</td></tr>" for g in green_stations[:3]])}
                    </table>
                </div>
                <div style="flex:1;">
                    <div style="padding:10px; background:#f9f9f9; border-radius:5px; border-left:4px solid #002366; margin-bottom:10px;">
                        <b>LIVE METAR</b><br><code>{bold_hazard(d['raw_m'])}</code>
                    </div>
                    <div style="padding:10px; background:#f9f9f9; border-radius:5px; border-left:4px solid #002366;">
                        <b>LIVE TAF</b><br><code>{bold_hazard(d['raw_t'])}</code>
                    </div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)
        if st.button("CLOSE BRIEF"): st.session_state.investigate_iata = "None"; st.rerun()
