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

# 2. HUD STYLING (V14.2 Foundation + Contrast Fixes)
st.markdown("""
    <style>
    .section-header { color: #002366 !important; font-weight: bold; font-size: 1.5rem; margin-top: 20px; border-bottom: 2px solid #d6001a; padding-bottom: 5px; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    [data-testid="stTextArea"] textarea { color: #002366 !important; background-color: #ffffff !important; font-weight: bold; font-family: 'Courier New', monospace; }
    
    /* SIDEBAR VISIBILITY FIXES */
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 300px !important; border-right: 2px solid #d6001a; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold !important; }
    
    /* Force high contrast for selectors and inputs */
    [data-testid="stSidebar"] div[data-baseweb="input"], 
    [data-testid="stSidebar"] div[data-baseweb="select"],
    [data-testid="stSidebar"] input,
    .stSelectbox div,
    .stDateInput div {
        background-color: #ffffff !important;
        color: #002366 !important;
        font-weight: bold !important;
    }
    div[role="listbox"] ul li { background-color: white !important; color: #002366 !important; }

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
    .reason-box h3, .reason-box p, .reason-box b, .reason-box small { color: #002366 !important; }
    .limits-table { width: 100%; font-size: 0.8rem; border-collapse: collapse; margin-top: 10px; color: white !important; }
    .limits-table td, .limits-table th { border: 1px solid rgba(255,255,255,0.2); padding: 4px; text-align: left; }
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
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "JER": {"icao": "EGJJ", "lat": 49.208, "lon": -2.195, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "ALC": {"icao": "LEAL", "lat": 38.282, "lon": -0.558, "rwy": 100, "fleet": "Euroflyer", "spec": False},
    "SZG": {"icao": "LOWS", "lat": 47.794, "lon": 13.004, "rwy": 330, "fleet": "Euroflyer", "spec": False},
    "FNC": {"icao": "LPMA", "lat": 32.694, "lon": -16.774, "rwy": 50, "fleet": "Euroflyer", "spec": True},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "Euroflyer", "spec": False},
}

# 5. SESSION STATE
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

# 6. SIDEBAR MISSION CONTROL
with st.sidebar:
    st.title("🛠️ MISSION CONTROL")
    uploaded_file = st.file_uploader("Upload report.csv", type="csv")
    selected_date = st.date_input("Select Date", datetime(2026, 2, 12))
    
    # 6.1 CSV PROCESSING (Strips empty rows automatically)
    station_flights = {}
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file, skiprows=2, on_bad_lines='skip')
            df.columns = df.columns.str.strip().str.upper()
            df = df.dropna(subset=['DATE', 'FLT']) # Drop spacer rows
            
            # Match date format
            df['DATE_DT'] = pd.to_datetime(df['DATE'], dayfirst=True, errors='coerce').dt.date
            day_flights = df[df['DATE_DT'] == selected_date]
            
            # Map flight numbers to stations
            for _, row in day_flights.iterrows():
                for port in [str(row['DEP']), str(row['ARR'])]:
                    p = port.strip().upper()
                    if p not in station_flights: station_flights[p] = []
                    if row['FLT'] not in station_flights[p]: station_flights[p].append(row['FLT'])
            
            st.success(f"Linked {len(day_flights)} Flights")
        except Exception as e:
            st.error("Error processing schedule file.")

    st.markdown("---")
    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)
    if st.button("🔄 MANUAL DATA REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    st.markdown("📊 **FLEET X-WIND LIMITS**")
    st.markdown("""<table class="limits-table"><tr><th>FLEET</th><th>DRY</th><th>WET</th></tr><tr><td><b>A320/321</b></td><td>38 kt</td><td>33 kt</td></tr><tr><td><b>E190/170</b></td><td>30 kt</td><td>25 kt</td></tr></table>""", unsafe_allow_html=True)

# 7. DATA FETCH (STABLE BACKGROUND FETCH)
@st.cache_data(ttl=600)
def get_intel_global(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
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

weather_data = get_intel_global(base_airports)

# 8. ANALYTICS & UI LOOP
metar_alerts, taf_alerts, green_stations, map_markers = {}, {}, [], []
for iata, info in base_airports.items():
    data = weather_data.get(iata)
    if not data: continue
    is_shown = (info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    color, m_issues, actual_str, forecast_str = "#008000", [], "STABLE", "NIL"
    xw = 0
    
    if data['status'] == "online":
        xw = calculate_xwind(data.get('w_dir', 0), max(data.get('w_spd', 0), data.get('w_gst', 0)), info['rwy'])
        if info['fleet'] == "Cityflyer" and ("FZRA" in data['raw_m'] or "FZDZ" in data['raw_m']): m_issues.append("FZRA/DZ"); color = "#d6001a"
        if data['vis'] < v_lim: m_issues.append("VIS"); color = "#d6001a"
        if xw >= 25: m_issues.append("XWIND"); color = "#d6001a"
        
        if is_shown:
            if m_issues: actual_str = "/".join(m_issues); metar_alerts[iata] = {"type": actual_str, "hex": "primary"}
            else: green_stations.append(iata)
            # Basic TAF alert logic for v14.2
            if "TSRA" in data['raw_t'] or "FG" in data['raw_t']:
                forecast_str = "HAZARDS DETECTED"; color = "#eb8f34" if color == "#008000" else color
                taf_alerts[iata] = {"type": "WX", "time": "TBD", "prob": False, "hex": "secondary"}

    if is_shown:
        r1, r2 = int(info['rwy']/10), int(((info['rwy']+180)%360)/10)
        m_bold, t_bold = bold_hazard(data.get('raw_m', 'N/A')), bold_hazard(data.get('raw_t', 'N/A'))
        
        # 8.1 INJECT FLIGHT NUMBERS INTO POPUP
        flights_at_station = station_flights.get(iata, ["No Flights Found"])
        flight_list_html = ", ".join(flights_at_station)

        popup_html = f"""
        <div style="width:600px; color:black !important; font-family:monospace; font-size:14px;">
            <b style="color:#002366; font-size:18px;">{iata} STATUS</b>
            <div style="margin-top:8px; padding:10px; border-left:6px solid {color}; background:#f9f9f9; font-size:16px;">
                <b style="color:#002366;">RWY {r1:02d}/{r2:02d} Live X-Wind:</b> <span style="color:{'#d6001a' if xw >= 25 else 'black'}; font-weight:bold;">{xw} KT</span><br>
                <b style="color:#d6001a;">DAILY MISSIONS:</b> {flight_list_html}<br>
                <b>ACTUAL:</b> {actual_str}<br>
                <b>FORECAST:</b> {forecast_str}
            </div>
            <hr>
            <div style="display:flex; gap:12px;">
                <div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>METAR</b><br>{m_bold}</div>
                <div style="flex:1; background:#f0f0f0; padding:10px; border-radius:4px; font-size:14px;"><b>TAF</b><br>{t_bold}</div>
            </div>
        </div>"""
        map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "popup": popup_html})

# --- UI RENDER ---
st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles="CartoDB dark_matter", scrollWheelZoom=False)
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(mkr['popup'], max_width=700)).add_to(m)
st_folium(m, width=1200, height=1200, key="map_v18")

# 10. ALERTS
st.markdown('<div class="section-header">🔴 Actual Alerts (METAR)</div>', unsafe_allow_html=True)
if metar_alerts:
    cols = st.columns(5)
    for i, (iata, d) in enumerate(metar_alerts.items()):
        with cols[i % 5]:
            if st.button(f"{iata} NOW {d['type']}", key=f"m_{iata}", type="primary"): st.session_state.investigate_iata = iata

st.markdown('<div class="section-header">🟠 Forecast Alerts (TAF)</div>', unsafe_allow_html=True)
if taf_alerts:
    cols_f = st.columns(5)
    for i, (iata, d) in enumerate(taf_alerts.items()):
        with cols_f[i % 5]:
            if st.button(f"{iata} FORECAST {d['type']}", key=f"f_{iata}", type="secondary"): st.session_state.investigate_iata = iata
