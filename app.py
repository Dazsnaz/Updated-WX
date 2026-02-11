import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. HUD STYLING
st.markdown("""
    <style>
    /* TITLES & HEADERS - NAVY BLUE */
    .section-header { color: #002366 !important; font-weight: bold; font-size: 1.5rem; margin-top: 20px; border-bottom: 2px solid #d6001a; padding-bottom: 5px; }
    
    /* GLOBAL TEXT DEFAULT */
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    
    /* HANDOVER TEXT AREA FIX - DARK TEXT ON LIGHT BG */
    [data-testid="stTextArea"] textarea { 
        color: #002366 !important; 
        background-color: #ffffff !important; 
        font-weight: bold; 
        font-family: 'Courier New', monospace;
        border: 2px solid #002366 !important;
    }
    
    /* SIDEBAR LOCK */
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 250px !important; }
    [data-testid="stSidebar"] .stTextInput input { color: #002366 !important; background-color: white !important; font-weight: bold; }
    
    /* HORIZONTAL ALIGNMENT FIX */
    .stButton > button { 
        background-color: #005a9c !important; 
        color: white !important; 
        border: 1px solid white !important; 
        width: 100%; 
        text-transform: uppercase; 
        font-size: 0.52rem !important; 
        height: 60px !important; 
        line-height: 1.1 !important; 
        white-space: pre-wrap !important; 
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
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

# 4. MASTER DATABASE (FULL 46 STATIONS)
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer", "spec": True},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer", "spec": False},
    "MAD": {"icao": "LEMD", "lat": 40.494, "lon": -3.567, "rwy": 140, "fleet": "Cityflyer", "spec": False},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "JER": {"icao": "EGJJ", "lat": 49.208, "lon": -2.195, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer", "spec": True},
    "FNC": {"icao": "LPMA", "lat": 32.694, "lon": -16.774, "rwy": 50, "fleet": "Euroflyer", "spec": True},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "RTM": {"icao": "EHRD", "lat": 51.957, "lon": 4.440, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "Cityflyer", "spec": False},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer", "spec": True},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 180, "fleet": "Cityflyer", "spec": True},
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
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "fleet": "Cityflyer", "spec": False},
    "GVA": {"icao": "LSGG", "lat": 46.237, "lon": 6.109, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "BER": {"icao": "EDDB", "lat": 52.362, "lon": 13.501, "rwy": 250, "fleet": "Cityflyer", "spec": False},
    "FRA": {"icao": "EDDF", "lat": 50.033, "lon": 8.571, "rwy": 250, "fleet": "Cityflyer", "spec": False},
    "LIN": {"icao": "LIML", "lat": 45.445, "lon": 9.277, "rwy": 360, "fleet": "Cityflyer", "spec": False},
    "IBZ": {"icao": "LEIB", "lat": 38.873, "lon": 1.373, "rwy": 60, "fleet": "Cityflyer", "spec": False},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "AGP": {"icao": "LEMG", "lat": 36.675, "lon": -4.499, "rwy": 130, "fleet": "Cityflyer", "spec": False},
    "FAO": {"icao": "LPFR", "lat": 37.017, "lon": -7.965, "rwy": 280, "fleet": "Cityflyer", "spec": False},
    "SEN": {"icao": "EGMC", "lat": 51.571, "lon": 0.701, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "ALG": {"icao": "DAAG", "lat": 36.691, "lon": 3.215, "rwy": 230, "fleet": "Euroflyer", "spec": False},
}

# 5. SESSION STATE
if 'manual_stations' not in st.session_state: st.session_state.manual_stations = {}
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

# 6. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND SETTINGS")
    if st.button("🔄 MANUAL DATA REFRESH"):
        st.cache_data.clear(); st.rerun()
    map_theme = st.radio("MAP THEME", ["Dark Mode", "Light Mode"])
    
    st.markdown("---")
    st.markdown("📊 **FLEET X-WIND LIMITS**")
    st.markdown("""
    <table class="limits-table">
        <tr><th>FLEET</th><th>DRY</th><th>WET</th></tr>
        <tr><td><b>A320/321</b></td><td>38 kt</td><td>33 kt</td></tr>
        <tr><td><b>E190/170</b></td><td>30 kt</td><td>25 kt</td></tr>
        <tr><td><b>ATR-72</b></td><td>27 kt</td><td>27 kt</td></tr>
    </table>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    with st.form("manual_add", clear_on_submit=True):
        new_iata, new_icao = st.text_input("IATA").upper(), st.text_input("ICAO").upper()
        if st.form_submit_button("Add Station"):
            try:
                m = Metar(new_icao); m.update()
                st.session_state.manual_stations[new_iata] = {"icao": new_icao, "lat": m.data.station.latitude, "lon": m.data.station.longitude, "rwy": 0, "fleet": "Ad-Hoc", "spec": False}
                st.cache_data.clear(); st.rerun()
            except: st.error("Invalid ICAO")

# 7. DATA FETCH
all_stations = {**base_airports, **st.session_state.manual_stations}

@st.cache_data(ttl=600)
def get_intel(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
            
            w_vis, w_cig, w_issue, w_time, w_prob = 9999, 9999, None, "", False
            if t.data:
                for line in t.data.forecast:
                    v = line.visibility.value if line.visibility else 9999
                    c = 9999
                    if line.clouds:
                        for lyr in line.clouds:
                            if lyr.type in ['BKN', 'OVC'] and lyr.base: c = min(c, lyr.base * 100)
                    
                    issue = None
                    if info['fleet'] == "Cityflyer" and ("FZRA" in line.raw or "FZDZ" in line.raw): issue = "CLOSED-FZRA"
                    elif v < v_lim or c < c_lim: issue = "MINIMA"
                    elif v < (v_lim * 2) or c < (c_lim * 2): issue = "MARGINAL"
                    elif "TSRA" in line.raw: issue = "TSRA"
                    
                    if issue and (v < w_vis or issue == "CLOSED-FZRA"):
                        w_vis, w_cig, w_issue, w_prob = v, c, issue, ("PROB" in line.raw)
                        w_time = f"{line.start_time.dt.strftime('%H')}-{line.end_time.dt.strftime('%H')}Z"
                        if issue == "CLOSED-FZRA": break
            
            res[iata] = {
                "vis": m.data.visibility.value if m.data.visibility else 9999,
                "cig": 9999, "w_dir": m.data.wind_direction.value if m.data.wind_direction else 0,
                "w_spd": m.data.wind_speed.value if m.data.wind_speed else 0,
                "w_gst": m.data.wind_gust.value if m.data.wind_gust else 0,
                "raw_m": m.raw, "raw_t": t.raw, "status": "online",
                "f_issue": w_issue, "f_time": w_time, "f_prob": w_prob
            }
            if m.data.clouds:
                for lyr in m.data.clouds:
                    if lyr.type in ['BKN', 'OVC'] and lyr.base: res[iata]["cig"] = min(res[iata]["cig"], lyr.base * 100)
        except: res[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A", "f_issue": None}
    return res

weather_data = get_intel(all_stations)

# 8. ALERT PROCESSING
metar_alerts = {}; taf_alerts = {}; green_stations = []; map_markers = []
for iata, data in weather_data.items():
    info = all_stations[iata]
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    color = "#008000"
    
    if data['status'] == "online":
        m_type = None
        xw = calculate_xwind(data.get('w_dir', 0), max(data.get('w_spd', 0), data.get('w_gst', 0)), info['rwy'])
        
        if info['fleet'] == "Cityflyer" and ("FZRA" in data['raw_m'] or "FZDZ" in data['raw_m']):
            m_type = "CLOSED-FZRA"; color = "#d6001a"
        elif data['vis'] < v_lim or data['cig'] < c_lim:
            m_type = "MINIMA"; color = "#d6001a"
        elif xw > 25:
            m_type = "X-WIND"; color = "#eb8f34"
        elif "TSRA" in data['raw_m']:
            m_type = "TSRA"; color = "#eb8f34"

        if m_type: metar_alerts[iata] = {"type": m_type, "hex": "primary" if color == "#d6001a" else "secondary"}
        else: green_stations.append(iata)

        if data['f_issue']:
            t_hex = "primary" if data['f_issue'] in ["MINIMA", "CLOSED-FZRA"] else "secondary"
            taf_alerts[iata] = {"type": data['f_issue'], "time": data['f_time'], "prob": data['f_prob'], "hex": t_hex}
            if color == "#008000": color = "#eb8f34"

    # MAP POPUP HORIZONTAL
    popup_html = f"""
    <div style="width:500px; color:black !important; font-family:monospace; font-size:12px;">
        <b style="color:#002366;">{iata} STATION DATA</b><hr>
        <div style="display:flex; gap:10px;">
            <div style="flex:1; background:#f0f0f0; padding:8px; border-radius:3px;"><b>METAR</b><br>{data['raw_m']}</div>
            <div style="flex:1; background:#f0f0f0; padding:8px; border-radius:3px;"><b>TAF</b><br>{data['raw_t']}</div>
        </div>
    </div>
    """
    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "popup": popup_html})

# --- UI RENDER ---
st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)

