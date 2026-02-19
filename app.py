import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
import io
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. HUD STYLING (ANTI-GREY OUT + CSS)
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    [data-testid="stAppViewContainer"] > main { opacity: 1 !important; transition: none !important; filter: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    .ba-header { background-color: #002366 !important; color: #ffffff !important; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 350px !important; border-right: 3px solid #d6001a; }
    [data-testid="stSidebar"] .stButton > button { background-color: #005a9c !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }
    .stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }
    .stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }
    div[data-testid="stSelectbox"] div[data-baseweb="select"], div[data-testid="stDateInput"] div { background-color: white !important; }
    div[data-testid="stSelectbox"] *, div[data-testid="stDateInput"] * { color: #002366 !important; font-weight: 800 !important; }
    [data-testid="stFileUploader"] section { background-color: #005a9c !important; border: 1px solid white !important; border-radius: 5px !important; padding: 15px !important; }
    [data-testid="stFileUploader"] section * { color: white !important; }
    .reason-box { background-color: #ffffff !important; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; color: #002366 !important; }
    .reason-box * { color: #002366 !important; }
    .section-header { color: #ffffff !important; background-color: #002366; padding: 10px; border-left: 10px solid #d6001a; font-weight: bold; font-size: 1.5rem; margin-top: 30px; }
    </style>
    """, unsafe_allow_html=True)

# 3. CORE UTILITIES
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
    text = re.sub(r'(\b(FG|TSRA|SN|-SN|\+SN|FZRA|FZDZ|TS|FOG)\b)', r'<b>\1</b>', text)
    return text

@st.cache_data
def load_schedule_robust(file_bytes):
    try:
        content = file_bytes.decode('utf-8').splitlines()
        skip_r = 0
        for i, line in enumerate(content):
            if 'DATE' in line and 'FLT' in line and 'DEP' in line and 'ARR' in line:
                skip_r = i
                break
        df = pd.read_csv(io.StringIO(file_bytes.decode('utf-8')), skiprows=skip_r, on_bad_lines='skip')
        df = df.dropna(subset=['FLT'])
        df['DATE_OBJ'] = pd.to_datetime(df['DATE'], dayfirst=True, errors='coerce').dt.date
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_raw_weather_master(airport_dict):
    raw_res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            raw_res[iata] = {"m_obj": m, "t_obj": t, "status": "online"}
        except: raw_res[iata] = {"status": "offline"}
    return raw_res

@st.cache_data(ttl=20)
def fetch_raw_radar():
    fleet = []
    try:
        url = "https://opensky-network.org/api/states/all?lamin=30.0&lomin=-20.0&lamax=65.0&lomax=30.0"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "states" in data and data["states"]:
                for s in data["states"]:
                    call = (s[1] or "").strip().upper()
                    if call.startswith("CFE") or call.startswith("EFW"):
                        fleet.append({"call": call, "lat": s[6], "lon": s[5], "type": "CFE" if call.startswith("CFE") else "EFW", "alt": round((s[7] or 0) * 3.28084), "hdg": s[10] or 0})
    except: pass
    return fleet

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
}

# 5. SESSION STATE
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"
if "map_center" not in st.session_state: st.session_state.map_center = [50.0, 10.0]
if "map_zoom" not in st.session_state: st.session_state.map_zoom = 4

# 6. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    uploaded_file = st.file_uploader("Upload Daily Flight Schedule (CSV)", type=["csv"])
    flight_schedule = pd.DataFrame()
    selected_date = st.date_input("📅 Select Operations Date:", value=datetime.now().date())
    active_stations = set()
    
    if uploaded_file is not None:
        flight_schedule = load_schedule_robust(uploaded_file.getvalue())
        if not flight_schedule.empty:
            flight_schedule = flight_schedule[flight_schedule['DATE_OBJ'] == selected_date]
            active_stations = set(flight_schedule['DEP'].dropna()) | set(flight_schedule['ARR'].dropna())
    
    display_airports = {k: v for k, v in base_airports.items() if k in active_stations} if uploaded_file and active_stations else base_airports
    
    if st.button("🔄 MANUAL DATA REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    show_radar = st.checkbox("Enable Live Aircraft Radar", value=True)
    time_horizon = st.radio("SCAN WINDOW", ["Next 6 Hours", "Next 12 Hours", "Next 24 Hours"], index=0)
    horizon_hours = 6 if "6" in time_horizon else (12 if "12" in time_horizon else 24)
    xw_limit = st.slider("X-WIND LIMIT (KT)", 15, 35, 25)
    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)
    map_theme = st.radio("MAP THEME", ["Dark Mode", "Light Mode"])

# 7. WEATHER DATA FETCH
raw_weather_bundle = get_raw_weather_master(display_airports)

def process_weather(bundle, airport_dict, horizon_limit, xw_threshold):
    processed = {}
    cutoff_time = datetime.now(timezone.utc) + timedelta(hours=horizon_limit)
    for iata, data in bundle.items():
        if data['status'] == "offline" or 'm_obj' not in data: continue
        m, t, info = data['m_obj'], data.get('t_obj'), airport_dict[iata]
        v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
        
        m_vis = m.data.visibility.value if (m.data and hasattr(m.data, 'visibility') and m.data.visibility) else 9999
        m_cig = 9999
        if m.data and hasattr(m.data, 'clouds') and m.data.clouds:
            for lyr in m.data.clouds:
                if lyr.type in ['BKN', 'OVC'] and lyr.base: m_cig = min(m_cig, lyr.base * 100)
        
        w_issues, f_time = [], ""
        if t and hasattr(t, 'data') and t.data and hasattr(t.data, 'forecast') and t.data.forecast:
            for line in t.data.forecast:
                if not hasattr(line, 'start_time') or not line.start_time or line.start_time.dt > cutoff_time: continue
                l_raw = line.raw.upper()
                if re.search(r'(-SN|\+SN|\bSN\b|\bFZ|\bFG\b)', l_raw): w_issues.append("WINTER/FOG")
                
                l_v = line.visibility.value if (hasattr(line, 'visibility') and line.visibility and line.visibility.value is not None) else 9999
                if l_v < v_lim: w_issues.append("VIS")
                
                # SAFE WIND/GUST EXTRACTION
                l_dir = line.wind_direction.value if (hasattr(line, 'wind_direction') and line.wind_direction and line.wind_direction.value is not None) else info['rwy']
                l_spd_val = line.wind_speed.value if (hasattr(line, 'wind_speed') and line.wind_speed and line.wind_speed.value is not None) else 0
                l_gst_val = line.wind_gust.value if (hasattr(line, 'wind_gust') and line.wind_gust and line.wind_gust.value is not None) else 0
                l_spd = max(l_spd_val, l_gst_val)
                
                if calculate_xwind(l_dir, l_spd, info['rwy']) >= xw_threshold: w_issues.append("XWIND")
                if w_issues: f_time = f"{line.start_time.dt.strftime('%H')}Z"; break
        
        w_dir = m.data.wind_direction.value if (m.data and hasattr(m.data, 'wind_direction') and m.data.wind_direction) else 0
        w_spd = m.data.wind_speed.value if (m.data and hasattr(m.data, 'wind_speed') and m.data.wind_speed) else 0
        w_gst = m.data.wind_gust.value if (m.data and hasattr(m.data, 'wind_gust') and m.data.wind_gust) else 0
        
        processed[iata] = {"vis": m_vis, "cig": m_cig, "w_dir": w_dir, "w_spd": w_spd, "w_gst": w_gst, "raw_m": m.raw or "N/A", "raw_t": t.raw if t else "N/A", "f_issues": list(set(w_issues)), "f_time": f_time}
    return processed

weather_data = process_weather(raw_weather_bundle, display_airports, horizon_hours, xw_limit)

# 8. MAPPING PREP
sched_dict = {}
if not flight_schedule.empty:
    has_arcid = 'ARCID' in flight_schedule.columns
    for _, r in flight_schedule.iterrows():
        if has_arcid and pd.notna(r['ARCID']): sched_dict[str(r['ARCID']).strip().upper()] = r
        flt_num = str(r['FLT']).replace('BA', '').strip()
        sched_dict[f"CFE{flt_num}"] = r; sched_dict[f"EFW{flt_num}"] = r

current_utc_time = datetime.now(timezone.utc).strftime('%H:%M')
map_markers = []
metar_alerts, taf_alerts = {}, {}

for iata, info in display_airports.items():
    d = weather_data.get(iata)
    if not d or not ((info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)): continue
    cur_xw = calculate_xwind(d['w_dir'], max(d['w_spd'], d['w_gst']), info['rwy'])
    color = "#008000"
    if d['vis'] < (1500 if info['spec'] else 800) or cur_xw >= xw_limit:
        color = "#d6001a"; metar_alerts[iata] = {"type": "NOW", "hex": "primary"}
    elif d['f_issues']: 
        color = "#eb8f34"; taf_alerts[iata] = {"type": d['f_time'], "hex": "secondary"}
    
    rows = ""
    if not flight_schedule.empty:
        arr_f = flight_schedule[(flight_schedule['ARR'] == iata) & (flight_schedule['STA'] >= current_utc_time)].sort_values('STA')
        for _, r in arr_f.iterrows():
            rows += f"<tr><td>{r['FLT']}</td><td>{r['DEP']}</td><td>{r['STA']}</td></tr>"
    
    content = f"<div style='color:black; width:400px;'><b>{iata} STATUS</b><br>METAR: {bold_hazard(d['raw_m'])}<br>TAF: {bold_hazard(d['raw_t'])}<br><table style='width:100%; font-size:12px; margin-top:10px;'>{rows}</table></div>"
    map_markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "content": content})

# 9. LIVE RADAR FRAGMENT
st.markdown(f'<div class="ba-header"><div>OCC HUD v29.2</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)

@st.fragment(run_every=20)
def live_radar_map(cf_on, ef_on, scheduler):
    m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom, tiles=("CartoDB dark_matter" if map_theme == "Dark Mode" else "CartoDB positron"), scrollWheelZoom=False)
    for mkr in map_markers:
        folium.CircleMarker([mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(mkr['content'], max_width=450)).add_to(m)
    
    if show_radar:
        planes = fetch_raw_radar()
        for p in planes:
            if (p['type'] == 'CFE' and not cf_on) or (p['type'] == 'EFW' and not ef_on): continue
            call = p['call']; flt, dep, arr = call, "UKN", "UKN"
            if call in scheduler:
                flt = scheduler[call]['FLT']; dep = scheduler[call]['DEP']; arr = scheduler[call]['ARR']
            
            icon_svg = f'<svg viewBox="0 0 24 24" width="22" height="22" xmlns="http://www.w3.org/2000/svg"><path d="M21,16v-2l-8-5V3.5C13,2.67,12.33,2,11.5,2S10,2.67,10,3.5V9l-8,5v2l8-2.5V19l-2,1.5V22l3.5-1l3.5,1v-1.5L13,19v-5.5L21,16z" fill="{"#00bfff" if p["type"]=="CFE" else "#ff4500"}" stroke="white" stroke-width="1"/></svg>'
            folium.Marker([p['lat'], p['lon']], icon=folium.DivIcon(html=f'<div style="transform: rotate({p["hdg"]}deg);">{icon_svg}</div>'), tooltip=f"FLT: {flt} | {dep}->{arr} | {p['alt']}ft").add_to(m)

    map_res = st_folium(m, width=1300, height=750, key="map_stable", returned_objects=["center", "zoom"])
    if map_res and map_res.get("center"):
        st.session_state.map_center = [map_res["center"]["lat"], map_res["center"]["lng"]]
        st.session_state.map_zoom = map_res["zoom"]

live_radar_map(show_cf, show_ef, sched_dict)

# 10. ALERTS & LOG
st.markdown('<div class="section-header">🔴 Actual Alerts</div>', unsafe_allow_html=True)
if metar_alerts:
    cols = st.columns(5)
    for i, (iata, d) in enumerate(metar_alerts.items()):
        with cols[i % 5]: st.button(f"{iata} {d['type']}", key=f"m_{iata}", type=d['hex'])
