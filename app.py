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
    /* SIDEBAR PERMANENCE */
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 300px !important; }
    [data-testid="stSidebar"] .stTextInput input { color: #002366 !important; background-color: white !important; font-weight: bold; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold; }

    /* SECTION TITLES - NAVY ON WHITE */
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
    
    /* MICRO-FONT TACTICAL BUTTONS */
    .stButton > button { 
        background-color: rgba(0, 90, 156, 0.4) !important; 
        color: white !important; 
        border: 1px solid rgba(255,255,255,0.3) !important; 
        width: auto !important; 
        min-width: 85px !important;
        text-transform: uppercase; 
        font-size: 0.52rem !important; 
        font-weight: 700 !important;
        padding: 2px 6px !important;
        line-height: 1.0 !important;
        height: 42px !important;
        white-space: pre-wrap !important;
        display: inline-block !important;
    }
    
    div.stButton > button[kind="primary"] { background-color: rgba(214, 0, 26, 0.8) !important; border: 1px solid #d6001a !important; }
    div.stButton > button[kind="secondary"] { background-color: rgba(235, 143, 52, 0.8) !important; border: 1px solid #eb8f34 !important; }

    .ba-header { background-color: #002366; padding: 20px; border-radius: 5px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #d6001a; color: white !important; }
    
    .reason-box { background-color: #ffffff; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; color: #002366 !important; }
    .reason-box h3, .reason-box p, .reason-box b { color: #002366 !important; }
    
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
    "SEN": {"icao": "EGMC", "lat": 51.571, "lon": 0.701, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer", "spec": True},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 180, "fleet": "Cityflyer", "spec": True},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "IBZ": {"icao": "LEIB", "lat": 38.873, "lon": 1.373, "rwy": 60, "fleet": "Cityflyer", "spec": False},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "AGP": {"icao": "LEMG", "lat": 36.675, "lon": -4.499, "rwy": 130, "fleet": "Cityflyer", "spec": False},
    "FAO": {"icao": "LPFR", "lat": 37.017, "lon": -7.965, "rwy": 280, "fleet": "Cityflyer", "spec": False},
    "MAD": {"icao": "LEMD", "lat": 40.494, "lon": -3.567, "rwy": 140, "fleet": "Cityflyer", "spec": False},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "Cityflyer", "spec": False},
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
    "ALG": {"icao": "DAAG", "lat": 36.691, "lon": 3.215, "rwy": 230, "fleet": "Euroflyer", "spec": False},
    "RTM": {"icao": "EHRD", "lat": 51.957, "lon": 4.440, "rwy": 240, "fleet": "Cityflyer", "spec": False},
}

# 5. SESSION STATE
if 'manual_stations' not in st.session_state: st.session_state.manual_stations = {}
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

# 6. SIDEBAR (STABILIZED)
with st.sidebar:
    st.title("🛠️ COMMAND SETTINGS")
    if st.button("🔄 MANUAL DATA REFRESH"):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.subheader("Add Ad-Hoc Station")
    with st.form("manual_add", clear_on_submit=True):
        new_iata = st.text_input("IATA").upper()
        new_icao = st.text_input("ICAO").upper()
        if st.form_submit_button("Add Station"):
            try:
                m = Metar(new_icao); m.update()
                st.session_state.manual_stations[new_iata] = {"icao": new_icao, "lat": m.data.station.latitude, "lon": m.data.station.longitude, "rwy": 0, "fleet": "Ad-Hoc", "spec": False}
                st.cache_data.clear()
                st.rerun()
            except: st.error("Invalid ICAO")
    
    if st.session_state.manual_stations:
        st.markdown("---")
        st.subheader("Manage Manual Stations")
        for iata in list(st.session_state.manual_stations.keys()):
            if st.button(f"Remove {iata}", key=f"del_{iata}"):
                del st.session_state.manual_stations[iata]
                st.cache_data.clear()
                st.rerun()

# 7. DATA FETCH & PREDICTIVE LOGIC
all_airports = {**base_airports, **st.session_state.manual_stations}

@st.cache_data(ttl=600)
def get_occ_intelligence(airport_dict):
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
                        for layer in line.clouds:
                            if layer.type in ['BKN', 'OVC'] and layer.base: c = min(c, layer.base * 100)
                    
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
                "cig": 9999, "w_dir": m.data.wind_direction.value or 0, "w_spd": m.data.wind_speed.value or 0,
                "raw_m": m.raw, "raw_t": t.raw, "status": "online", "f": f_issue
            }
            if m.data.clouds:
                for layer in m.data.clouds:
                    if layer.type in ['BKN', 'OVC'] and layer.base:
                        results[iata]["cig"] = min(results[iata]["cig"], layer.base * 100)
        except: results[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A", "f": None}
    return results

weather_intel = get_occ_intelligence(all_airports)

# 8. ALERT CLASSIFICATION & MAP COLORS
metar_alerts = {}; taf_alerts = {}; green_stations = []; map_markers = []

for iata, info in all_airports.items():
    data = weather_intel.get(iata, {"status": "offline"})
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    marker_color = "#008000"

    if data['status'] == "online":
        m_reason = None
        if data['vis'] < v_lim or data['cig'] < c_lim: m_reason = "MINIMA"; marker_color = "#d6001a"
        elif "TSRA" in data['raw_m']: m_reason = "TSRA"; marker_color = "#eb8f34"
        elif "FG" in data['raw_m']: m_reason = "FOG"; marker_color = "#eb8f34"

        if m_reason: metar_alerts[iata] = {"type": m_reason, "hex": "primary" if marker_color=="#d6001a" else "secondary"}
        else: green_stations.append(iata)

        if data['f']:
            f = data['f']
            taf_alerts[iata] = {"type": f['type'], "period": f['p'], "v": f['v'], "c": f['c'], "hex": "primary" if f['v'] < v_lim else "secondary"}
            if marker_color == "#008000": marker_color = "#eb8f34"

    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": marker_color, "metar": data['raw_m'], "taf": data['raw_t']})

# --- UI RENDER ---
st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)

# 9. MAP
m = folium.Map(location=[48.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")
for mkr in map_markers:
    popup_html = f"<div style='color:black; width:400px; font-family:monospace;'><b>{mkr['iata']} Status</b><hr><b>METAR:</b> {mkr['metar']}<br><b>TAF:</b> {mkr['taf']}</div>"
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=6, color=mkr['color'], fill=True, popup=folium.Popup(popup_html, max_width=500)).add_to(m)
st_folium(m, width=1400, height=400, key="map_main")

# 10. ALERT SECTIONS
st.markdown('<div class="section-title">🔴 ACTUAL WEATHER ALERTS (METAR)</div>', unsafe_allow_html=True)
if metar_alerts:
    cols = st.columns(10)
    for i, (iata, d) in enumerate(metar_alerts.items()):
        with cols[i % 10]:
            if st.button(f"{iata}\nNOW\n{d['type']}", key=f"m_{iata}", type=d['hex']): st.session_state.investigate_iata = iata

st.markdown('<div class="section-title">🟠 FORECAST ALERTS (TAF)</div>', unsafe_allow_html=True)
if taf_alerts:
    cols_t = st.columns(10)
    for i, (iata, d) in enumerate(taf_alerts.items()):
        with cols_t[i % 10]:
            if st.button(f"{iata}\n{d['period']}\n{d['type']}", key=f"t_{iata}", type=d['hex']): st.session_state.investigate_iata = iata

# 11. ANALYSIS BOX
if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d = weather_intel.get(iata)
    alt_iata, min_dist = "None", 9999
    for g in green_stations:
        dist = calculate_dist(all_airports[iata]['lat'], all_airports[iata]['lon'], all_airports[g]['lat'], all_airports[g]['lon'])
        if dist < min_dist: min_dist = dist; alt_iata = g

    st.markdown(f"""
    <div class="reason-box">
        <h3>{iata} Strategic Analysis</h3>
        <p><b>Weather Summary:</b> Visibility {d['vis']}m, Ceiling {d['cig']}ft. TAF Issue: {d['f']['type'] if d['f'] else 'Stable'}.</p>
        <p><b>Impact Statement:</b> Operational limits breached. Verify Cat 3 capability and fuel for alternates.</p>
        <p style="color:#d6001a !important; font-weight:bold;">✈️ Strategic Alternate: {alt_iata} ({min_dist} NM)</p>
        <hr><small><b>METAR:</b> {d['raw_m']}<br><b>TAF:</b> {d['raw_t']}</small>
    </div>""", unsafe_allow_html=True)
    if st.button("Close Analysis"): st.session_state.investigate_iata = "None"; st.rerun()

# 12. HANDOVER SUMMARY
st.markdown('<div class="section-title">📝 SHIFT HANDOVER SUMMARY</div>', unsafe_allow_html=True)
h_txt = f"SHIFT HANDOVER {datetime.now().strftime('%H:%M')}Z\n" + "="*35 + "\n"
for iata, d in taf_alerts.items():
    advice = "CAT3 Aircraft Advised" if d['type'] == "CAT3-ONLY" else "Monitor alternate availability"
    h_txt += f"{iata} {d['type']} {d['v']}m/{d['c']}ft ({d['period']}) - {advice}\n"
st.text_area("Handover Report Copy:", value=h_txt, height=150, label_visibility="collapsed")
