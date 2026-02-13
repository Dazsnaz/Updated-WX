import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
import pandas as pd
from datetime import datetime, timedelta

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. HUD STYLING (THE HIGH-CONTRAST NEON PATCH)
st.markdown("""
    <style>
    .section-header { color: #002366 !important; font-weight: bold; font-size: 1.5rem; margin-top: 20px; border-bottom: 2px solid #d6001a; padding-bottom: 5px; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    
    /* SIDEBAR: NAVY BACKGROUND / VIVID WHITE INPUTS */
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 330px !important; border-right: 3px solid #d6001a; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold !important; font-size: 1.1rem !important; text-shadow: 1px 1px 2px black; }
    
    /* Force high-contrast dropdowns and date pickers */
    [data-testid="stSidebar"] div[data-baseweb="input"], 
    [data-testid="stSidebar"] div[data-baseweb="select"],
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] select {
        background-color: #ffffff !important;
        color: #002366 !important;
        font-weight: 900 !important;
    }
    
    /* Fix Calendar Popup Visibility */
    div[data-baseweb="calendar"] { background-color: white !important; }
    div[data-baseweb="calendar"] * { color: #002366 !important; font-weight: bold !important; }

    /* CONCISE ALERT TABS */
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

# 4. FULL MASTER DATABASE
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
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "Euroflyer", "spec": False},
    "ALG": {"icao": "DAAG", "lat": 36.691, "lon": 3.215, "rwy": 230, "fleet": "Euroflyer", "spec": False},
    "LPA": {"icao": "GCLP", "lat": 27.931, "lon": -15.386, "rwy": 30, "fleet": "Euroflyer", "spec": False},
    "TFS": {"icao": "GCTS", "lat": 28.044, "lon": -16.572, "rwy": 70, "fleet": "Euroflyer", "spec": False},
    "ACE": {"icao": "GCRR", "lat": 28.945, "lon": -13.605, "rwy": 30, "fleet": "Euroflyer", "spec": False},
    "FUE": {"icao": "GCLB", "lat": 28.452, "lon": -13.864, "rwy": 10, "fleet": "Euroflyer", "spec": False},
}

# 5. SIDEBAR & CALENDAR MISSION CONTROL
with st.sidebar:
    st.title("🛠️ MISSION CONTROL")
    uploaded_file = st.file_uploader("Upload report.csv", type="csv")
    
    # Force vivid contrast for calendar
    selected_dt = st.date_input("📅 MISSION DATE", datetime(2026, 2, 12))
    
    flights_df = pd.DataFrame()
    if uploaded_file:
        try:
            raw_content = uploaded_file.read().decode('utf-8')
            lines = raw_content.splitlines()
            h_row = next(i for i, line in enumerate(lines) if "DATE" in line.upper() and "FLT" in line.upper())
            
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, skiprows=h_row, on_bad_lines='skip')
            df.columns = df.columns.str.strip().str.upper()
            df = df.dropna(subset=['DATE', 'FLT'])
            
            # Robust Date Matching
            df['DATE_DT'] = pd.to_datetime(df['DATE'], dayfirst=True, errors='coerce').dt.date
            flights_df = df[df['DATE_DT'] == selected_dt].reset_index(drop=True)
            
            st.success(f"Missions Linked: {len(flights_df)}")
        except Exception as e:
            st.error("Header Mismatch: Use 'DATE' and 'FLT'")

    st.markdown("---")
    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)
    if st.button("🔄 REFRESH ALL DATA"): st.cache_data.clear(); st.rerun()

# 6. DYNAMIC MISSION LINKING (AUTO-DISCOVERY)
active_stations = {}
op_windows = {}

if not flights_df.empty:
    for _, row in flights_df.iterrows():
        for port_type, time_col in [('DEP', 'STD'), ('ARR', 'STA')]:
            port = str(row[port_type]).strip().upper()
            if port in base_airports:
                active_stations[port] = base_airports[port]
                try:
                    t_str = str(row[time_col]).strip()
                    f_time = datetime.strptime(t_str, "%H:%M")
                    # Window logic: +/- 2 hours
                    win_start, win_end = (f_time - timedelta(hours=2)).time(), (f_time + timedelta(hours=2)).time()
                    if port not in op_windows: op_windows[port] = []
                    op_windows[port].append((win_start, win_end))
                except: pass
else:
    # GLOBAL VIEW (Default to Master List if no file)
    active_stations = base_airports.copy()

# 7. WEATHER ENGINE
@st.cache_data(ttl=600)
def get_mission_wx(station_dict):
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

weather_data = get_mission_wx(active_stations)

# 8. MISSION PROCESSING & MAP
metar_alerts, taf_alerts, map_markers = {}, {}, []

for iata, info in active_stations.items():
    data = weather_data.get(iata)
    if not data or data['status'] == "offline": continue
    is_shown = (info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)
    v_lim, c_lim = (1500, 500) if info.get('spec') else (800, 200)
    color, m_issues, actual_str, forecast_str = "#008000", [], "STABLE", "NIL"
    xw = calculate_xwind(data.get('w_dir', 0), max(data.get('w_spd', 0), data.get('w_gst', 0)), info['rwy'])
    
    # ACTUAL
    m_cig = 9999
    for lyr in data.get('m_clouds', []):
        if lyr.type in ['BKN', 'OVC'] and lyr.base: m_cig = min(m_cig, lyr.base * 100)
    if data['vis'] < v_lim: m_issues.append("VIS")
    if m_cig < c_lim: m_issues.append("CLOUD")
    if xw >= 25: m_issues.append("XWIND"); color = "#d6001a"
    
    # FORECAST (WINDOW ACCURATE)
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

    if is_shown:
        if m_issues: 
            color = "#d6001a"; actual_str = "/".join(m_issues)
            metar_alerts[iata] = {"type": actual_str}
        if w_issues:
            color = "#eb8f34" if color == "#008000" else color
            taf_alerts[iata] = {"type": "+".join(w_issues), "time": w_time, "prob": w_prob}

        r1, r2 = int(info['rwy']/10), int(((info['rwy']+180)%360)/10)
        popup_html = f"""<div style="width:600px; color:black !important; font-family:monospace; font-size:14px;"><b style="color:#002366; font-size:18px;">{iata} STATUS</b><div style="margin-top:8px; padding:10px; border-left:6px solid {color}; background:#f9f9f9; font-size:16px;"><b style="color:#002366;">RWY {r1:02d}/{r2:02d} Live X-Wind:</b> <span style="color:{'#d6001a' if xw >= 25 else 'black'}; font-weight:bold;">{xw} KT</span><br><b>ACTUAL:</b> {actual_str}<br><b>FORECAST:</b> {forecast_str}</div><hr><div style="display:flex; gap:12px;"><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>METAR</b><br>{bold_hazard(data['raw_m'])}</div><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>TAF</b><br>{bold_hazard(data['raw_t'])}</div></div></div>"""
        map_markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "popup": popup_html})

# 9. UI RENDER
st.markdown(f'<div class="ba-header"><div>OCC HUD - MISSION: {selected_dt}</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter", scrollWheelZoom=False)
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(mkr['popup'], max_width=700)).add_to(m)
st_folium(m, width=1200, height=1200, key="map_v171")

# 10. ALERTS (MISSION ACCURATE)
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
