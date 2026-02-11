import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. ULTRA-REFINED HUD STYLING
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@200;400;700&display=swap');
    
    html, body, [class*="st-"], div, p, h1, h2, h3, h4, label { 
        font-family: 'Inter', sans-serif !important; 
    }
    
    [data-testid="stSidebar"] { background-color: #001a4d !important; }
    .ba-header { background-color: #002366; padding: 12px; border-radius: 2px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #d6001a; }

    /* DYNAMIC WIDTH ALERT BUTTONS */
    .stButton > button {
        border: 1px solid rgba(255,255,255,0.2) !important;
        color: white !important;
        text-transform: uppercase;
        font-size: 0.55rem !important;
        font-weight: 700 !important;
        padding: 2px 8px !important;
        border-radius: 2px !important;
        height: 36px !important;
        line-height: 1.1 !important;
        width: auto !important; /* Fits text length */
        min-width: 80px !important;
        white-space: pre !important;
        display: inline-block !important;
    }

    /* Container for wrapping buttons */
    .alert-container {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 20px;
    }

    .reason-box, .handover-container {
        background-color: #ffffff; padding: 15px; border-radius: 2px; 
        border-left: 5px solid #d6001a; color: #002366 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-top: 10px;
    }
    .reason-box h3, .reason-box p, .reason-box b, .reason-box span, .reason-box i { color: #002366 !important; }
    
    [data-testid="stTextArea"] textarea { color: #002366 !important; font-size: 0.8rem !important; background-color: #f4f4f4 !important; font-family: monospace !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. UTILITIES
def calculate_dist(lat1, lon1, lat2, lon2):
    R = 3440.065 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)

# 4. MASTER DATABASE (46 STATIONS)
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
    "SEN": {"icao": "EGMC", "lat": 51.571, "lon": 0.701, "rwy": 230, "fleet": "Cityflyer", "spec": False},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer", "spec": True},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 180, "fleet": "Cityflyer", "spec": True},
    "ALG": {"icao": "DAAG", "lat": 36.691, "lon": 3.215, "rwy": 230, "fleet": "Euroflyer", "spec": False},
    "GRZ": {"icao": "LOWG", "lat": 46.991, "lon": 15.439, "rwy": 350, "fleet": "Euroflyer", "spec": False},
    "VRN": {"icao": "LIPX", "lat": 45.396, "lon": 10.888, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "RBA": {"icao": "GMME", "lat": 34.051, "lon": -6.751, "rwy": 30, "fleet": "Euroflyer", "spec": False},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "Euroflyer", "spec": False},
    "OPO": {"icao": "LPPR", "lat": 41.242, "lon": -8.678, "rwy": 350, "fleet": "Euroflyer", "spec": False},
    "LYS": {"icao": "LFLL", "lat": 45.726, "lon": 5.090, "rwy": 350, "fleet": "Euroflyer", "spec": False},
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

# 5. DATA FETCH & PREDICTIVE LOGIC
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"
all_airports = base_airports

@st.cache_data(ttl=600)
def get_occ_intel(airport_dict):
    results = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update(); t = Taf(info['icao']); t.update()
            
            f_res = None
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
                        f_res = {"reason": reason, "v": v, "c": c, "p": f"{line.start_time.dt.strftime('%H')}-{line.end_time.dt.strftime('%H')}Z"}
                        break

            results[iata] = {
                "vis": m.data.visibility.value if m.data.visibility else 9999,
                "cig": 9999, "temp": m.data.temperature.value if m.data.temperature else 0,
                "w_spd": m.data.wind_speed.value or 0, "w_dir": m.data.wind_direction.value or 0,
                "raw_m": m.raw, "raw_t": t.raw, "status": "online", "forecast": f_res
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
    
    if data['status'] == "online":
        xw = round(abs(data['w_spd'] * math.sin(math.radians(data['w_dir'] - info['rwy']))), 1) if info['rwy'] else 0
        m_reason, impact = None, ""
        
        if data['vis'] < v_lim or data['cig'] < c_lim: m_reason = "MINIMA"; impact = "Station below limits. Closed."
        elif xw > 25: m_reason = "XWIND"; impact = "High crosswind component."
        elif data['temp'] < -25: m_reason = "TEMP"; impact = "Extreme cold ops."
        elif "TSRA" in data['raw_m']: m_reason = "TSRA"; impact = "Active thunderstorms."
        elif "FG" in data['raw_m']: m_reason = "FOG"; impact = "Low Visibility Procedures."

        if m_reason: 
            metar_alerts[iata] = {"type": m_reason, "impact": impact, "hex": "#d6001a" if "MINIMA" in m_reason else "#eb8f34"}
            if "MINIMA" in m_reason: red_list.append(iata)
        else: green_stations.append(iata)

        f_data = data.get('forecast')
        if f_data: taf_alerts[iata] = {"type": f_data['reason'], "period": f_data['p'], "vis": f_data['v'], "cig": f_data['c'], "hex": "#eb8f34" if f_data['v'] > v_lim else "#d6001a"}

    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": "#008000" if iata not in metar_alerts else "#d6001a"})

# --- UI RENDER ---
st.markdown(f'<div class="ba-header"><div>OCC WEATHER HUD</div><div>{datetime.now().strftime("%H:%M")} UTC</div></div>', unsafe_allow_html=True)

# 7. MAP
m = folium.Map(location=[48.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")
for mkr in map_markers:
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=6, color=mkr['color'], fill=True).add_to(m)
st_folium(m, width=1400, height=400, key="map_v1")

# 8. TACTICAL ALERTS (METAR)
st.markdown("### 🔴 ACTUAL WEATHER (METAR)")
st.markdown('<div class="alert-container">', unsafe_allow_html=True)
for iata, d in metar_alerts.items():
    st.markdown(f'<style>#btn_m_{iata} > button {{ background-color: {d["hex"]}aa !important; border: 1px solid {d["hex"]} !important; }}</style>', unsafe_allow_html=True)
    if st.button(f"{iata}\nNOW\n{d['type']}", key=f"btn_m_{iata}"): st.session_state.investigate_iata = iata
st.markdown('</div>', unsafe_allow_html=True)

# 9. FORECAST ALERTS (TAF)
st.markdown("### 🟠 FORECAST ALERTS (TAF)")
st.markdown('<div class="alert-container">', unsafe_allow_html=True)
for iata, d in taf_alerts.items():
    st.markdown(f'<style>#btn_t_{iata} > button {{ background-color: {d["hex"]}aa !important; border: 1px solid {d["hex"]} !important; }}</style>', unsafe_allow_html=True)
    if st.button(f"{iata}\n{d['period']}\n{d['type']}", key=f"btn_t_{iata}"): st.session_state.investigate_iata = iata
st.markdown('</div>', unsafe_allow_html=True)

# 10. DIVE-DOWN ANALYSIS
if st.session_state.investigate_iata in all_airports:
    iata = st.session_state.investigate_iata
    d = weather_intel[iata]
    alt_iata, min_dist = "None", 9999
    for g in green_stations:
        dist = calculate_dist(all_airports[iata]['lat'], all_airports[iata]['lon'], all_airports[g]['lat'], all_airports[g]['lon'])
        if dist < min_dist: min_dist = dist; alt_iata = g
    
    st.markdown(f"""
    <div class="reason-box">
        <h3>{iata} Strategic Analysis</h3>
        <p><b>Weather Summary:</b> Visibility {d['vis']}m, Ceiling {d['cig']}ft. Trend based on TAF: {d['forecast']['reason'] if d.get('forecast') else 'Stable'}.</p>
        <p><b>Impact Statement:</b> Flight operations likely restricted. Confirm Cat 3 capability for approaching arrivals.</p>
        <p style="color:#d6001a !important; font-weight:bold;"><b>✈️ Strategic Alternate:</b> {alt_iata} ({min_dist} NM)</p>
        <hr>
        <div style="display:flex; gap:20px;">
            <div><b>METAR:</b><br><small>{d['raw_m']}</small></div>
            <div><b>TAF:</b><br><small>{d['raw_t']}</small></div>
        </div>
    </div>""", unsafe_allow_html=True)

# 11. HANDOVER
st.markdown("---")
st.markdown("### 📝 Strategic Handover")
handover_txt = f"SHIFT HANDOVER - {datetime.now().strftime('%H:%M')}Z\n"
for iata, d in taf_alerts.items():
    handover_txt += f"{iata} {d['type']} {d['vis']}m/{d['cig']}ft {d['period']} - CAT3 Aircraft Advised\n"
st.text_area("Report Output:", value=handover_txt, height=150)
