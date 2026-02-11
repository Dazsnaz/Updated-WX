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
    html, body, [class*="st-"], div, p, h1, h2, h3, h4, label { color: white !important; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #002366 !important; }
    
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
        height: 40px !important;
        white-space: pre-wrap !important;
        display: inline-block !important;
    }
    
    .alert-container { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 20px; }
    
    .marquee { width: 100%; background-color: #d6001a; color: white; white-space: nowrap; overflow: hidden; padding: 12px; font-weight: bold; border-radius: 5px; margin-bottom: 15px; border: 2px solid white; }
    .marquee span { display: inline-block; padding-left: 100%; animation: marquee 25s linear infinite; }
    @keyframes marquee { 0% { transform: translate(0, 0); } 100% { transform: translate(-100%, 0); } }
    
    .ba-header { background-color: #002366; padding: 20px; border-radius: 5px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #d6001a; }
    
    /* ALERT COLOR OVERRIDES */
    div.stButton > button[kind="primary"] { background-color: rgba(214, 0, 26, 0.8) !important; border: 1px solid #d6001a !important; }
    div.stButton > button[kind="secondary"] { background-color: rgba(235, 143, 52, 0.8) !important; border: 1px solid #eb8f34 !important; }
    
    .reason-box { background-color: #ffffff; border: 1px solid #ddd; padding: 25px; border-radius: 5px; margin-top: 20px; border-top: 10px solid #d6001a; color: #002366 !important; }
    .reason-box h3, .reason-box p, .reason-box b, .reason-box small, .reason-box span, .reason-box i { color: #002366 !important; }
    
    [data-testid="stTextArea"] textarea { color: #002366 !important; background-color: #ffffff !important; font-weight: bold; border: 1px solid #999 !important; }
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
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "spec": True},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "spec": False},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "spec": False},
    "JER": {"icao": "EGJJ", "lat": 49.208, "lon": -2.195, "rwy": 260, "spec": False},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "spec": True},
    "FNC": {"icao": "LPMA", "lat": 32.694, "lon": -16.774, "rwy": 50, "spec": True},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "spec": False},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "spec": False},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "spec": False},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "spec": False},
    "SEN": {"icao": "EGMC", "lat": 51.571, "lon": 0.701, "rwy": 230, "spec": False},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "spec": True},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 180, "spec": True},
    "ALG": {"icao": "DAAG", "lat": 36.691, "lon": 3.215, "rwy": 230, "spec": False},
    "GRZ": {"icao": "LOWG", "lat": 46.991, "lon": 15.439, "rwy": 350, "spec": False},
    "VRN": {"icao": "LIPX", "lat": 45.396, "lon": 10.888, "rwy": 40, "spec": False},
    "RBA": {"icao": "GMME", "lat": 34.051, "lon": -6.751, "rwy": 30, "spec": False},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "spec": False},
    "MAD": {"icao": "LEMD", "lat": 40.494, "lon": -3.567, "rwy": 140, "spec": False},
    "FAO": {"icao": "LPFR", "lat": 37.017, "lon": -7.965, "rwy": 280, "spec": False},
    "IBZ": {"icao": "LEIB", "lat": 38.873, "lon": 1.373, "rwy": 60, "spec": False},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "spec": False},
    "AGP": {"icao": "LEMG", "lat": 36.675, "lon": -4.499, "rwy": 130, "spec": False},
    "RTM": {"icao": "EHRD", "lat": 51.957, "lon": 4.440, "rwy": 240, "spec": False},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "spec": False},
    "OPO": {"icao": "LPPR", "lat": 41.242, "lon": -8.678, "rwy": 350, "spec": False},
    "LYS": {"icao": "LFLL", "lat": 45.726, "lon": 5.090, "rwy": 350, "spec": False},
    "SZG": {"icao": "LOWS", "lat": 47.794, "lon": 13.004, "rwy": 330, "spec": False},
    "BOD": {"icao": "LFBD", "lat": 44.828, "lon": -0.716, "rwy": 230, "spec": False},
    "GNB": {"icao": "LFLS", "lat": 45.363, "lon": 5.330, "rwy": 90, "spec": False},
    "TRN": {"icao": "LIMF", "lat": 45.202, "lon": 7.649, "rwy": 360, "spec": False},
    "ALC": {"icao": "LEAL", "lat": 38.282, "lon": -0.558, "rwy": 100, "spec": False},
    "SVQ": {"icao": "LEZL", "lat": 37.418, "lon": -5.893, "rwy": 270, "spec": False},
    "RAK": {"icao": "GMMX", "lat": 31.606, "lon": -8.036, "rwy": 100, "spec": False},
    "AGA": {"icao": "GMAD", "lat": 30.325, "lon": -9.413, "rwy": 90, "spec": False},
    "SSH": {"icao": "HESH", "lat": 27.977, "lon": 34.394, "rwy": 40, "spec": False},
    "PFO": {"icao": "LCPH", "lat": 34.718, "lon": 32.486, "rwy": 290, "spec": False},
    "LCA": {"icao": "LCLK", "lat": 34.875, "lon": 33.625, "rwy": 220, "spec": False},
    "FUE": {"icao": "GCLP", "lat": 28.452, "lon": -13.864, "rwy": 10, "spec": False},
    "TFS": {"icao": "GCTS", "lat": 28.044, "lon": -16.572, "rwy": 70, "spec": False},
    "ACE": {"icao": "GCRR", "lat": 28.945, "lon": -13.605, "rwy": 30, "spec": False},
    "LPA": {"icao": "GCLP", "lat": 27.931, "lon": -15.386, "rwy": 30, "spec": False},
    "IVL": {"icao": "EFIV", "lat": 68.607, "lon": 27.405, "rwy": 40, "spec": False},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "spec": False},
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "spec": False},
    "GVA": {"icao": "LSGG", "lat": 46.237, "lon": 6.109, "rwy": 220, "spec": False},
    "BER": {"icao": "EDDB", "lat": 52.362, "lon": 13.501, "rwy": 250, "spec": False},
    "FRA": {"icao": "EDDF", "lat": 50.033, "lon": 8.571, "rwy": 250, "spec": False},
    "LIN": {"icao": "LIML", "lat": 45.445, "lon": 9.277, "rwy": 360, "spec": False},
}

