import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. REFINED HUD STYLING
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    
    html, body, [class*="st-"], div, p, h1, h2, h3, h4, label { 
        color: white !important; 
        font-family: 'Inter', sans-serif !important; 
    }
    
    [data-testid="stSidebar"] { background-color: #002366 !important; }
    
    /* REFINED ALERT BUTTONS */
    .stButton > button {
        background-color: #005a9c !important; color: white !important;
        border: 1px solid rgba(255,255,255,0.3) !important; 
        width: 100%; text-transform: uppercase;
        font-size: 0.75rem !important;
        padding: 4px 8px !important;
        border-radius: 4px !important;
        height: auto !important;
    }

    .marquee {
        width: 100%; background-color: #d6001a; color: white; white-space: nowrap;
        overflow: hidden; padding: 10px; font-weight: bold; border-radius: 4px;
        margin-bottom: 15px; border: 1px solid white; font-size: 0.9rem;
    }
    .marquee span { display: inline-block; padding-left: 100%; animation: marquee 25s linear infinite; }
    @keyframes marquee { 0% { transform: translate(0, 0); } 100% { transform: translate(-100%, 0); } }

    .ba-header { background-color: #002366; padding: 15px; border-radius: 4px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #d6001a; }
    
    /* ANALYSIS BOX */
    .reason-box { background-color: #ffffff; border-radius: 4px; padding: 20px; margin-top: 15px; border-left: 8px solid #d6001a; color: #002366 !important; }
    .reason-box h3, .reason-box p, .reason-box b, .reason-box small, .reason-box span { color: #002366 !important; }
    
    /* HANDOVER BOX */
    .handover-area { background-color: #f0f2f6; color: #333 !important; padding: 15px; border-radius: 4px; font-family: monospace !important; border: 1px solid #ccc; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_dist(lat1, lon1, lat2, lon2):
    R = 3440.065 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)

# 4. MASTER DATABASE (FULL FLEET)
base_airports = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer", "spec": True},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "JER": {"icao": "EGJJ", "lat": 49.208, "lon": -2.195, "rwy": 260, "fleet": "Euroflyer", "spec": False},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer", "spec": True},
    "FNC": {"icao": "LPMA", "lat": 32.694, "lon": -16.774, "rwy": 50, "fleet": "Euroflyer", "spec": True},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer", "spec": False},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer", "spec": False},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "Cityflyer", "spec": False},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer", "spec": True},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 180, "fleet": "Cityflyer", "spec": True},
    "ALG": {"icao": "DAAG", "lat": 36.691, "lon": 3.215, "rwy": 230, "fleet": "Euroflyer", "spec": False},
    "GRZ": {"icao": "LOWG", "lat": 46.991, "lon": 15.439, "rwy": 350, "fleet": "Euroflyer", "spec": False},
    "VRN": {"icao": "LIPX", "lat": 45.396, "lon": 10.888, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "RBA": {"icao": "GMME", "lat": 34.051, "lon": -6.751, "rwy": 30, "fleet": "Euroflyer", "spec": False},
}

# 5. SESSION STATE
if 'manual_stations' not in st.session_state: st.session_state.manual_stations = {}
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

# 6. DATA FETCH
all_airports = {**base_airports, **st.session_state.manual_stations}

@st.cache_data(ttl=900)
def get_weather_intelligence(airport_dict):
    results = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update()
            t = Taf(info['icao']); t.update()
            f_vis, f_cig = 9999, 9999
            if t.data:
                for line in t.data.forecast:
                    if line.visibility: f_vis = min(f_vis, line.visibility.value)
                    if line.clouds:
                        for layer in line.clouds:
                            if layer.type in ['BKN', 'OVC'] and layer.base: f_cig = min(f_cig, layer.base * 100)
            results[iata] = {
                "vis": m.data.visibility.value if m.data.visibility else 9999,
                "ceiling": 9999, "w_dir": m.data.wind_direction.value or 0, "w_spd": m.data.wind_speed.value or 0,
                "f_vis": f_vis, "f_cig": f_cig, "raw_m": m.raw, "raw_t": t.raw, "status": "online"
            }
            if m.data.clouds:
                for layer in m.data.clouds:
                    if layer.type in ['BKN', 'OVC'] and layer.base: results[iata]["ceiling"] = min(results[iata]["ceiling"], layer.base * 100)
        except: results[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A"}
    return results

weather_data = get_weather_intelligence(all_airports)

# 7. TACTICAL ALERT LOGIC
active_alerts = {}; red_list = []; green_stations = []; map_markers = []
for iata, data in weather_data.items():
    info = all_airports[iata]
    v_limit, c_limit = (1500, 500) if info['spec'] else (800, 200)
    color = "#008000"; alert_type = None; reason = ""; impact = ""

    if data['status'] == "offline": color = "#808080"
    elif data['vis'] < v_limit or data['ceiling'] < c_limit:
        color = "#d6001a"; alert_type = "MINIMA"; reason = "Currently Below Limits"; impact = "Station Closed / Immediate Diversions."; red_list.append(iata)
    elif data['f_vis'] < v_limit or data['f_cig'] < c_limit:
        color = "#d6001a"; alert_type = "FCAST-MIN"; reason = "Forecast Below Minima"; impact = "Strategic fuel/alternate planning required."
    elif "TSRA" in data['raw_t']:
        color = "#eb8f34"; alert_type = "TSRA"; reason = "Convective Activity Forecast"; impact = "ATC flow restrictions and holding."
    elif data['f_vis'] < (v_limit * 2):
        color = "#eb8f34"; alert_type = "FCAST-VIS"; reason = "Forecast Marginal Visibility"; impact = "LVP preparation advised."

    if alert_type: active_alerts[iata] = {"type": alert_type, "reason": reason, "impact": impact, "metar": data['raw_m'], "taf": data['raw_t'], "color": "primary" if color == "#d6001a" else "secondary"}
    elif data['status'] == "online": green_stations.append(iata)
    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "metar": data['raw_m'], "taf": data['raw_t']})

