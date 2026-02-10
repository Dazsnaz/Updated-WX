import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC HUD v5", page_icon="✈️")

# 2. HUD CSS STYLING
st.markdown("""
    <style>
    .main .block-container { padding: 0; max-width: 100%; height: 100vh; overflow: hidden; }
    
    /* SIDEBAR TEXT VISIBILITY */
    [data-testid="stSidebar"] { background-color: #002366 !important; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold; font-size: 14px; }
    input { color: #333333 !important; }
    div[data-baseweb="select"] div { color: #333333 !important; }

    /* POSITION 1: TOP COMMAND BAR (Fleet Status) */
    .top-command-bar {
        position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
        z-index: 1000; background: rgba(0, 35, 102, 0.9); padding: 10px 30px;
        border-radius: 50px; border: 1px solid #005a9c; min-width: 600px;
        display: flex; justify-content: space-between; align-items: center;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.3);
    }
    
    /* POSITION 2: MID RIGHT (Live Alerts) */
    .floating-alerts {
        position: absolute; top: 80px; right: 20px; z-index: 1000;
        background: rgba(0, 35, 102, 0.9); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; width: 280px; max-height: 60vh; overflow-y: auto;
    }

    /* POSITION 3: BOTTOM CENTER (Analysis) */
    .floating-analysis {
        position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%);
        z-index: 1001; background: rgba(255, 255, 255, 0.98); padding: 20px; 
        border-radius: 8px; width: 75%; max-width: 1000px; 
        border-top: 10px solid #d6001a; color: #002366 !important;
        box-shadow: 0px 10px 30px rgba(0,0,0,0.5);
    }
    .floating-analysis h3, .floating-analysis p, .floating-analysis b { color: #002366 !important; }

    div.stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; font-weight: bold; }
    div.stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 3. FULL 42 AIRPORT DATABASE
airports = {
    # CITYFLYER
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
    "AGP": {"icao": "LEMG", "name": "Malaga", "fleet": "Cityflyer", "rwy": 130, "lat": 36.675, "lon": -4.499},
    "BER": {"icao": "EDDB", "name": "Berlin", "fleet": "Cityflyer", "rwy": 250, "lat": 52.362, "lon": 13.501},
    "FRA": {"icao": "EDDF", "name": "Frankfurt", "fleet": "Cityflyer", "rwy": 250, "lat": 50.033, "lon": 8.571},
    "LIN": {"icao": "LIML", "name": "Milan Linate", "fleet": "Cityflyer", "rwy": 360, "lat": 45.445, "lon": 9.277},
    "CMF": {"icao": "LFLB", "name": "Chambery", "fleet": "Cityflyer", "rwy": 180, "lat": 45.638, "lon": 5.880},
    "GVA": {"icao": "LSGG", "name": "Geneva", "fleet": "Cityflyer", "rwy": 220, "lat": 46.237, "lon": 6.109},
    "ZRH": {"icao": "LSZH", "name": "Zurich", "fleet": "Cityflyer", "rwy": 160, "lat": 47.458, "lon": 8.548},
    "MAD": {"icao": "LEMD", "name": "Madrid", "fleet": "Cityflyer", "rwy": 140, "lat": 40.494, "lon": -3.567},
    "IBZ": {"icao": "LEIB", "name": "Ibiza", "fleet": "Cityflyer", "rwy": 60, "lat": 38.873, "lon": 1.373},
    "PMI": {"icao": "LEPA", "name": "Palma", "fleet": "Cityflyer", "rwy": 240, "lat": 39.551, "lon": 2.738},
    "FAO": {"icao": "LPFR", "name": "Faro", "fleet": "Cityflyer", "rwy": 280, "lat": 37.017, "lon": -7.965},
    # EUROFLYER
    "LGW": {"icao": "EGKK", "name": "Gatwick", "fleet": "Euroflyer", "rwy": 260, "lat": 51.148, "lon": -0.190},
    "JER": {"icao": "EGJJ", "name": "Jersey", "fleet": "Euroflyer", "rwy": 260, "lat": 49.208, "lon": -2.195},
    "OPO": {"icao": "LPPR", "name": "Porto", "fleet": "Euroflyer", "rwy": 350, "lat": 41.242, "lon": -8.678},
    "LYS": {"icao": "LFLL", "name": "Lyon", "fleet": "Euroflyer", "rwy": 350, "lat": 45.726, "lon": 5.090},
    "INN": {"icao": "LOWI", "name": "Innsbruck", "fleet": "Euroflyer", "rwy": 260, "lat": 47.260, "lon": 11.344},
    "SZG": {"icao": "LOWS", "name": "Salzburg", "fleet": "Euroflyer", "rwy": 330, "lat": 47.794, "lon": 13.004},
    "BOD": {"icao": "LFBD", "name": "Bordeaux", "fleet": "Euroflyer", "rwy": 230, "lat": 44.828, "lon": -0.716},
    "GNB": {"icao": "LFLS", "name": "Grenoble", "fleet": "Euroflyer", "rwy": 90, "lat": 45.363, "lon": 5.330},
    "NCE": {"icao": "LFMN", "name": "Nice", "fleet": "Euroflyer", "rwy": 40, "lat": 43.665, "lon": 7.215},
    "TRN": {"icao": "LIMF", "name": "Turin", "fleet": "Euroflyer", "rwy": 360, "lat": 45.202, "lon": 7.649},
    "VRN": {"icao": "LIPX", "name": "Verona", "fleet": "Euroflyer", "rwy": 40, "lat": 45.396, "lon": 10.888},
    "ALC": {"icao": "LEAL", "name": "Alicante", "fleet": "Euroflyer", "rwy": 100, "lat": 38.282, "lon": -0.558},
    "SVQ": {"icao": "LEZL", "name": "Seville", "fleet": "Euroflyer", "rwy": 270, "lat": 37.418, "lon": -5.893},
    "RAK": {"icao": "GMMX", "name": "Marrakesh", "fleet": "Euroflyer", "rwy": 100, "lat": 31.606, "lon": -8.036},
    "AGA": {"icao": "GMAD", "name": "Agadir", "fleet": "Euroflyer", "rwy": 90, "lat": 30.325, "lon": -9.413},
    "SSH": {"icao": "HESH", "name": "Sharm El Sheikh", "fleet": "Euroflyer", "rwy": 40, "lat": 27.977, "lon": 34.394},
    "PFO": {"icao": "LCPH", "name": "Paphos", "fleet": "Euroflyer", "rwy": 290, "lat": 34.718, "lon": 32.486},
    "LCA": {"icao": "LCLK", "name": "Larnaca", "fleet": "Euroflyer", "rwy": 220, "lat": 34.875, "lon": 33.625},
    "FUE": {"icao": "GCLP", "name": "Fuerteventura", "fleet": "Euroflyer", "rwy": 10, "lat": 28.452, "lon": -13.864},
    "TFS": {"icao": "GCTS", "name": "Tenerife South", "fleet": "Euroflyer", "rwy": 70, "lat": 28.044, "lon": -16.572},
    "ACE": {"icao": "GCRR", "name": "Lanzarote", "fleet": "Euroflyer", "rwy": 30, "lat": 28.945, "lon": -13.605},
    "LPA": {"icao": "GCLP", "name": "Gran Canaria", "fleet": "Euroflyer", "rwy": 30, "lat": 27.931, "lon": -15.386},
    "IVL": {"icao": "EFIV", "name": "Ivalo", "fleet": "Euroflyer", "rwy": 40, "lat": 68.607, "lon": 27.405},
    "MLA": {"icao": "LMML", "name": "Malta", "fleet": "Euroflyer", "rwy": 310, "lat": 35.857, "lon": 14.477},
    "FNC": {"icao": "LPMA", "name": "Madeira", "fleet": "Euroflyer", "rwy": 50, "lat": 32.694, "lon": -16.774},
}

def get_xwind(w_dir, w_spd, rwy):
    if not w_dir or not w_spd: return 0
    return round(abs(w_spd * math.sin(math.radians(w_dir - rwy))), 1)

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
                    if layer.type in ['BKN', 'OVC'] and layer.base:
                        c = min(c, layer.base * 100)
            res[iata] = {"vis": v, "w_dir": m.data.wind_direction.value if m.data.wind_direction else 0, "w_spd": m.data.wind_speed.value if m.data.wind_speed else 0, "ceiling": c, "m": m.raw, "t": t.raw}
        except: continue
    return res

weather_data = fetch_wx(airports)

# SIDEBAR CONTROLS
st.sidebar.title("🔧 OCC HUD CONFIG")
ui_visible = st.sidebar.checkbox("SHOW HUD LAYERS", value=True)
map_mode = st.sidebar.radio("MAP THEME", ["Dark Mode", "Light Mode"])
fleet_filter = st.sidebar.multiselect("FLEETS", ["Cityflyer", "Euroflyer"], default=["Cityflyer", "Euroflyer"])
search_iata = st.sidebar.text_input("IATA SEARCH", "").upper()

if st.sidebar.button("FORCE DATA REFRESH"):
    st.cache_data.clear()
    st.rerun()

# HUD STATE MANAGEMENT
if 'last_red' not in st.session_state: st.session_state.last_red = 0
if 'minimized' not in st.session_state: st.session_state.minimized = False
if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"
if search_iata in airports: st.session_state.investigate_iata = search_iata

# DATA PROCESSING
active_alerts = {}; counts = {"Cityflyer": {"G":0,"A":0,"R":0}, "Euroflyer": {"G":0,"A":0,"R":0}}; map_markers = []
curr_red = 0

for iata, d in weather_data.items():
    info = airports[iata]
    if info['fleet'] in fleet_filter:
        xw = get_xwind(d['w_dir'], d['w_spd'], info['rwy'])
        color = "#008000"; a_type = None; reason = ""
        if xw > 25: a_type = "red"; reason = "HIGH X-WIND"
        elif d['vis'] < 800: a_type = "red"; reason = "LOW VIS"
        elif d['ceiling'] < 200: a_type = "red"; reason = "LOW CEILING"
        elif xw > 18 or d['vis'] < 1500 or d['ceiling'] < 500: a_type = "amber"; reason = "MARGINAL"
        
        if a_type:
            active_alerts[iata] = {"type": a_type, "reason": reason, "vis": d['vis'], "cig": d['ceiling'], "xw": xw, "m": d['m'], "t": d['t']}
            color = "#d6001a" if a_type == "red" else "#eb8f34"
            counts[info['fleet']]["R" if a_type=="red" else "A"] += 1
            if a_type == "red": curr_red += 1
        else: counts[info['fleet']]["G"] += 1
        map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "m": d['m'], "t": d['t']})

trend = "➡️"
if curr_red > st.session_state.last_red: trend = "📈"
elif curr_red < st.session_state.last_red: trend = "📉"
st.session_state.last_red = curr_red

# 1. MAP BACKGROUND
tile = "CartoDB dark_matter" if map_mode == "Dark Mode" else "CartoDB positron"
m = folium.Map(location=[48.0, 5.0], zoom_start=5, tiles=tile, zoom_control=False)
for mkr in map_markers:
    popup_html = f"<div style='width:350px; color:black;'><b>METAR:</b> {mkr['m']}<br><br><b>TAF:</b> {mkr['t']}</div>"
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=12 if mkr['iata'] == st.session_state.investigate_iata else 7, color=mkr['color'], fill=True, fill_opacity=0.8, popup=folium.Popup(popup_html, max_width=400)).add_to(m)
st_folium(m, width=2200, height=1200, key="fullscreen_final")

# 2. TOP COMMAND BAR (HUD)
if ui_visible:
    st.markdown(f"""
    <div class="top-command-bar">
        <div style="font-weight:bold; font-size:16px; color:#d6001a !important;">{trend} NETWORK HEALTH</div>
        <div style="font-size:14px;"><b>CF:</b> {counts['Cityflyer']['G']}G | {counts['Cityflyer']['A']}A | {counts['Cityflyer']['R']}R</div>
        <div style="font-size:14px;"><b>EF:</b> {counts['Euroflyer']['G']}G | {counts['Euroflyer']['A']}A | {counts['Euroflyer']['R']}R</div>
        <div style="font-size:12px; opacity:0.8;">{datetime.now().strftime("%H:%M")} UTC</div>
    </div>
    """, unsafe_allow_html=True)

    # 3. ALERTS (HUD)
    with st.container():
        st.markdown('<div class="floating-alerts">', unsafe_allow_html=True)
        st.write("⚠️ LIVE ALERTS")
        if not active_alerts: st.write("Clean Network")
        for iata, d in active_alerts.items():
            if st.button(f"{iata}: {d['reason']}", key=f"btn_{iata}", type="primary" if d['type'] == "red" else "secondary"):
                st.session_state.investigate_iata = iata; st.session_state.minimized = False; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# 4. ANALYSIS (HUD)
if st.session_state.investigate_iata in active_alerts and ui_visible:
    d = active_alerts[st.session_state.investigate_iata]
    if st.session_state.minimized:
        if st.button(f"🔼 EXPAND {st.session_state.investigate_iata} ANALYSIS"): st.session_state.minimized = False; st.rerun()
    else:
        st.markdown(f"""
        <div class="floating-analysis">
            <h3 style="margin:0;">{st.session_state.investigate_iata} OPERATIONAL ANALYSIS</h3>
            <p><b>ISSUE:</b> {d['reason']} detected. Current conditions below standard landing minima.</p>
            <p><b>OUTLOOK:</b> Forecast suggests high probability of <b>ATC holding or diversions</b>. Expect <b>operational delays</b> if trend continues.</p>
            <hr style="border:0.5px solid #ddd;">
            <p style="font-size:11px; background:#f4f4f4; padding:8px;"><b>TAF:</b> {d['t']}</p>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns([5,5])
        with c1: 
            if st.button("🔽 MINIMIZE"): st.session_state.minimized = True; st.rerun()
        with c2:
            if st.button("✖ CLOSE"): st.session_state.investigate_iata = "None"; st.rerun()