# 5. SESSION STATE
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

# 6. DATA FETCH & PREDICTIVE ANALYSIS
@st.cache_data(ttl=600)
def get_occ_intelligence(airport_dict):
    results = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            
            f_issue = None
            if t.data:
                for line in t.data.forecast:
                    v = line.visibility.value if line.visibility else 9999
                    c = 9999
                    if line.clouds:
                        for layer in line.clouds:
                            if layer.type in ['BKN', 'OVC'] and layer.base: c = min(c, layer.base * 100)
                    
                    reason = None
                    if "TSRA" in line.raw: reason = "TSRA"
                    elif "FZRA" in line.raw: reason = "FZRA"
                    elif "SN" in line.raw: reason = "SNOW"
                    elif v < 1500 or "FG" in line.raw: reason = "FOG"
                    elif v < 3000: reason = "VIS"
                    elif c < 1000: reason = "CLOUD"
                    
                    if reason:
                        f_issue = {"type": reason, "v": v, "c": c, "p": f"{line.start_time.dt.strftime('%H')}-{line.end_time.dt.strftime('%H')}Z"}
                        break

            results[iata] = {
                "vis": m.data.visibility.value if m.data.visibility else 9999,
                "cig": 9999, "w_dir": m.data.wind_direction.value or 0, "w_spd": m.data.wind_speed.value or 0,
                "temp": m.data.temperature.value or 0, "raw_m": m.raw, "raw_t": t.raw, "status": "online", "f": f_issue
            }
            if m.data.clouds:
                for layer in m.data.clouds:
                    if layer.type in ['BKN', 'OVC'] and layer.base: results[iata]["cig"] = min(results[iata]["cig"], layer.base * 100)
        except: results[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A", "f": None}
    return results

weather_intel = get_occ_intelligence(base_airports)

# 7. ALERT CLASSIFICATION
metar_alerts = {}; taf_alerts = {}; red_list = []; green_stations = []; map_markers = []

for iata, info in base_airports.items():
    data = weather_intel.get(iata, {"status": "offline"})
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    xw = round(abs(data.get('w_spd', 0) * math.sin(math.radians(data.get('w_dir', 0) - info['rwy']))), 1) if info['rwy'] else 0

    if data['status'] == "online":
        m_reason = None
        if data['vis'] < v_lim or data['cig'] < c_lim: m_reason = "MINIMA"; red_list.append(iata)
        elif xw > 25: m_reason = "XWIND"
        elif "TSRA" in data['raw_m']: m_reason = "TSRA"
        elif "FG" in data['raw_m']: m_reason = "FOG"

        if m_reason: metar_alerts[iata] = {"type": m_reason, "hex": "primary" if m_reason=="MINIMA" else "secondary"}
        else: green_stations.append(iata)

        if data['f']:
            f = data['f']
            taf_alerts[iata] = {"type": f['type'], "period": f['p'], "v": f['v'], "c": f['c'], "hex": "primary" if f['v'] < v_lim else "secondary"}

    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": "#d6001a" if iata in metar_alerts and metar_alerts[iata]['type']=="MINIMA" else "#008000"})

# --- UI RENDER ---
if red_list: st.markdown(f'<div class="marquee"><span>🚨 CRITICAL: {", ".join(red_list)} AT MINIMA</span></div>', unsafe_allow_html=True)
st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)

