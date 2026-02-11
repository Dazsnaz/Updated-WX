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
    html, body, [class*="st-"], div, p, h1, h2, h3, h4, label { color: white !important; }
    [data-testid="stSidebar"] { background-color: #002366 !important; }
    [data-testid="stSidebar"] .stTextInput input { color: #002366 !important; background-color: white !important; font-weight: bold; }
    .stButton > button { background-color: #005a9c !important; color: white !important; border: 1px solid white !important; width: 100%; text-transform: uppercase; font-size: 0.6rem !important; }
    .marquee { width: 100%; background-color: #d6001a; color: white; white-space: nowrap; overflow: hidden; padding: 12px; font-weight: bold; border-radius: 5px; margin-bottom: 15px; border: 2px solid white; }
    .marquee span { display: inline-block; padding-left: 100%; animation: marquee 25s linear infinite; }
    @keyframes marquee { 0% { transform: translate(0, 0); } 100% { transform: translate(-100%, 0); } }
    .ba-header { background-color: #002366; padding: 20px; border-radius: 5px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
    div.stButton > button[kind="primary"] { background-color: #d6001a !important; }
    div.stButton > button[kind="secondary"] { background-color: #eb8f34 !important; }
    .reason-box { background-color: #ffffff; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; color: #002366 !important; }
    .reason-box h3, .reason-box p, .reason-box b, .reason-box small, .reason-box span, .reason-box i { color: #002366 !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_dist(lat1, lon1, lat2, lon2):
    R = 3440.065 # Nautical Miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)

# 4. MASTER DATABASE (FULL 46 STATIONS)
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer", "spec": True},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer", "spec": False},
    "RTM": {"icao": "EHRD", "lat": 51.957, "lon": 4.440, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "Cityflyer", "spec": False},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "SEN": {"icao": "EGMC", "lat": 51.571, "lon": 0.701, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer", "spec": True},
    "AGP": {"icao": "LEMG", "lat": 36.675, "lon": -4.499, "rwy": 130, "fleet": "Cityflyer", "spec": False},
    "BER": {"icao": "EDDB", "lat": 52.362, "lon": 13.501, "rwy": 250, "fleet": "Cityflyer", "spec": False},
    "FRA": {"icao": "EDDF", "lat": 50.033, "lon": 8.571, "rwy": 250, "fleet": "Cityflyer", "spec": False},
    "LIN": {"icao": "LIML", "lat": 45.445, "lon": 9.277, "rwy": 360, "fleet": "Cityflyer", "spec": False},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 180, "fleet": "Cityflyer", "spec": True},
    "GVA": {"icao": "LSGG", "lat": 46.237, "lon": 6.109, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "fleet": "Cityflyer", "spec": False},
    "MAD": {"icao": "LEMD", "lat": 40.494, "lon": -3.567, "rwy": 140, "fleet": "Cityflyer", "spec": False},
    "IBZ": {"icao": "LEIB", "lat": 38.873, "lon": 1.373, "rwy": 60, "fleet": "Cityflyer", "spec": False},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "FAO": {"icao": "LPFR", "lat": 37.017, "lon": -7.965, "rwy": 280, "fleet": "Cityflyer", "spec": False},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "JER": {"icao": "EGJJ", "lat": 49.208, "lon": -2.195, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "OPO": {"icao": "LPPR", "lat": 41.242, "lon": -8.678, "rwy": 350, "fleet": "Euroflyer", "spec": False},
    "LYS": {"icao": "LFLL", "lat": 45.726, "lon": 5.090, "rwy": 350, "fleet": "Euroflyer", "spec": False},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer", "spec": True},
    "SZG": {"icao": "LOWS", "lat": 47.794, "lon": 13.004, "rwy": 330, "fleet": "Euroflyer", "spec": False},
    "BOD": {"icao": "LFBD", "lat": 44.828, "lon": -0.716, "rwy": 230, "fleet": "Euroflyer", "spec": False},
    "GNB": {"icao": "LFLS", "lat": 45.363, "lon": 5.330, "rwy": 90, "fleet": "Euroflyer", "spec": False},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "TRN": {"icao": "LIMF", "lat": 45.202, "lon": 7.649, "rwy": 360, "fleet": "Euroflyer", "spec": False},
    "VRN": {"icao": "LIPX", "lat": 45.396, "lon": 10.888, "rwy": 40, "fleet": "Euroflyer", "spec": False},
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
    "FNC": {"icao": "LPMA", "lat": 32.694, "lon": -16.774, "rwy": 50, "fleet": "Euroflyer", "spec": True},
    "ALG": {"icao": "DAAG", "lat": 36.691, "lon": 3.215, "rwy": 230, "fleet": "Euroflyer", "spec": False},
    "GRZ": {"icao": "LOWG", "lat": 46.991, "lon": 15.439, "rwy": 350, "fleet": "Euroflyer", "spec": False},
    "RBA": {"icao": "GMME", "lat": 34.051, "lon": -6.751, "rwy": 30, "fleet": "Euroflyer", "spec": False},
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

    with st.form("manual_add", clear_on_submit=True):
        new_iata = st.text_input("IATA SEARCH").upper()
        new_icao = st.text_input("ICAO").upper()
        if st.form_submit_button("Add Station"):
            try:
                m = Metar(new_icao); m.update()
                st.session_state.manual_stations[new_iata] = {"icao": new_icao, "lat": m.data.station.latitude, "lon": m.data.station.longitude, "rwy": 0, "fleet": "Ad-Hoc", "spec": False}
                st.cache_data.clear(); st.rerun()
            except: st.error("Invalid ICAO")

# 7. DATA FETCH
all_airports = {**base_airports, **st.session_state.manual_stations}

@st.cache_data(ttl=600)
def get_weather_intelligence(airport_dict):
    results = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update()
            t = Taf(info['icao']); t.update()
            
            f_vis, f_cig, f_issue = 9999, 9999, None
            if t.data:
                for line in t.data.forecast:
                    v = line.visibility.value if line.visibility else 9999
                    c = 9999
                    if line.clouds:
                        for layer in line.clouds:
                            if layer.type in ['BKN', 'OVC'] and layer.base: c = min(c, layer.base * 100)
                    
                    # Embraer icing check
                    if info['fleet'] == "Cityflyer" and ("FZRA" in line.raw or "FZDZ" in line.raw):
                        f_issue = "CLOSED-FZRA"
                        break
                    if v < 800 or c < 200: 
                        f_issue = "MINIMA"
                        f_vis, f_cig = v, c
                        break

            results[iata] = {
                "vis": m.data.visibility.value if m.data.visibility else 9999,
                "ceiling": 9999, "w_dir": m.data.wind_direction.value or 0, "w_spd": m.data.wind_speed.value or 0,
                "raw_m": m.raw, "raw_t": t.raw, "status": "online", "f_issue": f_issue
            }
            if m.data.clouds:
                for layer in m.data.clouds:
                    if layer.type in ['BKN', 'OVC'] and layer.base:
                        results[iata]["ceiling"] = min(results[iata]["ceiling"], layer.base * 100)
        except: results[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A", "f_issue": None}
    return results

weather_data = get_weather_intelligence(all_airports)

# 8. ALERT PROCESSING
metar_alerts = {}; taf_alerts = {}; red_list = []; green_stations = []; map_markers = []

for iata, data in weather_data.items():
    info = all_airports[iata]
    v_limit, c_limit = (1500, 500) if info['spec'] else (800, 200)
    xw = round(abs(data.get('w_spd', 0) * math.sin(math.radians(data.get('w_dir', 0) - info['rwy']))), 1) if info['rwy'] else 0
    color = "#008000"

    if data['status'] == "offline":
        color = "#808080"
    else:
        # Check Actuals (METAR)
        m_type = None
        if info['fleet'] == "Cityflyer" and ("FZRA" in data['raw_m'] or "FZDZ" in data['raw_m']):
            m_type = "CLOSED-FZRA"; color = "#d6001a"; red_list.append(iata)
        elif data['vis'] < v_limit or data['ceiling'] < c_limit:
            m_type = "MINIMA"; color = "#d6001a"; red_list.append(iata)
        elif xw > 25:
            m_type = "X-WIND"; color = "#eb8f34"
        elif "TSRA" in data['raw_m']:
            m_type = "TSRA"; color = "#eb8f34"

        if m_type:
            metar_alerts[iata] = {"type": m_type, "color": "primary" if color == "#d6001a" else "secondary"}
        else:
            green_stations.append(iata)

        # Check Forecasts (TAF)
        if data['f_issue']:
            taf_alerts[iata] = {"type": data['f_issue'], "color": "primary" if data['f_issue'] in ["MINIMA", "CLOSED-FZRA"] else "secondary"}
            if color == "#008000": color = "#eb8f34"

    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "metar": data['raw_m'], "taf": data['raw_t']})

# --- UI RENDER ---
if red_list: st.markdown(f'<div class="marquee"><span>🚨 CRITICAL: {", ".join(red_list)} AT MINIMA</span></div>', unsafe_allow_html=True)
st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)

# 9. MAP
tile = "CartoDB dark_matter" if map_theme == "Dark Mode" else "CartoDB positron"
m = folium.Map(location=[45.0, 5.0], zoom_start=5, tiles=tile)
for mkr in map_markers:
    popup_txt = f"<b>{mkr['iata']}</b><br><br>METAR: {mkr['metar']}<br><br>TAF: {mkr['taf']}"
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(popup_txt, max_width=300)).add_to(m)
st_folium(m, width=1400, height=500, key="map_main")

# 10. ALERTS
st.subheader("🔴 Actual Alerts (METAR)")
if metar_alerts:
    cols = st.columns(10)
    for i, (iata, d) in enumerate(metar_alerts.items()):
        with cols[i % 10]:
            if st.button(f"{iata}: {d['type']}", key=f"m_{iata}", type=d['color']): st.session_state.investigate_iata = iata

st.subheader("🟠 Forecast Alerts (TAF)")
if taf_alerts:
    cols_f = st.columns(10)
    for i, (iata, d) in enumerate(taf_alerts.items()):
        with cols_f[i % 10]:
            if st.button(f"{iata}: {d['type']}", key=f"f_{iata}", type=d['color']): st.session_state.investigate_iata = iata

# 11. ANALYSIS
if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d = weather_data.get(iata)
    info = all_airports[iata]
    
    # Alternate Logic
    alt_iata, min_dist = "None", 9999
    for g in green_stations:
        if g != iata:
            dist = calculate_dist(info['lat'], info['lon'], all_airports[g]['lat'], all_airports[g]['lon'])
            if dist < min_dist: min_dist = dist; alt_iata = g

    st.markdown(f"""
    <div class="reason-box">
        <h3>{iata} Strategy Brief</h3>
        <p><b>Impact Statement:</b> Operational limits breached. Check aircraft capability.</p>
        <p style="color:#d6001a !important; font-size:1.1em;"><b>✈️ Strategic Alternate:</b> {alt_iata} ({min_dist} NM).</p>
        <hr><small>METAR: {d['raw_m']}<br>TAF: {d['raw_t']}</small>
    </div>""", unsafe_allow_html=True)
    if st.button("Close Analysis"): st.session_state.investigate_iata = "None"; st.rerun()
