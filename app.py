import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
import re
from datetime import datetime, timedelta, timezone

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. HUD STYLING (NAVY & CONTRAST LOCK)
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

    .stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }
    .stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; border: 1px solid white !important; font-weight: bold !important; }

    [data-testid="stTextArea"] textarea { 
        color: #002366 !important; 
        background-color: #ffffff !important; 
        font-weight: bold !important; 
        font-family: 'Courier New', monospace !important; 
    }

    .reason-box { background-color: #ffffff !important; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .reason-box * { color: #002366 !important; }
    
    .section-header { color: #ffffff !important; background-color: #002366; padding: 10px; border-left: 10px solid #d6001a; font-weight: bold; font-size: 1.5rem; margin-top: 30px; }
    
    .leaflet-tooltip, .leaflet-popup-content-wrapper { 
        background: white !important; 
        border: 2px solid #002366 !important; 
        padding: 0 !important; 
        opacity: 1 !important; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.5) !important;
        min-width: 580px !important;
        white-space: normal !important;
    }
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
    text = re.sub(r'(\b\d{4}/\d{4}\b)', r'<b>\1</b>', text)
    text = re.sub(r'(\b\d{3}\d{2}G\d{2,3}KT\b)', r'<b>\1</b>', text)
    text = re.sub(r'(\b(FG|TSRA|SN|-SN|FZRA|FZDZ|TS|FOG)\b)', r'<b>\1</b>', text)
    text = re.sub(r'\b((?:BKN|OVC)00[0-9])\b', r'<b>\1</b>', text)
    text = re.sub(r'\b((?:BKN|OVC)01[0-5])\b', r'<b>\1</b>', text)
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

# 6. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 MANUAL DATA REFRESH"):
        st.cache_data.clear(); st.rerun()
    st.markdown("---")
    st.markdown("🕒 **INTEL HORIZON**")
    time_horizon = st.radio("SCAN WINDOW", ["Next 6 Hours", "Next 12 Hours", "Next 24 Hours"], index=0)
    horizon_hours = 6 if "6" in time_horizon else (12 if "12" in time_horizon else 24)
    st.markdown("---")
    st.markdown("⚠️ **SAFETY LIMITS**")
    xw_limit = st.slider("X-WIND LIMIT (KT)", 15, 35, 25)
    st.markdown("---")
    hazard_filter = st.selectbox("ISOLATE HAZARD", ["Show All Network", "Any Amber/Red Alert", "XWIND", "WINDY (Gusts >25)", "FOG", "WINTER (Snow/FZRA)", "TSRA", "VIS (<Limits)", "LOW CLOUD (<Limits)"])
    st.markdown("---")
    show_cf = st.checkbox("Cityflyer (CFE)", value=True)
    show_ef = st.checkbox("Euroflyer (EFW)", value=True)
    st.markdown("---")
    map_theme = st.radio("MAP THEME", ["Dark Mode", "Light Mode"])

# 7. DATA FETCH (30 MIN REFRESH)
@st.cache_data(ttl=1800)
def get_raw_weather_master(airport_dict):
    raw_res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            raw_res[iata] = {"m_obj": m, "t_obj": t, "status": "online"}
        except: raw_res[iata] = {"status": "offline"}
    return raw_res

raw_weather_bundle = get_raw_weather_master(base_airports)

# 8. PROCESSOR
def process_weather_for_horizon(bundle, airport_dict, horizon_limit, xw_threshold):
    processed = {}
    cutoff_time = datetime.now(timezone.utc) + timedelta(hours=horizon_limit)
    for iata, data in bundle.items():
        if data['status'] == "offline" or "m_obj" not in data:
            processed[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A", "f_issues": [], "f_wind_spd":0, "f_wind_dir":0, "f_prob": False}
            continue
        m, t, info = data['m_obj'], data['t_obj'], airport_dict[iata]
        v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
        m_vis = m.data.visibility.value if (m.data and m.data.visibility) else 9999
        m_cig = 9999
        if m.data and m.data.clouds:
            for lyr in m.data.clouds:
                if lyr.type in ['BKN', 'OVC'] and lyr.base: m_cig = min(m_cig, lyr.base * 100)
        
        w_issues, f_wind_spd, f_wind_dir, w_time, w_prob = [], 0, 0, "", False
        if t.data:
            for line in t.data.forecast:
                if not line.start_time or not hasattr(line.start_time, 'dt'): continue
                if line.start_time.dt > cutoff_time: continue
                l_raw = line.raw.upper()
                l_issues = []
                l_v = line.visibility.value if (line.visibility and line.visibility.value is not None) else 9999
                l_c = 9999
                if line.clouds:
                    for lyr in line.clouds:
                        if lyr.type in ['BKN', 'OVC'] and lyr.base: l_c = min(l_c, lyr.base * 100)
                if re.search(r'\bFG\b', l_raw): l_issues.append("FOG")
                if re.search(r'\bSN\b|\bFZ', l_raw): l_issues.append("WINTER")
                if l_v < v_lim: l_issues.append("VIS")
                if l_c < c_lim: l_issues.append("CLOUD")
                if re.search(r'\bTS|VCTS', l_raw): l_issues.append("TSRA")
                l_dir = line.wind_direction.value if (line.wind_direction and line.wind_direction.value) else info['rwy']
                l_spd = line.wind_speed.value if (line.wind_speed and line.wind_speed.value) else 0
                l_gst = line.wind_gust.value if (line.wind_gust and line.wind_gust.value) else 0
                peak = max(l_spd, l_gst)
                if calculate_xwind(l_dir, peak, info['rwy']) >= xw_threshold: l_issues.append("XWIND")
                elif peak > 25: l_issues.append("WINDY")
                if l_issues:
                    for iss in l_issues:
                        if iss not in w_issues: w_issues.append(iss)
                    w_time = f"{line.start_time.dt.strftime('%H')}Z"
                    f_wind_spd, f_wind_dir, w_prob = peak, l_dir, ("PROB" in l_raw)

        processed[iata] = {
            "vis": m_vis, "cig": m_cig, "status": "online",
            "w_dir": m.data.wind_direction.value if (m.data and m.data.wind_direction) else 0,
            "w_spd": m.data.wind_speed.value if (m.data and m.data.wind_speed) else 0,
            "w_gst": m.data.wind_gust.value if (m.data and m.data.wind_gust) else 0,
            "raw_m": m.raw
