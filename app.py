import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
import pandas as pd
from datetime import datetime, time, timedelta

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. HUD STYLING
st.markdown("""
    <style>
    .section-header { color: #002366 !important; font-weight: bold; font-size: 1.5rem; margin-top: 20px; border-bottom: 2px solid #d6001a; padding-bottom: 5px; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    [data-testid="stTextArea"] textarea { color: #002366 !important; background-color: #ffffff !important; font-weight: bold; font-family: 'Courier New', monospace; }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 250px !important; }
    [data-testid="stSidebar"] .stTextInput input { color: #002366 !important; background-color: white !important; font-weight: bold; }
    
    /* CONCISE SINGLE-LINE ALERTS */
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
    .reason-box h3, .reason-box p, .reason-box b, .reason-box small { color: #002366 !important; }
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
    text = re.sub(r'(\b\d{4}\b)', r'<b>\1</b>', text)
    text = re.sub(r'((BKN|OVC)\d{3})', r'<b>\1</b>', text)
    text = re.sub(r'(\b(FG|TSRA|SN|FZRA|FZDZ|RA|DZ|TS|VIS|CLOUD|FOG|XWIND|WIND)\b)', r'<b>\1</b>', text)
    text = re.sub(r'(\b\d{3}\d{2}(G\d{2})?KT\b)', r'<b>\1</b>', text)
    return text

# 4. MASTER DATABASE & ICAO MAPPING
# (Includes standard coordinates/runways for lookups)
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer", "spec": True},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "MAD": {"icao": "LEMD", "lat": 40.494, "lon": -3.567, "rwy": 140, "fleet": "Cityflyer", "spec": False},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer", "spec": False},
    "IBZ": {"icao": "LEIB", "lat": 38.873, "lon": 1.373, "rwy": 60, "fleet": "Cityflyer", "spec": False},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "Euroflyer", "spec": False},
    "BOD": {"icao": "LFBD", "lat": 44.828, "lon": -0.716, "rwy": 230, "fleet": "Euroflyer", "spec": False},
    "JER": {"icao": "EGJJ", "lat": 49.208, "lon": -2.195, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "ALC": {"icao": "LEAL", "lat": 38.282, "lon": -0.558, "rwy": 100, "fleet": "Euroflyer", "spec": False},
    # Add other stations as needed...
}

# 5. SIDEBAR & SCHEDULE LOADING
with st.sidebar:
    st.title("🛠️ MISSION CONTROL")
    uploaded_file = st.file_uploader("Upload Flight Schedule (report.csv)", type="csv")
    
    flights_df = pd.DataFrame()
    selected_date = None
    if uploaded_file:
        try:
            # Skip informational headers and empty separator rows
            df_full = pd.read_csv(uploaded_file, skiprows=2, on_bad_lines='skip')
            flights_df = df_full.dropna(subset=['DATE', 'FLT']).reset_index(drop=True)
            
            unique_dates = sorted(flights_df['DATE'].unique().tolist())
            selected_date = st.selectbox("Select Date", unique_dates)
            
            # Filter for active missions on that date
            flights_df = flights_df[flights_df['DATE'] == selected_date]
        except Exception as e:
            st.error(f"Schedule Error: {e}")

    st.markdown("---")
    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)
    map_theme = st.radio("MAP THEME", ["Dark Mode", "Light Mode"])
    if st.button("🔄 MANUAL DATA REFRESH"): st.cache_data.clear(); st.rerun()

# 6. DYNAMIC MISSION MAPPING
active_stations = {}
op_windows = {} # Format: {IATA: [(start_hour, end_hour), ...]}

if not flights_df.empty:
    for _, row in flights_df.iterrows():
        # Map DEP and ARR stations from schedule
        for port_type, time_col in [('DEP', 'STD'), ('ARR', 'STA')]:
            port = str(row[port_type]).strip().upper()
            if port in base_airports:
                active_stations[port] = base_airports[port]
                # Calculate +/- 2 Hour Operational Window
                try:
                    t_str = str(row[time_col]).strip()
                    f_dt = datetime.strptime(t_str, "%H:%M")
                    start_win = (f_dt - timedelta(hours=2)).hour
                    end_win = (f_dt + timedelta(hours=2)).hour
                    if port not in op_windows: op_windows[port] = []
                    op_windows[port].append((start_win, end_win))
                except: pass
else:
    # Fallback to hardcoded list if no schedule uploaded
    active_stations = base_airports.copy()

# 7. WEATHER ENGINE
@st.cache_data(ttl=600)
def fetch_mission_weather(station_dict):
    res = {}
    for iata, info in station_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            res[iata] = {
                "raw_m": m.raw or "N/A", "raw_t": t.raw or "N/A", "status": "online",
                "vis": m.data.visibility.value if (m.data and m.data.visibility) else 9999,
                "w_dir": m.data.wind_direction.value if (m.data and m.data.wind_direction) else 0,
                "w_spd": m.data.wind_speed.value or 0, "w_gst": m.data.wind_gust.value or 0,
                "m_clouds": m.data.clouds if (m.data and m.data.clouds) else [],
                "taf_lines": t.data.forecast if (t.data and t.data.forecast) else []
            }
        except: res[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A"}
    return res

weather_data = fetch_mission_weather(active_stations)

# 8. ANALYTICS & UI PROCESSING
metar_alerts, taf_alerts, map_markers, green_stations = {}, {}, [], []

for iata, info in active_stations.items():
    data = weather_data.get(iata)
    if not data or data['status'] == "offline": continue
    
    v_lim, c_lim = (1500, 500) if info.get('spec') else (800, 200)
    color, m_issues, actual_str, forecast_str = "#008000", [], "STABLE", "NIL"
    
    # 8.1 ACTUAL (METAR)
    xw = calculate_xwind(data.get('w_dir', 0), max(data['w_spd'], data['w_gst']), info['rwy'])
    m_cig = 9999
    for lyr in data.get('m_clouds', []):
        if lyr.type in ['BKN', 'OVC'] and lyr.base: m_cig = min(m_cig, lyr.base * 100)
    
    if data['vis'] < v_lim: m_issues.append("VIS")
    if m_cig < c_lim: m_issues.append("CLOUD")
    if xw >= 25: m_issues.append("XWIND")
    if "TSRA" in data['raw_m']: m_issues.append("TSRA")
    
    # 8.2 FORECAST (SCHEDULE-SENSITIVE)
    w_issues, w_time, w_prob = [], "", False
    
    for line in data.get("taf_lines", []):
        # Operational Window Filter: Skip TAF lines that don't overlap with flights
        is_relevant = True
        if iata in op_windows:
            line_start = line.start_time.dt.hour
            line_end = line.end_time.dt.hour
            is_relevant = any(start <= line_end and end >= line_start for (start, end) in op_windows[iata])
        
        if not is_relevant: continue

        v = line.visibility.value if line.visibility else 9999
        c = 9999
        if line.clouds:
            for lyr in line.clouds:
                if lyr.type in ['BKN', 'OVC'] and lyr.base: c = min(c, lyr.base * 100)
        
        l_issues = []
        if v < v_lim: l_issues.append("VIS")
        if c < c_lim: l_issues.append("CLOUD")
        if "TSRA" in line.raw: l_issues.append("TSRA")
        
        if l_issues:
            w_issues, w_prob = l_issues, ("PROB" in line.raw)
            w_time = f"{line.start_time.dt.strftime('%H')}-{line.end_time.dt.strftime('%H')}Z"

    # UI Mapping
    if m_issues:
        color = "#d6001a"
        metar_alerts[iata] = {"type": "/".join(m_issues), "hex": "primary"}
    if w_issues:
        color = "#eb8f34" if color == "#008000" else color
        taf_alerts[iata] = {"type": "+".join(w_issues), "time": w_time, "prob": w_prob, "hex": "secondary"}

    # Station Status Popup (High Vis)
    r1, r2 = int(info['rwy']/10), int(((info['rwy']+180)%360)/10)
    popup_html = f"""<div style="width:550px; color:black !important; font-family:monospace;"><b style="font-size:18px;">{iata} STATUS</b><div style="margin-top:8px; padding:10px; border-left:6px solid {color}; background:#f9f9f9; font-size:16px;"><b>RWY {r1:02d}/{r2:02d} Live X-Wind:</b> <span style="color:{'#d6001a' if xw >= 25 else 'black'}; font-weight:bold;">{xw} KT</span><br><b>ACTUAL:</b> {"/".join(m_issues) if m_issues else "STABLE"}<br><b>FORECAST:</b> {"+".join(w_issues) if w_issues else "NIL"}</div><hr><div style="display:flex; gap:10px;"><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>METAR</b><br>{bold_hazard(data['raw_m'])}</div><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>TAF</b><br>{bold_hazard(data['raw_t'])}</div></div></div>"""
    map_markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "popup": popup_html})

# 9. UI RENDER
st.markdown(f'<div class="ba-header"><div>OCC HUD - MISSION: {selected_date or "GLOBAL"}</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter", scrollWheelZoom=False)
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(mkr['popup'], max_width=700)).add_to(m)
st_folium(m, width=1200, height=1200, key="map_v151")

# 10. ALERTS
st.markdown('<div class="section-header">🔴 Actual Alerts (METAR)</div>', unsafe_allow_html=True)
if metar_alerts:
    cols = st.columns(5)
    for i, (iata, d) in enumerate(metar_alerts.items()):
        with cols[i % 5]:
            if st.button(f"{iata} NOW {d['type']}", key=f"m_{iata}", type="primary"): pass

st.markdown('<div class="section-header">🟠 Forecast Alerts (TAF)</div>', unsafe_allow_html=True)
if taf_alerts:
    cols_f = st.columns(5)
    for i, (iata, d) in enumerate(taf_alerts.items()):
        with cols_f[i % 5]:
            p_tag = " prob" if d['prob'] else ""
            if st.button(f"{iata} {d['time']} {d['type']}{p_tag}", key=f"f_{iata}", type="secondary"): pass
