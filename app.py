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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="st-"], div, p, h1, h2, h3, h4, label { font-family: 'Inter', sans-serif !important; }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 300px !important; }
    [data-testid="stSidebar"] .stTextInput input { color: #002366 !important; background-color: white !important; font-weight: bold; }
    .section-title { color: #002366 !important; font-weight: 800; font-size: 1.1rem; margin-top: 25px; margin-bottom: 10px; border-bottom: 2px solid #d6001a; padding-bottom: 3px; text-transform: uppercase; }
    .stButton > button { color: white !important; border: 1px solid rgba(255,255,255,0.4) !important; text-transform: uppercase; font-size: 0.55rem !important; font-weight: 700 !important; padding: 4px 2px !important; line-height: 1.1 !important; height: 55px !important; white-space: pre-wrap !important; display: block !important; width: 100% !important; border-radius: 4px !important; }
    div.stButton > button[kind="primary"] { background-color: rgba(214, 0, 26, 0.9) !important; border: 1px solid #d6001a !important; }
    div.stButton > button[kind="secondary"] { background-color: rgba(235, 143, 52, 0.9) !important; border: 1px solid #eb8f34 !important; }
    .ba-header { background-color: #002366; padding: 20px; border-radius: 5px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #d6001a; color: white !important; }
    .reason-box { background-color: #ffffff; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-left: 10px solid #d6001a; color: #002366 !important; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
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

def calculate_xwind(wind_dir, wind_spd, rwy_hdg):
    if wind_dir is None or wind_spd is None or rwy_hdg is None: return 0
    angle = math.radians(wind_dir - rwy_hdg)
    return round(abs(wind_spd * math.sin(angle)))

# 4. DATABASE (46 STATIONS)
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
    "IBZ": {"icao": "LEIB", "lat": 38.873, "lon": 1.373, "rwy": 60, "fleet": "Cityflyer", "spec": False},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "AGP": {"icao": "LEMG", "lat": 36.675, "lon": -4.499, "rwy": 130, "fleet": "Cityflyer", "spec": False},
    "FAO": {"icao": "LPFR", "lat": 37.017, "lon": -7.965, "rwy": 280, "fleet": "Cityflyer", "spec": False},
    "SEN": {"icao": "EGMC", "lat": 51.571, "lon": 0.701, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "ALG": {"icao": "DAAG", "lat": 36.691, "lon": 3.215, "rwy": 230, "fleet": "Euroflyer", "spec": False},
}

# 5. DATA FETCH & PRIORITY LOGIC
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
                    v, c = (line.visibility.value if line.visibility else 9999), 9999
                    gust = line.wind_gust.value if line.wind_gust else 0
                    if line.clouds:
                        for layer in line.clouds:
                            if layer.type in ['BKN', 'OVC'] and layer.base: c = min(c, layer.base * 100)
                    
                    # PRIORITY ORDER ALERT DETECTION
                    reason = None
                    if info['fleet'] == "Cityflyer" and ("FZRA" in line.raw or "FZDZ" in line.raw): reason = "CLOSED-FZRA"
                    elif info['fleet'] == "Cityflyer" and 200 <= v <= 550: reason = "CAT3-ONLY"
                    elif "TSRA" in line.raw: reason = "TSRA"
                    elif "SN" in line.raw: reason = "SNOW"
                    elif v < v_lim: reason = "VIS"
                    elif c < c_lim: reason = "CLOUD"
                    elif gust >= 35: reason = "GUST"
                    
                    if reason:
                        f_issue = {"type": reason, "v": v, "c": c, "g": gust, "p": f"{line.start_time.dt.strftime('%H')}-{line.end_time.dt.strftime('%H')}Z"}
                        break

            results[iata] = {
                "vis": m.data.visibility.value if m.data.visibility else 9999,
                "cig": 9999, "w_dir": m.data.wind_direction.value or 0, "w_spd": m.data.wind_speed.value or 0,
                "w_gst": m.data.wind_gust.value or 0, "raw_m": m.raw, "raw_t": t.raw, "status": "online", "f": f_issue
            }
            if m.data.clouds:
                for layer in m.data.clouds:
                    if layer.type in ['BKN', 'OVC'] and layer.base: results[iata]["cig"] = min(results[iata]["cig"], layer.base * 100)
        except: results[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A", "f": None, "w_spd": 0, "w_gst": 0, "w_dir": 0}
    return results

all_stations = {**base_airports, **st.session_state.manual_stations}
weather_intel = get_occ_intel(all_stations)

# 6. SIDEBAR
with st.sidebar:
    st.title("🛠️ COMMAND SETTINGS")
    if st.button("🔄 MANUAL DATA REFRESH"): st.cache_data.clear(); st.rerun()
    map_theme = st.radio("MAP THEME", ["Dark Mode", "Light Mode"])
    st.markdown("---")
    with st.form("manual_add"):
        new_iata, new_icao = st.text_input("IATA").upper(), st.text_input("ICAO").upper()
        if st.form_submit_button("Add Station"):
            try:
                m = Metar(new_icao); m.update()
                st.session_state.manual_stations[new_iata] = {"icao": new_icao, "lat": m.data.station.latitude, "lon": m.data.station.longitude, "rwy": 0, "fleet": "Ad-Hoc", "spec": False}
                st.cache_data.clear(); st.rerun()
            except: st.error("Invalid ICAO")

metar_alerts = {}; taf_alerts = {}; green_stations = []; map_markers = []
for iata, info in all_stations.items():
    data = weather_intel.get(iata, {"status": "offline", "w_spd": 0, "w_gst": 0})
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    marker_color = "#008000"
    if data['status'] == "online":
        m_res, m_severity = None, "secondary"
        if info['fleet'] == "Cityflyer" and ("FZRA" in data['raw_m'] or "FZDZ" in data['raw_m']):
            m_res = "CLOSED-FZRA"; marker_color = "#d6001a"; m_severity = "primary"
        elif data['vis'] < v_lim or data['cig'] < c_lim: 
            m_res = "MINIMA"; marker_color = "#d6001a"; m_severity = "primary"
        elif "TSRA" in data['raw_m']: m_res = "TSRA"; marker_color = "#eb8f34"
        elif data['w_gst'] > 35: m_res = "GUST"; marker_color = "#eb8f34"
        
        if m_res: metar_alerts[iata] = {"type": m_res, "hex": m_severity}
        else: green_stations.append(iata)
        
        if data['f']:
            f = data['f']
            f_severity = "primary" if f['type'] in ["CLOSED-FZRA", "MINIMA"] or f['v'] < v_lim else "secondary"
            taf_alerts[iata] = {"type": f['type'], "period": f['p'], "v": f['v'], "c": f['c'], "hex": f_severity}
            if marker_color == "#008000": marker_color = "#eb8f34"

    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": marker_color, "metar": data['raw_m'], "taf": data['raw_t']})

st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)
tile = "CartoDB dark_matter" if map_theme == "Dark Mode" else "CartoDB positron"
m = folium.Map(location=[48.0, 5.0], zoom_start=5, tiles=tile)
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=6, color=mkr['color'], fill=True, popup=folium.Popup(f"<div style='color:black; width:350px; font-family:monospace;'><b>{mkr['iata']}</b><hr>METAR: {mkr['metar']}</div>", max_width=400)).add_to(m)
st_folium(m, width=1400, height=400, key="map_v22")

# 7. ALERT ROWS
st.markdown('<div class="section-title">🔴 ACTUAL WEATHER ALERTS (METAR)</div>', unsafe_allow_html=True)
if metar_alerts:
    cols = st.columns(min(len(metar_alerts), 12))
    for i, (iata, d) in enumerate(metar_alerts.items()):
        with cols[i % 12]:
            if st.button(f"{iata}\nNOW\n{d['type']}", key=f"m_{iata}", type=d['hex']): st.session_state.investigate_iata = iata

st.markdown('<div class="section-title">🟠 FORECAST ALERTS (TAF)</div>', unsafe_allow_html=True)
if taf_alerts:
    cols_t = st.columns(min(len(taf_alerts), 12))
    for i, (iata, d) in enumerate(taf_alerts.items()):
        with cols_t[i % 12]:
            if st.button(f"{iata}\n{d['period']}\n{d['type']}", key=f"t_{iata}", type=d['hex']): st.session_state.investigate_iata = iata

# 8. STRATEGIC ANALYSIS
if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d = weather_intel.get(iata, {"w_spd": 0, "w_gst": 0, "w_dir": 0, "raw_m": "N/A", "raw_t": "N/A"})
    info = all_stations.get(iata, {"rwy": 0, "lat": 0, "lon": 0})
    
    main_issue = metar_alerts.get(iata, {}).get('type') or taf_alerts.get(iata, {}).get('type', "N/A")
    period = "CURRENT" if iata in metar_alerts else taf_alerts.get(iata, {}).get('period', "N/A")
    
    impact_stmt = "Operational limits breached. Verify aircraft icing/minima status."
    if "CLOSED" in main_issue: impact_stmt = "STATION CLOSED for Embraer fleet due to FZRA/FZDZ limitations."
    if "CAT3" in main_issue: impact_stmt = "LVP Operations. CAT3 Capable aircraft/crew only."

    # WIND CALC
    xw_msg = ""
    w_spd, w_gst, w_dir = d.get('w_spd', 0), d.get('w_gst', 0), d.get('w_dir', 0)
    if w_spd > 20 or w_gst > 0:
        xw_comp = calculate_xwind(w_dir, w_spd, info.get('rwy', 0))
        xw_msg = f" | X-WIND: {xw_comp}kt"

    alt_iata, min_dist = "None", 9999
    for g in green_stations:
        if g != iata:
            dist = calculate_dist(info['lat'], info['lon'], all_stations[g]['lat'], all_stations[g]['lon'])
            if dist < min_dist: min_dist = dist; alt_iata = g

    st.markdown(f"""
    <div class="reason-box">
        <h3>{iata} Strategy Brief</h3>
        <p><b>Weather Summary:</b> Issue: {main_issue}{xw_msg} | Period: {period}</p>
        <p><b>Impact Statement:</b> {impact_stmt}</p>
        <p style="color:#d6001a !important; font-weight:bold; font-size:1.1rem;">✈️ Nearest Safe Alternate: {alt_iata} ({min_dist} NM)</p>
        <hr><small><b>METAR:</b> {d['raw_m']}<br><b>TAF:</b> {d['raw_t']}</small>
    </div>""", unsafe_allow_html=True)
    if st.button("Close Analysis"): st.session_state.investigate_iata = "None"; st.rerun()

# 9. HANDOVER
st.markdown('<div class="section-title">📝 SHIFT HANDOVER SUMMARY</div>', unsafe_allow_html=True)
h_txt = f"SHIFT HANDOVER {datetime.now().strftime('%H:%M')}Z\n" + "="*35 + "\n"
for iata, d in taf_alerts.items():
    advice = "CAT3 Aircraft Advised" if d['type'] == "CAT3-ONLY" else "Monitor alternate availability"
    if "CLOSED" in d['type']: advice = "STATION CLOSED - EMBRAER LIMITS"
    h_txt += f"{iata} {d['type']} ({d['period']}) - {advice}\n"
st.text_area("Handover Report Copy:", value=h_txt, height=150, label_visibility="collapsed")