# 8. UI RENDER
if red_list: st.markdown(f'<div class="marquee"><span>🚨 CRITICAL: {", ".join(red_list)} AT MINIMA</span></div>', unsafe_allow_html=True)

st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)

# MAP
m = folium.Map(location=[45.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")
for mkr in map_markers:
    popup_html = f"<div style='color:black; width:450px; font-family:monospace;'><b>{mkr['iata']} Status</b><hr><b>METAR:</b> {mkr['metar']}<br><b>TAF:</b> {mkr['taf']}</div>"
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=7, color=mkr['color'], fill=True, popup=folium.Popup(popup_html, max_width=500)).add_to(m)
st_folium(m, width=1400, height=450, key=f"map_v{len(map_markers)}")

# 9. REFINED ALERT BUTTONS
st.markdown("### ⚠️ Tactical Alerts")
if active_alerts:
    cols = st.columns(10) # Smaller, more compact columns
    for i, (iata, d) in enumerate(active_alerts.items()):
        with cols[i % 10]:
            if st.button(f"{iata}\n{d['type']}", key=f"btn_{iata}", type=d['color']):
                st.session_state.investigate_iata = iata

if st.session_state.investigate_iata in active_alerts:
    d = active_alerts[st.session_state.investigate_iata]
    cur = all_airports[st.session_state.investigate_iata]
    alt_iata = "None"; min_dist = 9999
    for g in green_stations:
        dist = calculate_dist(cur['lat'], cur['lon'], all_airports[g]['lat'], all_airports[g]['lon'])
        if dist < min_dist: min_dist = dist; alt_iata = g

    st.markdown(f"""
    <div class="reason-box">
        <h3>{st.session_state.investigate_iata} Analysis: {d['type']}</h3>
        <p><b>Summary:</b> {d['reason']} | <b>Impact:</b> <i>{d['impact']}</i></p>
        <p style="color:#d6001a !important;"><b>✈️ Strategic Alternate:</b> {alt_iata} ({min_dist} NM)</p>
        <hr>
        <div style="display:flex; gap:20px;">
            <div><b>Current METAR:</b><br><small>{d['metar']}</small></div>
            <div><b>Forecast TAF:</b><br><small>{d['taf']}</small></div>
        </div>
    </div>""", unsafe_allow_html=True)
    if st.button("Close Analysis"): st.session_state.investigate_iata = "None"; st.rerun()

# 10. HANDOVER SUMMARY TOOL
st.markdown("---")
st.markdown("### 📝 Shift Handover Summary")
handover_text = f"SHIFT HANDOVER SUMMARY - {datetime.now().strftime('%d %b %H:%M')} UTC\n"
handover_text += "========================================\n"
if active_alerts:
    for iata, d in active_alerts.items():
        handover_text += f"[{iata}] {d['type']}: {d['impact']}\n"
else:
    handover_text += "No significant operational weather alerts."

st.text_area("Copy for Handover Report:", value=handover_text, height=150)
