import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
from datetime import datetime, timedelta, timezone

# --- OFFICIAL FR24 SDK INTEGRATION ---
try:
    from fr24sdk.client import Client
    FR_AVAILABLE = True
except ImportError:
    FR_AVAILABLE = False

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. STABLE v29.2 CSS RESTORATION
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

    .stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }
    .stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }

    .reason-box { background-color: #ffffff !important; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .reason-box * { color: #002366 !important; }
    
    .section-header { color: #ffffff !important; background-color: #002366; padding: 10px; border-left: 10px solid #d6001a; font-weight: bold; font-size: 1.5rem; margin-top: 30px; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
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

# 4. MASTER DATABASE
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
}

# 5. SESSION STATE
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

# 6. OFFICIAL SDK FLEET FETCH
@st.cache_data(ttl=60)
def get_official_fleet():
    if not FR_AVAILABLE: return [], 0, 0
    try:
        # Using the token provided in your previous message
        api_token = "019c6fb5-bd21-725e-a31e-f9814df70712|CYYoXrBCOBJGJuwfTFq28JBhypNfIOC729Mke8bza542008f"
        fleet_list = []
        
        with Client(api_token=api_token) as client:
            # Query the bounding box for Europe roughly (N, S, W, E)
            bounds = "71.0,30.0,-25.0,40.0"
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            for f in flights.data:
                callsign = getattr(f, 'callsign', "")
                # Filter for your specific callsigns
                if callsign.startswith("CFE") or callsign.startswith("EFW"):
                    fleet_list.append({
                        "callsign": callsign,
                        "lat": f.latitude,
                        "lon": f.longitude,
                        "alt": getattr(f, 'altitude', 0),
                        "dest": getattr(f, 'destination', "???"),
                        "type": "EFW" if callsign.startswith("EFW") else "CFE"
                    })
        
        cfe = [p for p in fleet_list if p['type'] == "CFE"]
        efw = [p for p in fleet_list if p['type'] == "EFW"]
        return fleet_list, len(cfe), len(efw)
    except:
        return [], 0, 0

# 7. SIDEBAR & DATA CALLS
active_fleet, cfe_n, efw_n = get_official_fleet()

with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH HUD"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    st.markdown(f"✈️ **CFE Airborne:** {cfe_n}")
    st.markdown(f"✈️ **EFW Airborne:** {efw_n}")
    show_fleet = st.checkbox("Show Official Fleet Track", value=True)
    st.markdown("---")
    show_cf = st.checkbox("Cityflyer (CFE) Stations", value=True)
    show_ef = st.checkbox("Euroflyer (EFW) Stations", value=True)
    xw_limit = st.slider("X-WIND LIMIT (KT)", 15, 35, 25)

# 8. WEATHER (v29.2 Logic)
@st.cache_data(ttl=1800)
def fetch_wx(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            res[iata] = {"m_obj": m, "t_obj": t, "status": "online"}
        except: res[iata] = {"status": "offline"}
    return res

weather_bundle = fetch_wx(base_airports)

def process_wx(bundle, airport_dict, limit, xw_thresh):
    proc = {}
    cutoff = datetime.now(timezone.utc) + timedelta(hours=limit)
    for iata, data in bundle.items():
        if data['status'] == "offline": continue
        m, t, info = data['m_obj'], data['t_obj'], airport_dict[iata]
        f_issues, f_time = [], ""
        if t.data:
            for line in t.data.forecast:
                if not line.start_time or line.start_time.dt > cutoff: continue
                l_dir = getattr(line.wind_direction, 'value', info['rwy'])
                peak = max(getattr(line.wind_speed, 'value', 0), getattr(line.wind_gust, 'value', 0))
                if calculate_xwind(l_dir, peak, info['rwy']) >= xw_thresh: f_issues.append("XWIND")
                if re.search(r'\bSN\b|\bFZ', line.raw.upper()): f_issues.append("WINTER")
                if f_issues: f_time = f"{line.start_time.dt.strftime('%H')}Z"
        proc[iata] = {
            "w_dir": getattr(m.data.wind_direction, 'value', 0),
            "w_spd": getattr(m.data.wind_speed, 'value', 0),
            "w_gst": getattr(m.data.wind_gust, 'value', 0),
            "raw_m": m.raw, "raw_t": t.raw, "f_issues": f_issues, "f_time": f_time
        }
    return proc

weather_data = process_wx(weather_bundle, base_airports, 6, xw_limit)

# [cite_start]9. UI & MAP [cite: 39-45]
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
    content = f"""<div style="width:300px; color:black; background:white; padding:10px;"><b>{iata}</b><hr>Actual XW: {xw}KT</div>"""
    markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "content": content})

# 10. RENDER
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.8 (Official SDK)</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter")

for mkr in markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(mkr['content'])).add_to(m)

if show_fleet and active_fleet:
    for p in active_fleet:
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color="red" if p['type'] == "EFW" else "blue", icon="plane", prefix="fa"),
            tooltip=f"{p['callsign']} to {p['dest']}"
        ).add_to(m)

st_folium(m, width=1200, height=800, key="official_fr24_map")

# 11. ALERTS & BRIEF
if metar_alerts:
    st.markdown('<div class="section-header">🔴 Actual Alerts</div>', unsafe_allow_html=True)
    cols = st.columns(5)
    for i, (iata, msg) in enumerate(metar_alerts.items()):
        with cols[i % 5]:
            if st.button(f"{iata}: {msg}", key=f"m_{iata}", type="primary"): st.session_state.investigate_iata = iata

if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d = weather_data.get(iata)
    st.markdown(f"""<div class="reason-box"><h3>{iata} Strategy Brief</h3><p><b>METAR:</b> {bold_hazard(d['raw_m'])}</p></div>""", unsafe_allow_html=True)
    if st.button("CLOSE BRIEF"): st.session_state.investigate_iata = "None"; st.rerun()
