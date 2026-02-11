import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. ADAPTIVE HUD STYLING
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="st-"], div, p, h1, h2, h3, h4, label { font-family: 'Inter', sans-serif !important; }
    
    /* SIDEBAR */
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 300px !important; }
    [data-testid="stSidebar"] .stTextInput input { color: #002366 !important; background-color: white !important; font-weight: bold; }

    /* SECTION TITLES */
    .section-title { 
        color: #002366 !important; 
        font-weight: 800; 
        font-size: 1.1rem; 
        margin-top: 25px; 
        margin-bottom: 10px;
        border-bottom: 2px solid #d6001a; 
        padding-bottom: 3px;
        text-transform: uppercase;
    }
    
    /* ADAPTIVE FLEX CONTAINER */
    .flex-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        width: 100%;
        margin-bottom: 20px;
    }

    /* ADAPTIVE ALERT BUTTONS */
    .stButton > button { 
        color: white !important; 
        border: 1px solid rgba(255,255,255,0.4) !important; 
        text-transform: uppercase; 
        font-size: 0.65rem !important; 
        font-weight: 700 !important;
        padding: 6px 12px !important;
        line-height: 1.2 !important;
        height: auto !important; 
        min-height: 55px;
        white-space: pre !important; /* Keeps the vertical stack of info */
        display: inline-block !important;
        width: auto !important; /* Adaptive width */
        border-radius: 4px !important;
    }
    
    /* PRIMARY (RED) & SECONDARY (AMBER) */
    div.stButton > button[kind="primary"] { background-color: rgba(214, 0, 26, 0.9) !important; border: 1px solid #d6001a !important; }
    div.stButton > button[kind="secondary"] { background-color: rgba(235, 143, 52, 0.9) !important; border: 1px solid #eb8f34 !important; }

    .ba-header { background-color: #002366; padding: 20px; border-radius: 5px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #d6001a; color: white !important; }
    
    .reason-box { background-color: #ffffff; border: 1px solid #ddd; padding: 20px; border-radius: 5px; margin-top: 20px; border-left: 10px solid #d6001a; color: #002366 !important; }
    
    [data-testid="stTextArea"] textarea { color: #002366 !important; background-color: #ffffff !important; font-weight: bold; border: 1px solid #999 !important; font-family: monospace; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_dist(lat1, lon1, lat2, lon2):
    R = 3440.065 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)

# 4. MASTER DATABASE (FULL 46 STATIONS)
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer", "spec": True},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer", "spec": False},
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
    "SEN": {"icao": "EGMC", "lat": 51.571, "lon": 0.701, "rwy": 230, "fleet": "Cityflyer", "spec": False},
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
    "MAD": {"icao": "LEMD", "lat": 40.494, "lon": -3.567, "rwy": 140, "fleet": "Cityflyer", "spec": False},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "IBZ": {"icao": "LEIB", "lat": 38.873, "lon": 1.373, "rwy": 60, "fleet": "Cityflyer", "spec": False},
    "AGP": {"icao": "LEMG", "lat": 36.675, "lon": -4.499, "rwy": 130, "fleet": "Cityflyer", "spec": False},
    "FAO": {"icao": "LPFR", "lat": 37.017, "lon": -7.965, "rwy": 280, "fleet": "Cityflyer", "spec": False},
}

# 5. DATA FETCH
if 'manual_stations' not in st.session_state: st.session_state.manual_stations = {}
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

@st.cache_data(ttl=600)
def get_occ_intel(airport_dict):
    results = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
            f_issue = None
            if t.data:
                for line in t.data.forecast:
                    v = line.visibility.value if line.visibility else 9999
                    c = 9999
                    gust = line.wind_gust.value if line.wind_gust else 0
                    if line.clouds:
                        for lyr in line.clouds:
                            if lyr.type in ['BKN', 'OVC'] and lyr.base: c = min(c, lyr.base * 100)
                    
                    reason = None
                    if info['fleet'] == "Cityflyer" and 200 <= v <= 550: reason = "CAT3-ONLY"
                    elif "TSRA" in line.raw: reason = "TSRA"
                    elif gust >= 35: reason = "GUST"
                    elif v < v_lim: reason = "VIS"
                    elif c < c_lim: reason = "CLOUD"
                    
                    if reason:
                        f_issue = {"type": reason, "v": v, "c": c, "p": f"{line.start_time.dt.strftime('%H')}-{line.end_time.dt.strftime('%H')}Z"}
                        break

            results[iata] = {
                "vis": m.data.visibility.value if m.data.visibility else 9999,
                "cig": 9999, "raw_m": m.raw, "raw_t": t.raw, "status": "online", "f": f_issue
            }
            if m.data.clouds:
                for lyr in m.data.clouds:
                    if lyr.type in ['BKN', 'OVC'] and lyr.base: results[iata]["cig"] = min(results[iata]["cig"], lyr.base * 100)
        except: results[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A", "f": None}
    return results

weather_intel = get_occ_intel({**base_airports, **st.session_state.manual_stations})

# 6. ALERT CLASSIFICATION
metar_alerts = {}; taf_alerts = {}; green_stations = []; map_markers = []
for iata, info in {**base_airports, **st.session_state.manual_stations}.items():
    data = weather_intel.get(iata, {"status": "offline"})
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    marker_color = "#008000"

    if data['status'] == "online":
        m_reason = None
        if data['vis'] < v_lim or data['cig'] < c_lim: m_reason = "MINIMA"; marker_color = "#d6001a"
        elif "TSRA" in data['raw_m']: m_reason = "TSRA"; marker_color = "#eb8f34"

        if m_reason: metar_alerts[iata] = {"type": m_reason, "hex": "primary" if marker_color=="#d6001a" else "secondary"}
        else: green_stations.append(iata)

        if data['f']:
            f = data['f']
            taf_alerts[iata] = {"type": f['type'], "period": f['p'], "hex": "primary" if f['v'] < v_lim else "secondary"}
            if marker_color == "#008000": marker_color = "#eb8f34"

    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": marker_color, "metar": data['raw_m'], "taf": data['raw_t']})

# --- UI RENDER ---
with st.sidebar:
    st.title("🛠️ COMMAND SETTINGS")
    if st.button("🔄 MANUAL DATA REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    with st.form("manual_add"):
        st.subheader("Add Station")
        new_iata = st.text_input("IATA").upper()
        new_icao = st.text_input("ICAO").upper()
        if st.form_submit_button("Add Station"):
            try:
                m = Metar(new_icao); m.update()
                st.session_state.manual_stations[new_iata] = {"icao": new_icao, "lat": m.data.station.latitude, "lon": m.data.station.longitude, "rwy": 0, "fleet": "Ad-Hoc", "spec": False}
                st.cache_data.clear(); st.rerun()
            except: st.error("Invalid ICAO")

st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)

# 7. MAP
m = folium.Map(location=[48.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")
for mkr in map_markers:
    popup_html = f"<div style='color:black; width:400px; font-family:monospace;'><b>{mkr['iata']}</b><hr><b>METAR:</b> {mkr['metar']}<br><b>TAF:</b> {mkr['taf']}</div>"
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=6, color=mkr['color'], fill=True, popup=folium.Popup(popup_html, max_width=500)).add_to(m)
st_folium(m, width=1400, height=400, key="map_v15")

# 8. ADAPTIVE ALERT ROWS
st.markdown('<div class="section-title">🔴 ACTUAL WEATHER ALERTS (METAR)</div>', unsafe_allow_html=True)
st.markdown('<div class="flex-container">', unsafe_allow_html=True)
for iata, d in metar_alerts.items():
    if st.button(f"{iata}\nNOW\n{d['type']}", key=f"m_{iata}", type=d['hex']): st.session_state.investigate_iata = iata
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">🟠 FORECAST ALERTS (TAF)</div>', unsafe_allow_html=True)
st.markdown('<div class="flex-container">', unsafe_allow_html=True)
for iata, d in taf_alerts.items():
    if st.button(f"{iata}\n{d['period']}\n{d['type']}", key=f"t_{iata}", type=d['hex']): st.session_state.investigate_iata = iata
st.markdown('</div>', unsafe_allow_html=True)

# 9. ANALYSIS BOX
if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d = weather_intel.get(iata)
    issue = metar_alerts[iata]['type'] if iata in metar_alerts else (taf_alerts[iata]['type'] if iata in taf_alerts else "N/A")
    period = "CURRENT" if iata in metar_alerts else (taf_alerts[iata]['period'] if iata in taf_alerts else "N/A")
    
    alt_iata, min_dist = "None", 9999
    all_airp = {**base_airports, **st.session_state.manual_stations}
    for g in green_stations:
        dist = calculate_dist(all_airp[iata]['lat'], all_airp[iata]['lon'], all_airp[g]['lat'], all_airp[g]['lon'])
        if dist < min_dist: min_dist = dist; alt_iata = g

    st.markdown(f"""
    <div class="reason-box">
        <h3>{iata} Strategy Brief</h3>
        <p><b>Weather Summary:</b> Issue: {issue} | Period: {period}</p>
        <p><b>Impact Statement:</b> Operational limits breached or forecasted. High likelihood of ATC flow restrictions.</p>
        <p style="color:#d6001a !important; font-weight:bold;">✈️ Strategic Alternate: {alt_iata} ({min_dist} NM)</p>
        <hr><small><b>METAR:</b> {d['raw_m']}<br><b>TAF:</b> {d['raw_t']}</small>
    </div>""", unsafe_allow_html=True)
    if st.button("Close Analysis"): st.session_state.investigate_iata = "None"; st.rerun()

# 10. HANDOVER
st.markdown('<div class="section-title">📝 SHIFT HANDOVER SUMMARY</div>', unsafe_allow_html=True)
h_txt = f"SHIFT HANDOVER {datetime.now().strftime('%H:%M')}Z\n" + "="*35 + "\n"
for iata, d in taf_alerts.items():
    h_txt += f"{iata} {d['type']} ({d['period']}) - CAT3 Aircraft Advised\n"
st.text_area("Handover Report Copy:", value=h_txt, height=150, label_visibility="collapsed")
