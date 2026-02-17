import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
from datetime import datetime, timedelta, timezone

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. EXACT v29.2 CSS FOUNDATION + v33.3 RADIO LOCK
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

    /* DROPDOWNS (NAVY-ON-WHITE) */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] { background-color: white !important; }
    div[data-testid="stSelectbox"] * { color: #002366 !important; font-weight: 800 !important; }
    [data-baseweb="popover"] * { color: #002366 !important; background-color: white !important; font-weight: bold !important; }

    /* ALERT TABS (v29.2 SHADES) */
    .stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; border: 1px solid white !important; }
    .stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; border: 1px solid white !important; }

    /* STRATEGY BRIEF - COMPLETE NAVY LOCK */
    .reason-box { background-color: #ffffff !important; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .reason-box * { color: #002366 !important; }
    
    /* Specific force for Radio labels which often stay white */
    .reason-box [data-testid="stWidgetLabel"] p, .reason-box .stRadio label p { 
        color: #002366 !important; 
        font-weight: bold !important; 
    }
    
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
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

def bold_hazard(text):
    if not text or text == "N/A": return text
    text = re.sub(r'\b(TEMPO|BECMG|PROB\d{2}|NOSIG|CAVOK)\b', r'<b>\1</b>', text)
    text = re.sub(r'(\b\d{3}\d{2}G\d{2,3}KT\b)', r'<b>\1</b>', text)
    text = re.sub(r'(\b(FG|TSRA|SN|-SN|FZRA|FZDZ|TS|FOG)\b)', r'<b>\1</b>', text)
    return text

# 4. MASTER DATABASE (FULL 47+ NETWORK)
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
    "IBZ": {"icao": "LEIB", "lat": 38.873, "lon": 1.373, "rwy": 60, "fleet": "Cityflyer", "spec": False},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "AGP": {"icao": "LEMG", "lat": 36.675, "lon": -4.499, "rwy": 130, "fleet": "Cityflyer", "spec": False},
    "FAO": {"icao": "LPFR", "lat": 37.017, "lon": -7.965, "rwy": 280, "fleet": "Cityflyer", "spec": False},
    "SEN": {"icao": "EGMC", "lat": 51.571, "lon": 0.701, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "JER": {"icao": "EGJJ", "lat": 49.208, "lon": -2.195, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer", "spec": True},
    "FNC": {"icao": "LPMA", "lat": 32.694, "lon": -16.774, "rwy": 50, "fleet": "Euroflyer", "spec": True},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "VRN": {"icao": "LIPX", "lat": 45.396, "lon": 10.888, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "OPO": {"icao": "LPPR", "lat": 41.242, "lon": -8.678, "rwy": 350, "fleet": "Euroflyer", "spec": False},
    "LYS": {"icao": "LFLL", "lat": 45.726, "lon": 5.090, "rwy": 350, "fleet": "Euroflyer", "spec": False},
    "SZG": {"icao": "LOWS", "lat": 47.794, "lon": 13.004, "rwy": 330, "fleet": "Euroflyer", "spec": False},
    "BOD": {"icao": "LFBD", "lat": 44.828, "lon": -0.716, "rwy": 230, "fleet": "Euroflyer", "spec": False},
    "GNB": {"icao": "LFLS", "lat": 45.363, "lon": 5.330, "rwy": 90, "fleet": "Euroflyer", "spec": False},
    "TRN": {"icao": "LIMF", "lat": 45.202, "lon": 7.649, "rwy": 360, "fleet": "Euroflyer", "spec": False},
    "ALC": {"icao": "LEAL", "lat": 38.282, "lon": -0.558, "rwy": 100, "fleet": "Euroflyer", "spec": False},
    "SVQ": {"icao": "LEZL", "lat": 37.418, "lon": -5.893, "rwy": 270, "fleet": "Euroflyer", "spec": False},
    "RAK": {"icao": "GMMX", "lat": 31.606, "lon": -8.036, "rwy": 100, "fleet": "Euroflyer", "spec": False},
    "AGA": {"icao": "GMAD", "lat": 30.325, "lon": -9.413, "rwy": 90, "fleet": "Euroflyer", "spec": False},
    "SSH": {"icao": "HESH", "lat": 27.977, "lon": 34.394, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "PFO": {"icao": "LCPH", "lat": 34.718, "lon": 32.486, "rwy": 290, "fleet": "Euroflyer", "spec": False},
    "LCA": {"icao": "LCLK", "lat": 34.875, "lon": 33.625, "rwy": 220, "fleet": "Euroflyer", "spec": False},
    "FUE": {"icao": "GCLP", "lat": 28.452, "lon": -13.864, "rwy": 10, "fleet": "Euroflyer", "spec": False},
    "TFS": {"icao": "GCTS", "lat": 28.044, "lon": -16.572, "rwy": 70, "fleet": "Euroflyer", "spec": False},
    "ACE": {"icao": "GCRR", "lat": 28.945, "lon": -13.605, "rwy": 30, "fleet": "Euroflyer", "spec": False},
    "LPA": {"icao": "GCLP", "lat": 27.931, "lon": -15.386, "rwy": 30, "fleet": "Euroflyer", "spec": False},
    "IVL": {"icao": "EFIV", "lat": 68.607, "lon": 27.405, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "Euroflyer", "spec": False},
    "ALG": {"icao": "DAAG", "lat": 36.691, "lon": 3.215, "rwy": 230, "fleet": "Euroflyer", "spec": False},
    # EXTRA DIVERSION STATIONS
    "PSA": {"icao": "LIRP", "lat": 43.683, "lon": 10.395, "rwy": 220, "fleet": "Special", "hide_map": True},
    "BLQ": {"icao": "LIPE", "lat": 44.535, "lon": 11.288, "rwy": 300, "fleet": "Special", "hide_map": True},
    "MUC": {"icao": "EDDM", "lat": 48.353, "lon": 11.786, "rwy": 260, "fleet": "Special", "hide_map": True},
    "PSO": {"icao": "LPPS", "lat": 33.071, "lon": -16.350, "rwy": 360, "fleet": "Special", "hide_map": True},
}

if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH DATA"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)
    hazard_filter = st.selectbox("ISOLATE HAZARD", ["Show All", "XWIND", "WINTER", "FOG"])

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

# 8. PROCESSOR (WITH v33.3 SAFETY WRAPPERS)
def process_network(bundle, airport_dict, horizon):
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
                if not line.start_time or line.start_time.dt > cutoff: continue
                l_dir = getattr(line.wind_direction, 'value', info.get('rwy', 0)) if line.wind_direction else info.get('rwy', 0)
                peak = max(getattr(line.wind_speed, 'value', 0), getattr(line.wind_gust, 'value', 0))
                if calculate_xwind(l_dir, peak, info.get('rwy', 0)) >= 25: f_issues.append("XWIND")
                if re.search(r'\bSN\b|\bFZ', line.raw.upper()): f_issues.append("WINTER")
                if f_issues: f_time = f"{line.start_time.dt.strftime('%H')}Z"

        proc[iata] = {"w_dir": m_w_dir, "w_spd": m_w_spd, "w_gst": m_w_gst, "raw_m": m.raw, "raw_t": t.raw, "f_issues": f_issues, "f_time": f_time}
    return proc

weather_data = process_network(weather_bundle, base_airports, 6)

# 9. UI LOOP
metar_alerts, taf_alerts, markers, green_stations = {}, {}, [], []
for iata, info in base_airports.items():
    d = weather_data.get(iata)
    if not d: continue
    xw = calculate_xwind(d['w_dir'], max(d['w_spd'], d['w_gst']), info.get('rwy', 0))
    m_issues = []
    if xw >= 25: m_issues.append("XWIND")
    if re.search(r'\bSN\b|\bFZ', d['raw_m'].upper()): m_issues.append("WINTER")
    
    color = "#008000"
    if m_issues: color = "#d6001a" if "WINTER" in m_issues or xw > 30 else "#eb8f34"
    elif d['f_issues']: color = "#eb8f34"
    if color == "#008000": green_stations.append(iata)

    if info.get('hide_map'): continue
    if not ((info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)): continue
    if m_issues: metar_alerts[iata] = {"type": "/".join(m_issues), "hex": "primary" if color == "#d6001a" else "secondary"}
    if d['f_issues']: taf_alerts[iata] = {"type": "+".join(d['f_issues']), "time": d['f_time']}

    content = f"""<div style="width:580px; background:white; padding:15px; border-radius:5px; color:#002366 !important;"><b>{iata} STATUS</b><hr><b>Actual XW:</b> {xw} KT<br><b>METAR:</b> {bold_hazard(d['raw_m'])}<br><b>TAF:</b> {bold_hazard(d['raw_t'])}</div>"""
    markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "content": content})

# 10. RENDER
st.markdown(f'<div class="ba-header"><div>OCC HUD v33.3 (Full Recovery)</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
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

# 11. STRATEGY BRIEF (v33.3 FIXED MATH & FONT LOCK)
if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d, info = weather_data.get(iata), base_airports.get(iata)
    
    # SAFETY: Only run rwy math if rwy value exists in database
    r1_val, r2_val = 0, 0
    if info and info.get('rwy'):
        r1_val = int(info['rwy']/10)
        r2_val = int(((info['rwy']+180)%360)/10)
    
    st.markdown('<div class="reason-box">', unsafe_allow_html=True)
    st.markdown(f'<div style="color:#002366 !important; font-size:22px; font-weight:900; margin-bottom:15px;">{iata} Strategy Brief</div>', unsafe_allow_html=True)
    
    # MANUAL RWY SELECTION (Forced Navy Label via HTML)
    st.markdown('<p style="color:#002366 !important; font-weight:bold; margin-bottom:0px;">Manual RWY Selection:</p>', unsafe_allow_html=True)
    sel_rwy = st.radio("Toggle:", [f"RWY {r1_val:02d}", f"RWY {r2_val:02d}"], horizontal=True, label_visibility="collapsed")
    
    target_hdg = info.get('rwy', 0) if f"{r1_val:02d}" in sel_rwy else (info.get('rwy', 0)+180)%360
    final_xw = calculate_xwind(d['w_dir'], max(d['w_spd'], d['w_gst']), target_hdg)
    
    st.markdown(f"""
        <div style="display:flex; gap:40px; margin-top:20px; color:#002366 !important;">
            <div style="flex:1;">
                <p style="color:#002366 !important;"><b>Active Hazards:</b> {(taf_alerts.get(iata, {}) or metar_alerts.get(iata, {}) or {'type':'STABLE'})['type']}</p>
                <p style="color:#002366 !important;"><b>Selected Crosswind: {final_xw}kt</b></p>
                <p style="margin-top:15px; font-weight:bold; color:#002366 !important;">Tactical Alternate Recommendations:</p>
                <table style="width:100%; border-collapse:collapse; color:#002366 !important;">
                    <tr style="border-bottom:2px solid #002366; text-align:left;"><th>Alternate</th><th>NM</th><th>XW</th></tr>
                    {"".join([f"<tr style='color:#002366 !important;'><td><b>{g}</b></td><td>{calculate_dist(info['lat'], info['lon'], base_airports[g]['lat'], base_airports[g]['lon'])} NM</td><td>{calculate_xwind(weather_data[g]['w_dir'], weather_data[g]['w_spd'], base_airports[g]['rwy'])} kt</td></tr>" for g in green_stations[:3]])}
                </table>
            </div>
            <div style="flex:1;">
                <div style="padding:10px; background:#f9f9f9; border-radius:5px; border-left:4px solid #002366; margin-bottom:10px; color:#002366 !important;">
                    <b style="color:#002366 !important;">LIVE METAR</b><br><code style="color:#002366 !important;">{bold_hazard(d['raw_m'])}</code>
                </div>
                <div style="padding:10px; background:#f9f9f9; border-radius:5px; border-left:4px solid #002366; color:#002366 !important;">
                    <b style="color:#002366 !important;">LIVE TAF</b><br><code style="color:#002366 !important;">{bold_hazard(d['raw_t'])}</code>
                </div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)
    if st.button("CLOSE BRIEF"): st.session_state.investigate_iata = "None"; st.rerun()
