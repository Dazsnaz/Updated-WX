import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf, Station
import math
import re
import pandas as pd
import io
from datetime import datetime, timedelta

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. HIGH-CONTRAST CSS SHIELD
st.markdown("""
    <style>
    .section-header { color: #002366 !important; font-weight: bold; font-size: 1.5rem; margin-top: 20px; border-bottom: 2px solid #d6001a; padding-bottom: 5px; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    
    /* SIDEBAR CONTRAST OVERRIDE */
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 330px !important; border-right: 3px solid #d6001a; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold !important; font-size: 1.1rem !important; }
    
    /* Force Navy Text on White for all inputs and popups */
    [data-testid="stSidebar"] div[data-baseweb="input"], 
    [data-testid="stSidebar"] div[data-baseweb="select"],
    [data-testid="stSidebar"] input,
    .stSelectbox div,
    div[data-baseweb="calendar"] {
        background-color: #ffffff !important;
        color: #002366 !important;
        font-weight: bold !important;
    }
    
    /* Target Calendar Text Specifically */
    div[data-baseweb="calendar"] * { color: #002366 !important; }

    /* ALERT BUTTONS */
    .stButton > button { 
        background-color: #005a9c !important; color: white !important; border: 1px solid white !important; 
        width: 100%; text-transform: uppercase; font-size: 0.72rem !important; height: 45px !important; 
        line-height: 1.1 !important; white-space: nowrap !important; overflow: hidden;
        text-overflow: ellipsis; display: flex; align-items: center; justify-content: center; 
    }
    
    .ba-header { background-color: #002366; padding: 20px; border-radius: 5px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 4px solid #d6001a; }
    div.stButton > button[kind="primary"] { background-color: #d6001a !important; }
    div.stButton > button[kind="secondary"] { background-color: #eb8f34 !important; }
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
    text = re.sub(r'(\b(FG|TSRA|SN|FZRA|FZDZ|RA|DZ|TS|VIS|CLOUD|FOG|XWIND|WIND)\b)', r'<b>\1</b>', text)
    text = re.sub(r'(\b\d{3}\d{2}(G\d{2})?KT\b)', r'<b>\1</b>', text)
    return text

# 4. SIDEBAR & SCHEDULE PROCESSING
with st.sidebar:
    st.title("🛠️ MISSION CONTROL")
    uploaded_file = st.file_uploader("1. UPLOAD report.csv", type="csv")
    selected_dt = st.date_input("2. SELECT MISSION DATE", datetime(2026, 2, 12))
    
    flights_df = pd.DataFrame()
    if uploaded_file:
        try:
            # Flexible reading to handle spacer rows and info headers
            raw = uploaded_file.read().decode('utf-8')
            lines = raw.splitlines()
            h_row = next(i for i, line in enumerate(lines) if "DATE" in line.upper() and "FLT" in line.upper())
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, skiprows=h_row, on_bad_lines='skip')
            df.columns = df.columns.str.strip().str.upper()
            df = df.dropna(subset=['DATE', 'FLT'])
            
            # Match date regardless of format (DD/MM/YY or DD/MM/YYYY)
            df['DATE_DT'] = pd.to_datetime(df['DATE'], dayfirst=True, errors='coerce').dt.date
            flights_df = df[df['DATE_DT'] == selected_dt].reset_index(drop=True)
            
            st.success(f"Linked: {len(flights_df)} Flights")
        except Exception as e:
            st.error("Error Linking Schedule. Check headers.")

    st.markdown("---")
    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)
    if st.button("🔄 REFRESH ALL"): st.cache_data.clear(); st.rerun()

# 5. GLOBAL STATION DISCOVERY
active_stations = {}
op_windows = {}

if not flights_df.empty:
    unique_codes = pd.concat([flights_df['DEP'], flights_df['ARR']]).unique()
    for iata in unique_codes:
        iata = str(iata).strip().upper()
        if len(iata) != 3: continue
        try:
            # Auto-Discovery: Lookup coordinates for any airport in the schedule
            s = Station.from_iata(iata)
            active_stations[iata] = {
                "icao": s.icao, "lat": s.latitude, "lon": s.longitude, 
                "rwy": 270, # Defaulting to 270 for unknown ports
                "spec": (iata in ["LCY", "FLR", "CMF", "INN", "FNC"])
            }
            # Map mission windows
            dep_times = flights_df[flights_df['DEP'] == iata]['STD'].tolist()
            arr_times = flights_df[flights_df['ARR'] == iata]['STA'].tolist()
            for t_str in (dep_times + arr_times):
                try:
                    f_time = datetime.strptime(str(t_str).strip(), "%H:%M")
                    win_start = (f_time - timedelta(hours=2)).time()
                    win_end = (f_time + timedelta(hours=2)).time()
                    if iata not in op_windows: op_windows[iata] = []
                    op_windows[iata].append((win_start, win_end))
                except: pass
        except: continue

# 6. WEATHER ENGINE
@st.cache_data(ttl=600)
def fetch_weather(station_dict):
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

weather_data = fetch_weather(active_stations)

# 7. ANALYTICS & MAP PROCESSING
metar_alerts, taf_alerts, map_markers = {}, {}, []

for iata, info in active_stations.items():
    data = weather_data.get(iata)
    if not data or data['status'] == "offline": continue
    
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    color, m_issues, actual_str, forecast_str = "#008000", [], "STABLE", "NIL"
    xw = calculate_xwind(data.get('w_dir', 0), max(data.get('w_spd', 0), data.get('w_gst', 0)), info['rwy'])
    
    # 7.1 METAR CHECK
    m_cig = 9999
    for lyr in data.get('m_clouds', []):
        if lyr.type in ['BKN', 'OVC'] and lyr.base: m_cig = min(m_cig, lyr.base * 100)
    if data['vis'] < v_lim: m_issues.append("VIS")
    if m_cig < c_lim: m_issues.append("CLOUD")
    if xw >= 25: m_issues.append("XWIND"); color = "#d6001a"
    
    # 7.2 FORECAST (WINDOW ACCURATE)
    w_issues, w_time, w_prob = [], "", False
    for line in data.get("taf_lines", []):
        if iata in op_windows:
            l_start, l_end = line.start_time.dt.time(), line.end_time.dt.time()
            if not any((s <= l_end and e >= l_start) for (s, e) in op_windows[iata]): continue
        
        v = line.visibility.value if line.visibility else 9999
        c = 9999
        if line.clouds:
            for lyr in line.clouds:
                if lyr.type in ['BKN', 'OVC'] and lyr.base: c = min(c, lyr.base * 100)
        if v < v_lim or c < c_lim or "TSRA" in line.raw:
            w_issues = ["CLOUD"] if c < c_lim else ["VIS"]
            if "TSRA" in line.raw: w_issues.append("TSRA")
            w_prob, w_time = ("PROB" in line.raw), f"{line.start_time.dt.strftime('%H')}-{line.end_time.dt.strftime('%H')}Z"

    # UI Mapping
    if m_issues: 
        color = "#d6001a"; actual_str = "/".join(m_issues)
        metar_alerts[iata] = {"type": actual_str}
    if w_issues:
        color = "#eb8f34" if color == "#008000" else color
        forecast_str = f"{'+'.join(w_issues)}{' prob' if w_prob else ''} @ {w_time}"
        taf_alerts[iata] = {"type": "+".join(w_issues), "time": w_time, "prob": w_prob}

    popup_html = f"""<div style="width:600px; color:black !important; font-family:monospace; font-size:14px;"><b style="color:#002366; font-size:18px;">{iata} STATUS</b><div style="margin-top:8px; padding:10px; border-left:6px solid {color}; background:#f9f9f9; font-size:16px;"><b>Live X-Wind:</b> <span style="color:{'#d6001a' if xw >= 25 else 'black'}; font-weight:bold;">{xw} KT</span><br><b>ACTUAL:</b> {actual_str}<br><b>FORECAST:</b> {forecast_str}</div><hr><div style="display:flex; gap:12px;"><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>METAR</b><br>{bold_hazard(data['raw_m'])}</div><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>TAF</b><br>{bold_hazard(data['raw_t'])}</div></div></div>"""
    map_markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "popup": popup_html})

# 8. UI RENDER
st.markdown(f'<div class="ba-header"><div>OCC HUD - MISSION: {selected_dt}</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter", scrollWheelZoom=False)
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(mkr['popup'], max_width=700)).add_to(m)
st_folium(m, width=1200, height=1200, key="map_v173")

# 9. ALERTS
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
