import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Fullscreen", page_icon="✈️")

# 2. CUSTOM CSS FOR LAYERED UI
st.markdown("""
    <style>
    /* Force Full Screen for Map */
    .main .block-container { padding: 0; max-width: 100%; }
    
    /* Global Font Color */
    html, body, [class*="st-"], div, p, h1, h2, h3, h4, label { color: white !important; }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] { background-color: #002366 !important; }

    /* FLOATING DASHBOARD PANEL */
    .floating-stats {
        position: absolute; top: 10px; left: 60px; z-index: 1000;
        background: rgba(0, 35, 102, 0.85); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; min-width: 400px; pointer-events: none;
    }
    
    /* FLOATING ALERTS PANEL */
    .floating-alerts {
        position: absolute; top: 10px; right: 20px; z-index: 1000;
        background: rgba(0, 35, 102, 0.85); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; width: 320px; max-height: 80vh; overflow-y: auto;
    }

    /* Floating Analysis Box (Bottom) */
    .floating-analysis {
        position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%);
        z-index: 1001; background: white; padding: 20px; border-radius: 8px;
        width: 800px; border-top: 10px solid #002366; color: #002366 !important;
    }
    .floating-analysis * { color: #002366 !important; }

    /* Button Styling */
    div.stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; font-weight: bold; width: 100%; }
    div.stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; font-weight: bold; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# 3. COMPLETE FLEET DATABASE (Abbreviated for code length, keep your full dict here)
airports = {
    "LCY": {"icao": "EGLC", "name": "London City", "fleet": "Cityflyer", "rwy": 270, "lat": 51.505, "lon": 0.055},
    "AMS": {"icao": "EHAM", "name": "Amsterdam", "fleet": "Cityflyer", "rwy": 180, "lat": 52.313, "lon": 4.764},
    "STN": {"icao": "EGSS", "name": "Stansted", "fleet": "Cityflyer", "rwy": 220, "lat": 51.885, "lon": 0.235},
    "LGW": {"icao": "EGKK", "name": "Gatwick", "fleet": "Euroflyer", "rwy": 260, "lat": 51.148, "lon": -0.190},
    "INN": {"icao": "LOWI", "name": "Innsbruck", "fleet": "Euroflyer", "rwy": 260, "lat": 47.260, "lon": 11.344},
    "FNC": {"icao": "LPMA", "name": "Madeira", "fleet": "Euroflyer", "rwy": 50, "lat": 32.694, "lon": -16.774},
    # Add all 42 airports back in here...
}

def get_xwind(w_dir, w_spd, rwy):
    if not w_dir or not w_spd: return 0
    return round(abs(w_spd * math.sin(math.radians(w_dir - rwy))), 1)

@st.cache_data(ttl=1800)
def get_fleet_weather(airport_dict):
    results = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update()
            t = Taf(info['icao']); t.update()
            results[iata] = {
                "vis": m.data.visibility.value if m.data.visibility else 9999,
                "w_dir": m.data.wind_direction.value if m.data.wind_direction else 0,
                "w_spd": m.data.wind_speed.value if m.data.wind_speed else 0,
                "ceiling": 9999, "raw_metar": m.raw, "raw_taf": t.raw
            }
            if m.data.clouds:
                for layer in m.data.clouds:
                    if layer.type in ['BKN', 'OVC'] and layer.base:
                        results[iata]["ceiling"] = min(results[iata]["ceiling"], layer.base * 100)
        except: continue
    return results

# DATA FETCH
weather_data = get_fleet_weather(airports)

# SIDEBAR CONTROLS
st.sidebar.title("🔧 OCC Controls")
ui_visible = st.sidebar.checkbox("Show HUD Overlay", value=True)
search_iata = st.sidebar.text_input("IATA Search", "").upper()
fleet_filter = st.sidebar.multiselect("Active Fleet", ["Cityflyer", "Euroflyer"], default=["Cityflyer", "Euroflyer"])

if st.sidebar.button("🔄 Manual Refresh"):
    st.cache_data.clear()
    st.rerun()

if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"
if search_iata in airports: st.session_state.investigate_iata = search_iata

# PROCESS DATA
active_alerts = {}
counts = {"Cityflyer": {"green": 0, "orange": 0, "red": 0}, "Euroflyer": {"green": 0, "orange": 0, "red": 0}}
map_markers = []

for iata, data in weather_data.items():
    info = airports[iata]
    if info['fleet'] in fleet_filter:
        xw = get_xwind(data['w_dir'], data['w_spd'], info['rwy'])
        color = "#008000"; alert_type = None; reason = ""
        
        if xw > 25: alert_type = "red"; reason = "HIGH X-WIND"
        elif data['vis'] < 800: alert_type = "red"; reason = "LOW VIS"
        elif data['ceiling'] < 200: alert_type = "red"; reason = "LOW CEILING"
        elif xw > 18: alert_type = "amber"; reason = "MARGINAL X-WIND"
        elif data['vis'] < 1500: alert_type = "amber"; reason = "MARGINAL VIS"
        elif data['ceiling'] < 500: alert_type = "amber"; reason = "MARGINAL CIG"

        if alert_type:
            active_alerts[iata] = {"type": alert_type, "reason": reason, "vis": data['vis'], "ceiling": data['ceiling'], "xw": xw, "metar": data['raw_metar'], "taf": data['raw_taf']}
            color = "#d6001a" if alert_type == "red" else "#eb8f34"
            counts[info['fleet']]["red" if alert_type=="red" else "orange"] += 1
        else: counts[info['fleet']]["green"] += 1
        map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "metar": data['raw_metar'], "taf": data['raw_taf']})

# --- RENDER UI ---

# 1. THE FULLSCREEN MAP (Background Layer)
map_center = [48.0, 5.0]; zoom = 5
if st.session_state.investigate_iata in airports:
    target = airports[st.session_state.investigate_iata]
    map_center = [target["lat"], target["lon"]]; zoom = 10

m = folium.Map(location=map_center, zoom_start=zoom, tiles="CartoDB dark_matter", zoom_control=False)
for mkr in map_markers:
    popup_html = f"<div style='width:300px; color:black;'><b>METAR:</b> {mkr['metar']}<br><b>TAF:</b> {mkr['taf']}</div>"
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=10 if mkr['iata'] == st.session_state.investigate_iata else 6, color=mkr['color'], fill=True, fill_opacity=0.8, popup=folium.Popup(popup_html, max_width=400)).add_to(m)

st_folium(m, width=2000, height=900, key="full_screen_map")

# 2. THE HUD OVERLAY (Floating Layer)
if ui_visible:
    # Top Left Stats
    st.markdown(f"""
    <div class="floating-stats">
        <h4 style="margin:0;">BA OCC FLEET STATUS</h4>
        <hr style="margin:10px 0;">
        <div style="display:flex; justify-content:space-between;">
            <div><b>CF:</b> {counts['Cityflyer']['green']}G | {counts['Cityflyer']['orange']}A | {counts['Cityflyer']['red']}R</div>
            <div><b>EF:</b> {counts['Euroflyer']['green']}G | {counts['Euroflyer']['orange']}A | {counts['Euroflyer']['red']}R</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Top Right Alerts
    with st.container():
        st.markdown('<div class="floating-alerts">', unsafe_allow_html=True)
        st.write("⚠️ ACTIVE ALERTS")
        for iata, d in active_alerts.items():
            if st.button(f"{iata}: {d['reason']}", key=f"btn_{iata}", type="primary" if d['type'] == "red" else "secondary"):
                st.session_state.investigate_iata = iata
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# 3. ANALYSIS BOX (Bottom Layer)
if st.session_state.investigate_iata in active_alerts and ui_visible:
    d = active_alerts[st.session_state.investigate_iata]
    st.markdown(f"""
    <div class="floating-analysis">
        <h3 style="margin:0;">{st.session_state.investigate_iata} Deep-Dive Analysis</h3>
        <p><b>Issue:</b> {d['reason']} identified. Operating below standard limits.</p>
        <p><b>Impact:</b> May cause diversions or ATC slots. Long delays expected to the operation.</p>
        <hr>
        <p style="font-size:11px;"><b>TAF Forecast:</b> {d['taf']}</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Close Analysis", key="close_view"):
        st.session_state.investigate_iata = "None"; st.rerun()
