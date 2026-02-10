import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC HUD v7", page_icon="✈️")

# 2. HUD CSS STYLING
st.markdown("""
    <style>
    .main .block-container { padding: 0; max-width: 100%; height: 100vh; overflow: hidden; }
    [data-testid="stSidebar"] { background-color: #002366 !important; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold; }
    input { color: #333333 !important; }
    div[data-baseweb="select"] div { color: #333333 !important; }

    /* TOP COMMAND BAR - PILL DESIGN */
    .top-command-bar {
        position: absolute; top: 15px; left: 50%; transform: translateX(-50%);
        z-index: 1000; background: rgba(0, 35, 102, 0.95); padding: 10px 30px;
        border-radius: 50px; border: 1px solid #005a9c; min-width: 500px;
        display: flex; justify-content: space-around; align-items: center;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.4);
    }
    
    .floating-alerts {
        position: absolute; top: 85px; right: 20px; z-index: 1000;
        background: rgba(0, 35, 102, 0.9); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; width: 280px; max-height: 55vh; overflow-y: auto;
    }

    .floating-analysis {
        position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%);
        z-index: 1001; background: rgba(255, 255, 255, 0.98); padding: 20px; 
        border-radius: 8px; width: 80%; max-width: 1100px; 
        border-top: 10px solid #d6001a; color: #002366 !important;
        box-shadow: 0px 10px 30px rgba(0,0,0,0.5);
    }
    .floating-analysis h3, .floating-analysis p, .floating-analysis b { color: #002366 !important; }

    div.stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; font-weight: bold; }
    div.stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 3. DATABASE
airports = {
    "LCY": {"icao": "EGLC", "name": "London City", "fleet": "Cityflyer", "rwy": 270, "lat": 51.505, "lon": 0.055},
    "AMS": {"icao": "EHAM", "name": "Amsterdam", "fleet": "Cityflyer", "rwy": 180, "lat": 52.313, "lon": 4.764},
    "RTM": {"icao": "EHRD", "name": "Rotterdam", "fleet": "Cityflyer", "rwy": 240, "lat": 51.957, "lon": 4.440},
    "DUB": {"icao": "EIDW", "name": "Dublin", "fleet": "Cityflyer", "rwy": 280, "lat": 53.421, "lon": -6.270},
    "GLA": {"icao": "EGPF", "name": "Glasgow", "fleet": "Cityflyer", "rwy": 230, "lat": 55.871, "lon": -4.433},
    "EDI": {"icao": "EGPH", "name": "Edinburgh", "fleet": "Cityflyer", "rwy": 240, "lat": 55.950, "lon": -3.363},
    "BHD": {"icao": "EGAC", "name": "Belfast City", "fleet": "Cityflyer", "rwy": 220, "lat": 54.618, "lon": -5.872},
    "STN": {"icao": "EGSS", "name": "Stansted", "fleet": "Cityflyer", "rwy": 220, "lat": 51.885, "lon": 0.235},
    "SEN": {"icao": "EGMC", "name": "Southend", "fleet": "Cityflyer", "rwy": 230, "lat": 51.571, "lon": 0.701},
    "FLR": {"icao": "LIRQ", "name": "Florence", "fleet": "Cityflyer", "rwy": 50, "lat": 43.810, "lon": 11.205},
    "LGW": {"icao": "EGKK", "name": "Gatwick", "fleet": "Euroflyer", "rwy": 260, "lat": 51.148, "lon": -0.190},
    "JER": {"icao": "EGJJ", "name": "Jersey", "fleet": "Euroflyer", "rwy": 260, "lat": 49.208, "lon": -2.195},
    "INN": {"icao": "LOWI", "name": "Innsbruck", "fleet": "Euroflyer", "rwy": 260, "lat": 47.260, "lon": 11.344},
    "SZG": {"icao": "LOWS", "name": "Salzburg", "fleet": "Euroflyer", "rwy": 330, "lat": 47.794, "lon": 13.004},
    "IVL": {"icao": "EFIV", "name": "Ivalo", "fleet": "Euroflyer", "rwy": 40, "lat": 68.607, "lon": 27.405},
}

def get_dist(lat1, lon1, lat2, lon2):
    R = 3440.065 # Nautical Miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a)), 0)

@st.cache_data(ttl=1800)
def fetch_wx(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update()
            t = Taf(info['icao']); t.update()
            v = m.data.visibility.value if m.data.visibility else 9999
            c = 9999
            if m.data.clouds:
                for layer in m.data.clouds:
                    if layer.type in ['BKN', 'OVC'] and layer.base: c = min(c, layer.base * 100)
            res[iata] = {"vis": v, "w_dir": m.data.wind_direction.value if m.data.wind_direction else 0, "w_spd": m.data.wind_speed.value if m.data.wind_speed else 0, "ceiling": c, "m": m.raw, "t": t.raw}
        except: continue
    return res

weather_data = fetch_wx(airports)

# SIDEBAR HUD CONTROL
st.sidebar.title("🔧 OCC HUD CONFIG")
ui_visible = st.sidebar.checkbox("DISPLAY OVERLAYS", value=True)
map_mode = st.sidebar.radio("MAP THEME", ["Dark Mode", "Light Mode"])
fleet_filter = st.sidebar.multiselect("FLEETS", ["Cityflyer", "Euroflyer"], default=["Cityflyer", "Euroflyer"])
search_iata = st.sidebar.text_input("IATA SEARCH", "").upper()

if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"
if 'minimized' not in st.session_state: st.session_state.minimized = False

# PROCESS DATA
active_alerts = {}; counts = {"Cityflyer": {"G":0,"A":0,"R":0}, "Euroflyer": {"G":0,"A":0,"R":0}}; map_markers = []; green_stations = []
for iata, d in weather_data.items():
    info = airports[iata]
    if info['fleet'] in fleet_filter:
        xw = round(abs(d['w_spd'] * math.sin(math.radians(d['w_dir'] - info['rwy']))), 1)
        color = "#008000"; a_type = None; reason = ""
        if xw > 25: a_type = "red"; reason = "HIGH X-WIND"
        elif d['vis'] < 800: a_type = "red"; reason = "LOW VIS"
        elif d['ceiling'] < 200: a_type = "red"; reason = "LOW CEILING"
        elif xw > 18 or d['vis'] < 1500 or d['ceiling'] < 500: a_type = "amber"; reason = "MARGINAL"
        
        if a_type:
            active_alerts[iata] = {"type": a_type, "reason": reason, "vis": d['vis'], "cig": d['ceiling'], "xw": xw, "m": d['m'], "t": d['t'], "lat": info['lat'], "lon": info['lon']}
            color = "#d6001a" if a_type == "red" else "#eb8f34"
            counts[info['fleet']]["R" if a_type=="red" else "A"] += 1
        else: 
            counts[info['fleet']]["G"] += 1
            green_stations.append(iata)
        map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "m": d['m'], "t": d['t']})

# SNAP-ZOOM LOGIC
map_center = [48.0, 5.0]; map_zoom = 5
if search_iata in airports: st.session_state.investigate_iata = search_iata
if st.session_state.investigate_iata in airports:
    target = airports[st.session_state.investigate_iata]
    map_center = [target["lat"], target["lon"]]; map_zoom = 10

# 1. THE MAP
tile = "CartoDB dark_matter" if map_mode == "Dark Mode" else "CartoDB positron"
m = folium.Map(location=map_center, zoom_start=map_zoom, tiles=tile, zoom_control=False)
for mkr in map_markers:
    popup_html = f"<div style='width:350px; color:black;'><b>METAR:</b> {mkr['m']}<br><br><b>TAF:</b> {mkr['t']}</div>"
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=14 if mkr['iata'] == st.session_state.investigate_iata else 7, color=mkr['color'], fill=True, fill_opacity=0.8, popup=folium.Popup(popup_html, max_width=400)).add_to(m)
st_folium(m, width=2200, height=1200, key="fullscreen_final")

# 2. HUD ELEMENTS
if ui_visible:
    st.markdown(f"""<div class="top-command-bar"><div style="font-size:14px;"><b>CITYFLYER:</b> {counts['Cityflyer']['G']}G | {counts['Cityflyer']['A']}A | {counts['Cityflyer']['R']}R</div><div style="font-size:14px; border-left: 1px solid #005a9c; padding-left: 20px;"><b>EUROFLYER:</b> {counts['Euroflyer']['G']}G | {counts['Euroflyer']['A']}A | {counts['Euroflyer']['R']}R</div></div>""", unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="floating-alerts">', unsafe_allow_html=True)
        st.write("⚠️ LIVE ALERTS")
        for iata, d in active_alerts.items():
            if st.button(f"{iata}: {d['reason']}", key=f"btn_{iata}", type="primary" if d['type'] == "red" else "secondary"):
                st.session_state.investigate_iata = iata; st.session_state.minimized = False; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# 3. DIVERSION ASSIST ANALYSIS
if st.session_state.investigate_iata in active_alerts and ui_visible:
    d = active_alerts[st.session_state.investigate_iata]
    
    # Calculate Nearest Alternate
    alt_name = "N/A"; alt_dist = 9999
    for g_iata in green_stations:
        dist = get_dist(d['lat'], d['lon'], airports[g_iata]['lat'], airports[g_iata]['lon'])
        if dist < alt_dist: alt_dist = dist; alt_name = g_iata

    if not st.session_state.minimized:
        st.markdown(f"""
        <div class="floating-analysis">
            <h3 style="margin:0;">{st.session_state.investigate_iata} OPERATIONAL ANALYSIS</h3>
            <p><b>ISSUE:</b> {d['reason']} detected. Current conditions below standard minima.</p>
            <p style="color:#d6001a !important;"><b>DIVERSION PLANNING:</b> Closest Green station is <b>{alt_name}</b> ({alt_dist} NM).</p>
            <p><b>OUTLOOK:</b> Forecast suggests probability of <b>ATC holding or slots</b>. Expect <b>long delays</b>.</p>
            <hr style="border:0.5px solid #ddd;">
            <p style="font-size:11px; background:#f4f4f4; padding:8px;"><b>TAF:</b> {d['t']}</p>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: 
            if st.button("🔽 MINIMIZE"): st.session_state.minimized = True; st.rerun()
        with c2:
            if st.button("✖ CLOSE"): st.session_state.investigate_iata = "None"; st.rerun()
    else:
        if st.button(f"🔼 EXPAND {st.session_state.investigate_iata} ALTERNATE: {alt_name}"):
            st.session_state.minimized = False; st.rerun()
