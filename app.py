import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
from datetime import datetime, timedelta, timezone

# --- SAFETY GUARD FOR EXTERNAL API ---
try:
    from FlightRadar24 import FlightRadar24API
    FR_AVAILABLE = True
except ImportError:
    FR_AVAILABLE = False

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# [cite_start]2. STABLE v29.2 CSS (LOCKED) [cite: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
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
    [data-testid="stSidebar"] .stButton > button { background-color: #005a9c !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }

    div[data-testid="stSelectbox"] div[data-baseweb="select"] { background-color: white !important; }
    div[data-testid="stSelectbox"] * { color: #002366 !important; font-weight: 800 !important; }
    [data-baseweb="popover"] * { color: #002366 !important; background-color: white !important; font-weight: bold !important; }

    .stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }
    .stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }

    .reason-box { background-color: #ffffff !important; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .reason-box * { color: #002366 !important; }
    
    .section-header { color: #ffffff !important; background-color: #002366; padding: 10px; border-left: 10px solid #d6001a; font-weight: bold; font-size: 1.5rem; margin-top: 30px; }
    .leaflet-tooltip, .leaflet-popup-content-wrapper { background: white !important; border: 2px solid #002366 !important; padding: 0 !important; opacity: 1 !important; }
    </style>
    """, unsafe_allow_html=True)

# [cite_start]3. UTILITIES [cite: 18]
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
    text = re.sub(r'\b(TEMPO|BECMG|PROB\d{2})\b', r'<b>\1</b>', text)
    text = re.sub(r'(\b\d{3}\d{2}G\d{2,3}KT\b)', r'<b>\1</b>', text)
    text = re.sub(r'(\b(FG|TSRA|SN|-SN|FZRA|FZDZ|TS|FOG)\b)', r'<b>\1</b>', text)
    return text

# [cite_start]4. MASTER DATABASE [cite: 19, 20, 21, 22, 23, 24, 25, 26]
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer", "spec": True},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer", "spec": False},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "Cityflyer", "spec": False},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer", "spec": True},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer", "spec": True},
    "FNC": {"icao": "LPMA", "lat": 32.694, "lon": -16.774, "rwy": 50, "fleet": "Euroflyer", "spec": True},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "Euroflyer", "spec": False},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
}

# 5. SESSION STATE
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

# [cite_start]6. SIDEBAR [cite: 27, 28]
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 MANUAL DATA REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    st.markdown("✈️ **FLEET TRACKING**")
    if not FR_AVAILABLE:
        st.error("Missing dependency: FlightRadar24")
        st.info("Please add 'FlightRadar24' to your requirements.txt file.")
        show_fleet = False
    else:
        show_fleet = st.checkbox("Live CFE/EFW Tracking", value=True)

    st.markdown("---")
    time_horizon = st.radio("SCAN WINDOW", ["Next 6 Hours", "Next 12 Hours", "Next 24 Hours"], index=0)
    horizon_hours = 6 if "6" in time_horizon else (12 if "12" in time_horizon else 24)
    xw_limit = st.slider("X-WIND LIMIT (KT)", 15, 35, 25)
    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)

# [cite_start]7. DATA FETCH [cite: 29, 30, 31, 32, 33, 34, 35, 36, 37, 38]
@st.cache_data(ttl=60)
def get_live_fleet():
    if not FR_AVAILABLE or not show_fleet: return []
    try:
        fr = FlightRadar24API()
        return fr.get_flights(airline="CFE") + fr.get_flights(airline="EFW")
    except: return []

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

def process_weather(bundle, airport_dict, horizon, xw_thresh):
    proc = {}
    cutoff = datetime.now(timezone.utc) + timedelta(hours=horizon)
    for iata, data in bundle.items():
        if data['status'] == "offline": continue
        m, t, info = data['m_obj'], data['t_obj'], airport_dict[iata]
        
        f_issues, f_time = [], ""
        if t.data:
            for line in t.data.forecast:
                if not line.start_time or line.start_time.dt > cutoff: continue
                l_dir = getattr(line.wind_direction, 'value', info['rwy']) if line.wind_direction else info['rwy']
                peak = max(getattr(line.wind_speed, 'value', 0), getattr(line.wind_gust, 'value', 0))
                if calculate_xwind(l_dir, peak, info['rwy']) >= xw_thresh: f_issues.append("XWIND")
                if re.search(r'\bSN\b|\bFZ', line.raw.upper()): f_issues.append("WINTER")
                if f_issues: f_time = f"{line.start_time.dt.strftime('%H')}Z"

        proc[iata] = {
            "w_dir": getattr(m.data.wind_direction, 'value', 0),
            "w_spd": getattr(m.data.wind_speed, 'value', 0),
            "w_gst": getattr(m.data.wind_gust, 'value', 0),
            "raw_m": m.raw or "N/A", "raw_t": t.raw or "N/A",
            "f_issues": f_issues, "f_time": f_time
        }
    return proc

weather_data = process_weather(weather_bundle, base_airports, horizon_hours, xw_limit)

# [cite_start]8. UI LOOP [cite: 39, 40, 41, 42, 43, 44, 45]
metar_alerts, markers = {}, []
for iata, info in base_airports.items():
    d = weather_data.get(iata)
    if not d or not ((info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)): continue
    xw = calculate_xwind(d['w_dir'], max(d['w_spd'], d['w_gst']), info['rwy'])
    m_issues = []
    if xw >= xw_limit: m_issues.append("XWIND")
    if re.search(r'\bSN\b|\bFZ', d['raw_m'].upper()): m_issues.append("WINTER")
    
    color = "#008000"
    if m_issues: color = "#d6001a" if any(x in m_issues for x in ["WINTER","XWIND"]) else "#eb8f34"
    elif d['f_issues']: color = "#eb8f34"
    
    if m_issues: metar_alerts[iata] = "/".join(m_issues)
    
    content = f"""<div style="width:400px; color:black; background:white; padding:10px; border-radius:5px;"><b>{iata} STATUS</b><hr><b>Actual XW: {xw} KT</b><br>{d['raw_m']}</div>"""
    markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "content": content})

# 9. RENDER MAP
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.2</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=5, tiles="CartoDB dark_matter")

# Stations
for mkr in markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=8, color=mkr['color'], fill=True, popup=folium.Popup(mkr['content'], max_width=450)).add_to(m)

# Fleet tracking logic
if show_fleet:
    active_fleet = get_live_fleet()
    for p in active_fleet:
        dest = p.destination_airport_icao[-3:] # Get IATA
        dest_wx = weather_data.get(dest, {}).get('raw_m', "N/A")
        folium.Marker(
            location=[p.latitude, p.longitude],
            icon=folium.Icon(color="red" if p.airline_icao == "EFW" else "blue", icon="plane", prefix="fa"),
            popup=folium.Popup(f"<div style='color:black;'><b>{p.callsign}</b><br>DEST: {dest}<hr><b>ARR WX:</b><br>{dest_wx}</div>", max_width=250)
        ).add_to(m)

st_folium(m, width=1200, height=800, key="stable_map_v352")

# [cite_start]10. ALERTS & BRIEF [cite: 46, 47, 48, 49, 50, 51, 52, 53]
if metar_alerts:
    st.markdown('<div class="section-header">🔴 Actual Alerts (METAR)</div>', unsafe_allow_html=True)
    cols = st.columns(5)
    for i, (iata, msg) in enumerate(metar_alerts.items()):
        with cols[i % 5]:
            if st.button(f"{iata}: {msg}", key=f"btn_{iata}", type="primary"): st.session_state.investigate_iata = iata

if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d = weather_data.get(iata)
    st.markdown(f"""<div class="reason-box"><h3>{iata} Strategy Brief</h3><p><b>METAR:</b> {bold_hazard(d['raw_m'])}</p></div>""", unsafe_allow_html=True)
    if st.button("Close Brief"): st.session_state.investigate_iata = "None"; st.rerun()
