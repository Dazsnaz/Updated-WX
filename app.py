import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
import pandas as pd
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. HUD STYLING
st.markdown("""
    <style>
    .section-header { color: #002366 !important; font-weight: bold; font-size: 1.5rem; margin-top: 20px; border-bottom: 2px solid #d6001a; padding-bottom: 5px; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    [data-testid="stTextArea"] textarea { color: #002366 !important; background-color: #ffffff !important; font-weight: bold; font-family: 'Courier New', monospace; }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 300px; border-right: 2px solid #d6001a; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold !important; }
    
    /* Input visibility */
    div[data-baseweb="input"], div[data-baseweb="select"], input, .stSelectbox div, .stDateInput div {
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
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_xwind(wind_dir, wind_spd, rwy_hdg):
    if wind_dir is None or wind_spd is None or rwy_hdg is None: return 0
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

def bold_hazard(text):
    if not text or text == "N/A": return text
    # Bold winter hazards and fog, remove Rain/Drizzle bolding
    text = re.sub(r'(\b\d{4}\b)', r'<b>\1</b>', text)
    text = re.sub(r'((BKN|OVC)\d{3})', r'<b>\1</b>', text)
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
    "MAD": {"icao": "LEMD", "lat": 40.494, "lon": -3.567, "rwy": 140, "fleet": "Cityflyer", "spec": False},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "JER": {"icao": "EGJJ", "lat": 49.208, "lon": -2.195, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "ALC": {"icao": "LEAL", "lat": 38.282, "lon": -0.558, "rwy": 100, "fleet": "Euroflyer", "spec": False},
}

# 5. SIDEBAR & MISSIONS
with st.sidebar:
    st.title("🛠️ MISSION CONTROL")
    uploaded_file = st.file_uploader("Upload report.csv", type="csv")
    selected_date = st.date_input("Select Date", datetime(2026, 2, 12))
    
    station_flights = {}
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file, skiprows=2)
            df.columns = df.columns.str.strip().str.upper()
            df = df.dropna(subset=['DATE', 'FLT'])
            df['DATE_DT'] = pd.to_datetime(df['DATE'], dayfirst=True, errors='coerce').dt.date
            day_flights = df[df['DATE_DT'] == selected_date]
            for _, row in day_flights.iterrows():
                for p in [str(row['DEP']).strip().upper(), str(row['ARR']).strip().upper()]:
                    if p not in station_flights: station_flights[p] = []
                    if row['FLT'] not in station_flights[p]: station_flights[p].append(row['FLT'])
            st.success(f"Linked {len(day_flights)} Flights")
        except: st.error("Schedule Link Error.")

    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)
    if st.button("🔄 REFRESH"): st.cache_data.clear(); st.rerun()

# 6. BACKGROUND FETCH
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
                    
                    # WINTER & HAZARD ONLY (EXCLUDE RA/DZ)
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

# 7. LOGIC & UI LOOP
metar_alerts, taf_alerts, map_markers = {}, {}, []
for iata, info in base_airports.items():
    data = weather_data.get(iata)
    if not data: continue
    is_shown = (info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    color, m_issues, actual_str, forecast_str = "#008000", [], "STABLE", "NIL"
    
    if data['status'] == "online":
        xw = calculate_xwind(data['w_dir'], max(data['w_spd'], data['w_gst']), info['rwy'])
        raw_m = data['raw_m'].upper()
        
        # ACTUAL (No RA/DZ)
        if any(x in raw_m for x in [" SN ", "-SN ", "FZRA", "FZDZ"]): m_issues.append("WINTER"); color = "#d6001a"
        if "FG" in raw_m: m_issues.append("FOG"); color = "#d6001a" if data['vis'] < v_lim else "#eb8f34"
        if data['vis'] < v_lim: m_issues.append("VIS"); color = "#d6001a"
        if data.get("cig", 9999) < c_lim: m_issues.append("CLOUD"); color = "#d6001a"
        if xw >= 25: m_issues.append("XWIND"); color = "#d6001a"
        
        if is_shown:
            if m_issues: actual_str = "/".join(m_issues); metar_alerts[iata] = {"type": actual_str, "hex": "primary"}
            if data['f_issues']:
                p_tag = " prob" if data['f_prob'] else ""
                forecast_str = f"{'+'.join(data['f_issues'])}{p_tag} @ {data['f_time']}"
                taf_alerts[iata] = {"type": "+".join(data['f_issues']), "time": data['f_time'], "prob": data['f_prob'], "hex": "secondary"}
                if color == "#008000": color = "#eb8f34"

    if is_shown:
        r1, r2 = int(info['rwy']/10), int(((info['rwy']+180)%360)/10)
        flights = ", ".join(station_flights.get(iata, ["No Flights"]))
        popup_html = f"""<div style="width:550px; color:black !important; font-family:monospace; font-size:14px;"><b style="color:#002366; font-size:18px;">{iata} STATUS</b><div style="margin-top:8px; padding:10px; border-left:6px solid {color}; background:#f9f9f9; font-size:16px;"><b>Missions:</b> {flights}<br><b>RWY {r1:02d}/{r2:02d} X-Wind:</b> {xw} KT<br><b>ACTUAL:</b> {actual_str}<br><b>FORECAST:</b> {forecast_str}</div><hr><div style="display:flex; gap:12px;"><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>METAR</b><br>{bold_hazard(data['raw_m'])}</div><div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>TAF</b><br>{bold_hazard(data['raw_t'])}</div></div></div>"""
        map_markers.append({"lat": info['lat'], "lon": info['lon'], "color": color, "popup": popup_html})

# 8. RENDER
st.markdown(f'<div class="ba-header"><div>OCC WINTER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter", scrollWheelZoom=False)
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(mkr['popup'], max_width=700)).add_to(m)
st_folium(m, width=1200, height=1200)

st.markdown('<div class="section-header">🔴 Actual Alerts (METAR)</div>', unsafe_allow_html=True)
if metar_alerts:
    cols = st.columns(5)
    for i, (iata, d) in enumerate(metar_alerts.items()):
        cols[i % 5].button(f"{iata} NOW {d['type']}", key=f"m_{iata}", type="primary")

st.markdown('<div class="section-header">🟠 Forecast Alerts (TAF)</div>', unsafe_allow_html=True)
if taf_alerts:
    cols_f = st.columns(5)
    for i, (iata, d) in enumerate(taf_alerts.items()):
        p_tag = " prob" if d['prob'] else ""
        cols_f[i % 5].button(f"{iata} {d['time']} {d['type']}{p_tag}", key=f"f_{iata}", type="secondary")
