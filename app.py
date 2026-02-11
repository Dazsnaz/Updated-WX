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
    .section-header { color: #002366 !important; font-weight: bold; font-size: 1.5rem; margin-top: 20px; border-bottom: 2px solid #d6001a; padding-bottom: 5px; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    [data-testid="stSidebar"] { background-color: #002366 !important; }
    [data-testid="stSidebar"] .stTextInput input { color: #002366 !important; background-color: white !important; font-weight: bold; }
    .stButton > button { background-color: #005a9c !important; color: white !important; border: 1px solid white !important; width: 100%; text-transform: uppercase; font-size: 0.55rem !important; height: 55px !important; line-height: 1.1 !important; white-space: pre-wrap !important; }
    .ba-header { background-color: #002366; padding: 20px; border-radius: 5px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
    div.stButton > button[kind="primary"] { background-color: #d6001a !important; }
    div.stButton > button[kind="secondary"] { background-color: #eb8f34 !important; }
    .reason-box { background-color: #ffffff; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; color: #002366 !important; }
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

# 4. MASTER DATABASE
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
}

# 5. DATA FETCH (V1.0 Logic + Deep Scan)
@st.cache_data(ttl=600)
def get_intel(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            
            # Deep Scan TAF for Worst Case
            w_vis, w_cig, w_issue, w_time, w_prob = 9999, 9999, None, "", False
            if t.data:
                for line in t.data.forecast:
                    v = line.visibility.value if line.visibility else 9999
                    c = 9999
                    if line.clouds:
                        for lyr in line.clouds:
                            if lyr.type in ['BKN', 'OVC'] and lyr.base: c = min(c, lyr.base * 100)
                    
                    # Logic Check (Matches V1.0 Marginal thresholds)
                    issue = None
                    if info['fleet'] == "Cityflyer" and ("FZRA" in line.raw or "FZDZ" in line.raw): issue = "CLOSED-FZRA"
                    elif v < 800 or c < 200: issue = "MINIMA"
                    elif v < 1600 or c < 500: issue = "MARGINAL"
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

weather_data = get_intel({**base_airports, **st.session_state.get('manual_stations', {})})

# 6. ALERT CLASSIFICATION
metar_alerts = {}; taf_alerts = {}; green_stations = []; map_markers = []
for iata, data in weather_data.items():
    info = base_airports.get(iata)
    if not info: continue
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    color = "#008000"
    
    if data['status'] == "online":
        m_type = None
        xw = calculate_xwind(data['w_dir'], max(data['w_spd'], data['w_gst']), info['rwy'])
        
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

    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "metar": data['raw_m'], "taf": data['raw_t']})

# --- UI RENDER ---
st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)
tile = "CartoDB dark_matter" if st.sidebar.radio("THEME", ["Dark", "Light"]) == "Dark" else "CartoDB positron"
m = folium.Map(location=[50.0, 10.0], zoom_start=4, tiles=tile)
for mkr in map_markers:
    popup = f"{mkr['iata']}\n\nMETAR: {mkr['metar']}\n\nTAF: {mkr['taf']}"
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(popup, parse_html=False)).add_to(m)
st_folium(m, width=800, height=800, key="map_v33")

# 7. ALERTS
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

# 8. ANALYSIS
if st.session_state.get('investigate_iata') != "None":
    iata = st.session_state.investigate_iata
    d = weather_data.get(iata, {})
    info = base_airports.get(iata, {"rwy": 0, "lat": 0, "lon": 0})
    
    w_spd = max(d.get('w_spd', 0), d.get('w_gst', 0))
    xw_val = calculate_xwind(d.get('w_dir', 0), w_spd, info['rwy'])
    
    alt_iata, min_dist = "None", 9999
    for g in green_stations:
        if g != iata:
            dist = calculate_dist(info['lat'], info['lon'], base_airports[g]['lat'], base_airports[g]['lon'])
            if dist < min_dist: min_dist = dist; alt_iata = g

    st.markdown(f"""
    <div class="reason-box">
        <h3>{iata} Strategy Brief</h3>
        <p><b>Crosswind Component:</b> {xw_val}kt (Primary RWY {info['rwy']}°)</p>
        <p style="color:#d6001a !important; font-size:1.1rem;"><b>✈️ Nearest Safe Alternate:</b> {alt_iata} ({min_dist} NM).</p>
        <hr><small>METAR: {d.get('raw_m')}<br>TAF: {d.get('raw_t')}</small>
    </div>""", unsafe_allow_html=True)
    if st.button("Close Analysis"): st.session_state.investigate_iata = "None"; st.rerun()