# 8. MAP
m = folium.Map(location=[45.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")
for mkr in map_markers:
    data = weather_intel.get(mkr['iata'])
    popup_html = f"<div style='color:black; width:400px; font-family:monospace;'><b>{mkr['iata']} Status</b><hr><b>METAR:</b> {data['raw_m']}<br><b>TAF:</b> {data['raw_t']}</div>"
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=6, color=mkr['color'], fill=True, popup=folium.Popup(popup_html, max_width=500)).add_to(m)
st_folium(m, width=1400, height=400, key="map_v9")

# 9. SEPARATED ALERT ROWS
st.markdown("### 🔴 ACTUAL WEATHER (METAR)")
st.markdown('<div class="alert-container">', unsafe_allow_html=True)
c1 = st.columns(10)
for i, (iata, d) in enumerate(metar_alerts.items()):
    with c1[i % 10]:
        if st.button(f"{iata}\nNOW\n{d['type']}", key=f"m_{iata}", type=d['hex']): st.session_state.investigate_iata = iata
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("### 🟠 FORECAST ALERTS (TAF)")
st.markdown('<div class="alert-container">', unsafe_allow_html=True)
c2 = st.columns(10)
for i, (iata, d) in enumerate(taf_alerts.items()):
    with c2[i % 10]:
        if st.button(f"{iata}\n{d['period']}\n{d['type']}", key=f"t_{iata}", type=d['hex']): st.session_state.investigate_iata = iata
st.markdown('</div>', unsafe_allow_html=True)

# 10. STRATEGIC ANALYSIS
if st.session_state.investigate_iata != "None":
    iata = st.session_state.investigate_iata
    d = weather_intel.get(iata)
    alt_iata, min_dist = "None", 9999
    for g in green_stations:
        dist = calculate_dist(base_airports[iata]['lat'], base_airports[iata]['lon'], base_airports[g]['lat'], base_airports[g]['lon'])
        if dist < min_dist: min_dist = dist; alt_iata = g

    st.markdown(f"""
    <div class="reason-box">
        <h3>{iata} Strategy Brief</h3>
        <p><b>Weather Summary:</b> METAR reports {d['raw_m']}. Forecast Issue: {d['f']['type'] if d['f'] else 'Stable'}.</p>
        <p><b>Impact Statement:</b> High risk of holding/diversions. Verify Cat 3 status for scheduled arrivals.</p>
        <p style="color:#d6001a !important; font-weight:bold;">✈️ Strategic Alternate: {alt_iata} ({min_dist} NM)</p>
        <hr><small><b>METAR:</b> {d['raw_m']}<br><b>TAF:</b> {d['raw_t']}</small>
    </div>""", unsafe_allow_html=True)
    if st.button("Close Analysis"): st.session_state.investigate_iata = "None"; st.rerun()

# 11. HANDOVER
st.markdown("---")
st.markdown("### 📝 Shift Handover Summary")
h_txt = f"SHIFT HANDOVER {datetime.now().strftime('%H:%M')}Z\n" + "="*35 + "\n"
for iata, d in metar_alerts.items():
    h_txt += f"[ACTUAL] {iata}: Active {d['type']} procedures.\n"
for iata, d in taf_alerts.items():
    h_txt += f"[FCAST] {iata}: {d['type']} {d['v']}m/{d['c']}ft ({d['period']}) - CAT3 Aircraft Advised\n"
st.text_area("Handover Report Copy:", value=h_txt, height=150)
