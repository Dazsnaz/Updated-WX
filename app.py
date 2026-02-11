import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. ULTRA-HIGH-DENSITY STYLING
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@200;400;700&display=swap');
    
    html, body, [class*="st-"], div, p, h1, h2, h3, h4, label { 
        font-family: 'Inter', sans-serif !important; 
    }
    
    /* SIDEBAR & HEADER */
    [data-testid="stSidebar"] { background-color: #001a4d !important; }
    .ba-header { background-color: #002366; padding: 12px; border-radius: 2px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #d6001a; }

    /* MICRO-FONT ALERT BUTTONS */
    .stButton > button {
        border: 1px solid rgba(255,255,255,0.2) !important;
        color: white !important;
        width: 100%;
        text-transform: uppercase;
        font-size: 0.5rem !important; /* Micro Font */
        font-weight: 700 !important;
        padding: 1px 1px !important;
        border-radius: 2px !important;
        height: 38px !important; /* Slightly taller for 3 lines */
        line-height: 1.0 !important;
        white-space: pre-wrap !important;
    }

    /* ANALYSIS & HANDOVER READABILITY */
    .reason-box, .handover-container {
        background-color: #ffffff; padding: 15px; border-radius: 2px; 
        border-left: 5px solid #d6001a; color: #002366 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-top: 10px;
    }
    .reason-box h3, .reason-box p, .reason-box b, .reason-box span, .reason-box i { color: #002366 !important; }
    
    [data-testid="stTextArea"] textarea { color: #002366 !important; font-size: 0.8rem !important; background-color: #f4f4f4 !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_dist(lat1, lon1, lat2, lon2):
    R = 3440.065 # NM
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)

# 4. MASTER DATABASE (FULL 42+ STATIONS)
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
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer", "spec": True},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 180, "fleet": "Cityflyer", "spec": True},
    "ALG": {"icao": "DAAG", "lat": 36.691, "lon": 3.215, "rwy": 230, "fleet": "Euroflyer", "spec": False},
    "GRZ": {"icao": "LOWG", "lat": 46.991, "lon": 15.439, "rwy": 350, "fleet": "Euroflyer", "spec": False},
    "VRN": {"icao": "LIPX", "lat": 45.396, "lon": 10.888, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "RBA": {"icao": "GMME", "lat": 34.051, "lon": -6.751, "rwy": 30, "fleet": "Euroflyer", "spec": False}
}

# 5. DATA FETCH & REASONING
if 'manual_stations' not in st.session_state: st.session_state.manual_stations = {}
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"
all_airports = {**base_airports, **st.session_state.manual_stations}

@st.cache_data(ttl=600)
def get_occ_intel(airport_dict):
    results = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            
            # Forecast Analysis
            f_alerts = []
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
                    elif "FZDZ" in line.raw: reason = "FZDZ"
                    elif "SN" in line.raw: reason = "SNOW"
                    elif v < 800: reason = "VIS"
                    elif c < 200: reason = "CLOUD"
                    
                    if reason:
                        results[iata+"_f"] = {"reason": reason, "v": v, "c": c, "p": f"{line.start_time.dt.strftime('%H')}-{line.end_time.dt.strftime('%H')}Z"}
                        break

            results[iata] = {
                "vis": m.data.visibility.value if m.data.visibility else 9999,
                "cig": 9999, "temp": m.data.temperature.value if m.data.temperature else 0,
                "w_spd": m.data.wind_speed.value or 0, "w_dir": m.data.wind_direction.value or 0,
                "raw_m": m.raw, "raw_t": t.raw, "status": "online"
            }
            if m.data.clouds:
                for layer in m.data.clouds:
                    if layer.type in ['BKN', 'OVC'] and layer.base: results[iata]["cig"] = min(results[iata]["cig"], layer.base * 100)
        except: results[iata] = {"status": "offline", "raw_m": "N/A", "raw_t": "N/A"}
    return results

weather_intel = get_occ_intel(all_airports)

# 6. ALERT CLASSIFICATION
metar_alerts = {}; taf_alerts = {}; red_list = []; green_stations = []; map_markers = []
for iata, info in all_airports.items():
    data = weather_intel.get(iata, {"status": "offline"})
    v_lim, c_lim = (1500, 500) if info['spec'] else (800, 200)
    
    # Actuals (METAR)
    if data['status'] == "online":
        xw = round(abs(data['w_spd'] * math.sin(math.radians(data['w_dir'] - info['rwy']))), 1) if info['rwy'] else 0
        m_reason, impact = None, ""
        
        if data['vis'] < v_lim or data['cig'] < c_lim: m_reason = "MINIMA"; impact = "Station below limits. Closed."
        elif xw > 25: m_reason = "XWIND"; impact = "High crosswind component."
        elif data['temp'] < -25: m_reason = "TEMP"; impact = "Extreme cold ops."
        elif "TSRA" in data['raw_m']: m_reason = "TSRA"; impact = "Active thunderstorms."
        
        if m_reason: 
            metar_alerts[iata] = {"type": m_reason, "impact": impact, "hex": "#d6001a" if "MINIMA" in m_reason else "#eb8f34"}
            if "MINIMA" in m_reason: red_list.append(iata)
        else: green_stations.append(iata)

        # Forecasts (TAF)
        f_data = weather_intel.get(iata+"_f")
        if f_data: taf_alerts[iata] = {"type": f_data['reason'], "period": f_data['p'], "vis": f_data['v'], "cig": f_data['c'], "hex": "#eb8f34"}

    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": "#008000" if iata not in metar_alerts else "#d6001a"})

# --- UI RENDER ---
if red_list: st.markdown(f'<div class="marquee"><span>🚨 ACTUALS BELOW MINIMA: {", ".join(red_list)}</span></div>', unsafe_allow_html=True)
st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)

# 7. MAP
m = folium.Map(location=[48.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=6, color=mkr['color'], fill=True).add_to(m)
st_folium(m, width=1400, height=400, key=f"map_v{len(map_markers)}")

# 8. ALERT BUTTON ROWS
st.markdown("### 🔴 ACTUALS (METAR)")
c1 = st.columns(12)
for i, (iata, d) in enumerate(metar_alerts.items()):
    with c1[i % 12]:
        st.markdown(f'<style>div[data-testid="stHorizontalBlock"] div:nth-child({(i%12)+1}) button {{ background-color: {d["hex"]}aa !important; border: 1px solid {d["hex"]} !important; }}</style>', unsafe_allow_html=True)
        if st.button(f"{iata}\nACTUAL\n{d['type']}", key=f"m_{iata}"): st.session_state.investigate_iata = iata

st.markdown("### 🟠 FORECASTS (TAF)")
c2 = st.columns(12)
for i, (iata, d) in enumerate(taf_alerts.items()):
    with c2[i % 12]:
        st.markdown(f'<style>div[data-testid="stHorizontalBlock"] div:nth-child({(i%12)+1}) button {{ background-color: {d["hex"]}aa !important; border: 1px solid {d["hex"]} !important; }}</style>', unsafe_allow_html=True)
        if st.button(f"{iata}\n{d['period']}\n{d['type']}", key=f"t_{iata}"): st.session_state.investigate_iata = iata

# 9. DIVE-DOWN ANALYSIS
if st.session_state.investigate_iata in all_airports:
    iata = st.session_state.investigate_iata
    d = weather_intel[iata]
    # Strategic Alternate
    alt_iata, min_dist = "None", 9999
    for g in green_stations:
        dist = calculate_dist(all_airports[iata]['lat'], all_airports[iata]['lon'], all_airports[g]['lat'], all_airports[g]['lon'])
        if dist < min_dist: min_dist = dist; alt_iata = g
    
    st.markdown(f"""
    <div class="reason-box">
        <h3>{iata} Strategic Analysis</h3>
        <p><b>Weather Summary:</b> METAR reports {d['raw_m']}. Visibility {d['vis']}m, Ceiling {d['cig']}ft.</p>
        <p><b>Impact Statement:</b> Flight operations likely restricted. Confirm Cat 3 capability for approaching arrivals.</p>
        <p style="color:#d6001a !important; font-weight:bold;"><b>✈️ Strategic Alternate:</b> {alt_iata} ({min_dist} NM)</p>
        <hr>
        <div style="display:flex; gap:20px;">
            <div><b>METAR:</b><br><small>{d['raw_m']}</small></div>
            <div><b>TAF:</b><br><small>{d['raw_t']}</small></div>
        </div>
    </div>""", unsafe_allow_html=True)
    if st.button("Close Analysis"): st.session_state.investigate_iata = "None"; st.rerun()

# 10. HANDOVER
st.markdown("---")
st.markdown("### 📝 Strategic Handover")
handover_txt = f"SHIFT HANDOVER - {datetime.now().strftime('%H:%M')}Z\n"
for iata, d in taf_alerts.items():
    handover_txt += f"[FCAST] {iata} {d['type']} ({d['vis']}m/{d['cig']}ft) {d['period']} - CAT3 Aircraft Advised\n"

st.text_area("Report Output:", value=handover_txt, height=150)