# 9. SQUARE MAP
tile = "CartoDB dark_matter" if map_theme == "Dark Mode" else "CartoDB positron"
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles=tile)
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(mkr['popup'], max_width=600)).add_to(m)
st_folium(m, width=800, height=800, key="map_v36")

# 10. ALERTS
st.markdown('<div class="section-header">🔴 Actual Alerts (METAR)</div>', unsafe_allow_html=True)
if metar_alerts:
    cols = st.columns(10)
    for i, (iata, d) in enumerate(metar_alerts.items()):
        with cols[i % 10]:
            if st.button(f"{iata}\nNOW\n{d['type']}", key=f"m_{iata}", type=d['hex']): st.session_state.investigate_iata = iata

st.markdown('<div class="section-header">🟠 Forecast Alerts (TAF)</div>', unsafe_allow_html=True)
if taf_alerts:
    cols_f = st.columns(10)
    for i, (iata, d) in enumerate(taf_alerts.items()):
        with cols_f[i % 10]:
            p_tag = "\nPROB40" if d['prob'] else ""
            if st.button(f"{iata}\n{d['time']}\n{d['type']}{p_tag}", key=f"f_{iata}", type=d['hex']): st.session_state.investigate_iata = iata

# 11. ANALYSIS
if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d = weather_data.get(iata, {})
    info = all_stations.get(iata, {"rwy": 0, "lat": 0, "lon": 0})
    m_alert = metar_alerts.get(iata, {})
    f_alert = taf_alerts.get(iata, {})
    
    issue = f_alert.get('type') if f_alert else m_alert.get('type', "STABLE")
    period = f_alert.get('time', "CURRENT")
    xw_val = calculate_xwind(d.get('w_dir', 0), max(d.get('w_spd', 0), d.get('w_gst', 0)), info['rwy'])
    
    alt_iata, min_dist = "None", 9999
    for g in green_stations:
        if g != iata:
            dist = calculate_dist(info['lat'], info['lon'], all_stations[g]['lat'], all_stations[g]['lon'])
            if dist < min_dist: min_dist = dist; alt_iata = g

    impact = "Operational limits breached. Verify aircraft capability and crew currency."
    if "CLOSED" in issue: impact = "STATION CLOSED for Embraer fleet (FZRA/FZDZ limits)."
    if "MINIMA" in issue: impact = "LVP operations. CAT3 aircraft advised. Alternate fuel required."

    st.markdown(f"""
    <div class="reason-box">
        <h3>{iata} Strategy Brief: {issue}</h3>
        <p><b>Weather Summary:</b> Issue detected for {period} window. Live X-Wind: {xw_val}kt (RWY {info['rwy']}°).</p>
        <p><b>Impact Statement:</b> {impact}</p>
        <p style="color:#d6001a !important; font-size:1.1rem;"><b>✈️ Strategic Alternate:</b> {alt_iata} ({min_dist} NM).</p>
        <hr>
        <div style="display:flex; gap:20px;">
            <div style="flex:1;"><b>METAR:</b><br><small>{d.get('raw_m')}</small></div>
            <div style="flex:1;"><b>TAF:</b><br><small>{d.get('raw_t')}</small></div>
        </div>
    </div>""", unsafe_allow_html=True)
    if st.button("Close Analysis"): st.session_state.investigate_iata = "None"; st.rerun()

# 12. HANDOVER (FIXED FONT VISIBILITY)
st.markdown('<div class="section-header">📝 Shift Handover Log</div>', unsafe_allow_html=True)
h_txt = f"HANDOVER {datetime.now().strftime('%H:%M')}Z\n" + "="*35 + "\n"
for iata, d in taf_alerts.items():
    h_txt += f"{iata}: {d['type']} ({d['time']}){' - PROB40' if d['prob'] else ''}\n"

# EXPLICITLY STYLED AREA
st.text_area("Handover Report:", value=h_txt, height=200, label_visibility="collapsed")
