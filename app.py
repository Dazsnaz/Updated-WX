import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. HIGH-DENSITY HUD STYLING
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@200;400;600&display=swap');
    
    html, body, [class*="st-"], div, p, h1, h2, h3, h4, label { 
        font-family: 'Inter', sans-serif !important; 
    }
    
    /* FIX: BLACK TEXT FOR ANALYSIS & HANDOVER */
    .reason-box, .handover-container, [data-testid="stTextArea"] textarea {
        color: #002366 !important;
    }

    [data-testid="stSidebar"] { background-color: #001a4d !important; }
    
    /* SLICKER, THINNER ALERT BUTTONS */
    .stButton > button {
        border: 1px solid rgba(255,255,255,0.2) !important;
        color: white !important;
        width: 100%;
        text-transform: uppercase;
        font-size: 0.55rem !important; /* Smaller Font */
        font-weight: 400 !important;
        padding: 1px 2px !important;
        border-radius: 2px !important;
        height: 32px !important;
        line-height: 1.1 !important;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* GRID ALIGNMENT FIX */
    div[data-testid="stHorizontalBlock"] {
        gap: 0.5rem !important;
        align-items: start !important;
    }

    .marquee {
        width: 100%; background-color: rgba(214, 0, 26, 0.9); color: white;
        overflow: hidden; padding: 8px; font-weight: 400; border-radius: 2px;
        margin-bottom: 15px; font-size: 0.8rem;
    }

    .ba-header { background-color: #002366; padding: 12px; border-radius: 2px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #d6001a; }
    
    .reason-box { background-color: #ffffff; border-radius: 2px; padding: 15px; margin-top: 10px; border-left: 5px solid #d6001a; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    
    .handover-container { background-color: #f4f4f4; padding: 15px; border-radius: 2px; border: 1px solid #ccc; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_dist(lat1, lon1, lat2, lon2):
    R = 3440.065 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)

# 4. MASTER DATABASE (ALL STATIONS)
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
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "OPO": {"icao": "LPPR", "lat": 41.242, "lon": -8.678, "rwy": 350, "fleet": "Euroflyer", "spec": False}
}

# 5. DATA FETCH
if 'manual_stations' not in st.session_state: st.session_state.manual_stations = {}
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"

all_airports = {**base_airports, **st.session_state.manual_stations}

@st.cache_data(ttl=600)
def get_weather_intel(airport_dict):
    results = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update()
            t = Taf(info['icao']); t.update()
            
            # Forecast Analysis
            forecast_issues = []
            if t.data:
                for line in t.data.forecast:
                    v = line.visibility.value if line.visibility else 9999
                    c = 9999
                    if line.clouds:
                        for layer in line.clouds:
                            if layer.type in ['BKN', 'OVC'] and layer.base: c = min(c, layer.base * 100)
                    
                    if v < 1500 or c < 500:
                        start = line.start_time.dt.strftime("%H%M") if line.start_time else "???"
                        end = line.end_time.dt.strftime("%H%M") if line.end_time else "???"
                        forecast_issues.append({"vis": v, "cig": c, "period": f"{start}Z-{end}Z"})

            results[iata] = {
                "vis": m.data.visibility.value if m.data.visibility else 9999,
                "ceiling": 9999, "raw_m": m.raw, "raw_t": t.raw, "status": "online",
                "f_issues": forecast_issues
            }
            if m.data.clouds:
                for layer in m.data.clouds:
                    if layer.type in ['BKN', 'OVC'] and layer.base:
                        results[iata]["ceiling"] = min(results[iata]["ceiling"], layer.base * 100)
        except: results[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A", "f_issues": []}
    return results

weather_data = get_weather_intel(all_airports)

# 6. ALERT CLASSIFICATION
metar_alerts = {}; taf_alerts = {}; red_list = []; green_stations = []; map_markers = []

for iata, data in weather_data.items():
    info = all_airports[iata]
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    
    # METAR ALERTS (Actual)
    if data['status'] == "online":
        if data['vis'] < v_lim or data['ceiling'] < c_lim:
            metar_alerts[iata] = {"type": "MINIMA", "vis": data['vis'], "cig": data['ceiling'], "hex": "#d6001a"}
            red_list.append(iata)
        elif "TSRA" in data['raw_m']: metar_alerts[iata] = {"type": "TSRA", "hex": "#eb8f34"}
        elif "FG" in data['raw_m']: metar_alerts[iata] = {"type": "FOG", "hex": "#eb8f34"}
        elif data['vis'] < (v_lim*2): metar_alerts[iata] = {"type": "VIS", "hex": "#eb8f34"}
        else: green_stations.append(iata)

        # TAF ALERTS (Forecast)
        if data['f_issues']:
            worst = data['f_issues'][0]
            taf_alerts[iata] = {"type": "FCAST", "vis": worst['vis'], "cig": worst['cig'], "period": worst['period'], "hex": "#eb8f34" if worst['vis'] > v_lim else "#d6001a"}
    
    color = "#008000"
    if iata in metar_alerts: color = metar_alerts[iata]['hex']
    elif iata in taf_alerts: color = taf_alerts[iata]['hex']
    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "metar": data['raw_m'], "taf": data['raw_t']})

# --- UI RENDER ---
if red_list: st.markdown(f'<div class="marquee"><span>🚨 ACTUALS BELOW MINIMA: {", ".join(red_list)}</span></div>', unsafe_allow_html=True)
st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)

# MAP
m = folium.Map(location=[45.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=6, color=mkr['color'], fill=True).add_to(m)
st_folium(m, width=1400, height=400, key=f"map_v{len(map_markers)}")

# 7. SEPARATED ALERT SECTIONS
st.markdown("### 🔴 ACTUAL WEATHER ALERTS (METAR)")
if metar_alerts:
    cols = st.columns(12)
    for i, (iata, d) in enumerate(metar_alerts.items()):
        with cols[i % 12]:
            st.markdown(f'<style>div[data-testid="stHorizontalBlock"] div:nth-child({(i%12)+1}) button {{ background-color: {d["hex"]}aa !important; border: 1px solid {d["hex"]} !important; }}</style>', unsafe_allow_html=True)
            if st.button(f"{iata}\n{d['type']}", key=f"m_{iata}"): st.session_state.investigate_iata = iata

st.markdown("### 🟠 FORECAST ALERTS (TAF)")
if taf_alerts:
    cols_t = st.columns(12)
    for i, (iata, d) in enumerate(taf_alerts.items()):
        with cols_t[i % 12]:
            st.markdown(f'<style>div[data-testid="stHorizontalBlock"] div:nth-child({(i%12)+1}) button {{ background-color: {d["hex"]}aa !important; border: 1px solid {d["hex"]} !important; }}</style>', unsafe_allow_html=True)
            if st.button(f"{iata}\n{d['period']}", key=f"t_{iata}"): st.session_state.investigate_iata = iata

# ANALYSIS BOX
if st.session_state.investigate_iata in all_airports:
    d = weather_data[st.session_state.investigate_iata]
    st.markdown(f"""<div class="reason-box">
        <h3>{st.session_state.investigate_iata} Detailed Analysis</h3>
        <p><b>METAR:</b> {d['raw_m']}</p>
        <p><b>TAF:</b> {d['raw_t']}</p>
    </div>""", unsafe_allow_html=True)

# 8. HANDOVER SUMMARY
st.markdown("---")
st.markdown("### 📝 Strategic Handover")
handover_txt = f"SHIFT HANDOVER - {datetime.now().strftime('%H:%M')}Z\n"
for iata, d in metar_alerts.items():
    handover_txt += f"[ACTUAL] {iata}: {d['type']} issue observed.\n"
for iata, d in taf_alerts.items():
    handover_txt += f"[FCAST] {iata}: Low Vis/Cig {d['vis']}m/{d['cig']}ft ({d['period']}) - CAT3 Aircraft Advised\n"

st.markdown('<div class="handover-container">', unsafe_allow_html=True)
st.text_area("Copy for Report:", value=handover_txt, height=180, label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)
