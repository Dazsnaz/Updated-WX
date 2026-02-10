import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC HUD v2", page_icon="✈️")

# 2. ADVANCED HUD STYLING
st.markdown("""
    <style>
    .main .block-container { padding: 0; max-width: 100%; height: 100vh; overflow: hidden; }
    [data-testid="stSidebar"] { background-color: #002366 !important; }
    input { color: #333333 !important; }
    div[data-baseweb="select"] div { color: #333333 !important; }
    [data-testid="stSidebar"] label p { color: white !important; font-weight: bold; }

    /* PANEL 1: FLEET STATUS (Top Left) */
    .floating-stats {
        position: absolute; top: 20px; left: 80px; z-index: 1000;
        background: rgba(0, 35, 102, 0.85); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; min-width: 320px;
    }
    
    /* PANEL 2: ALERTS (Mid Right) */
    .floating-alerts {
        position: absolute; top: 120px; right: 20px; z-index: 1000;
        background: rgba(0, 35, 102, 0.85); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; width: 260px; max-height: 45vh; overflow-y: auto;
    }

    /* PANEL 3: ANALYSIS (Bottom Center) */
    .floating-analysis {
        position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%);
        z-index: 1001; background: rgba(255, 255, 255, 0.98); padding: 20px; 
        border-radius: 8px; width: 70%; max-width: 900px; 
        border-top: 10px solid #d6001a; color: #002366 !important;
        box-shadow: 0px 10px 30px rgba(0,0,0,0.5);
    }
    .floating-analysis h3, .floating-analysis p, .floating-analysis b { color: #002366 !important; }
    
    /* Minimized Style */
    .minimized-analysis {
        position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%);
        z-index: 1001; background: #d6001a; color: white !important;
        padding: 5px 20px; border-radius: 20px; font-weight: bold; cursor: pointer;
    }

    div.stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; font-weight: bold; width: 100%; border: none; }
    div.stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; font-weight: bold; width: 100%; border: none; }
    </style>
    """, unsafe_allow_html=True)

# 3. DATABASE HOOK
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
    "OPO": {"icao": "LPPR", "name": "Porto", "fleet": "Euroflyer", "rwy": 350, "lat": 41.242, "lon": -8.678},
    "INN": {"icao": "LOWI", "name": "Innsbruck", "fleet": "Euroflyer", "rwy": 260, "lat": 47.260, "lon": 11.344},
    "SZG": {"icao": "LOWS", "name": "Salzburg", "fleet": "Euroflyer", "rwy": 330, "lat": 47.794, "lon": 13.004},
    "IVL": {"icao": "EFIV", "name": "Ivalo", "fleet": "Euroflyer", "rwy": 40, "lat": 68.607, "lon": 27.405},
}

@st.cache_data(ttl=1800)
def fetch_wx(airport_dict):
    res = {}
    for iata, info in airport_dict.items():
        try:
            m = Metar(info['icao']); m.update()
            t = Taf(info['icao']); t.update()
            res[iata] = {"vis": m.data.visibility.value if m.data.visibility else 9999,
                         "w_dir": m.data.wind_direction.value if m.data.wind_direction else 0,
                         "w_spd": m.data.wind_speed.value if m.data.wind_speed else 0,
                         "ceiling": 9999, "raw_m": m.raw, "raw_t": t.raw}
            if m.data.clouds:
                for l in m.data.clouds:
                    if l.type in ['BKN', 'OVC'] and l.base: res[iata]["ceiling"] = min(res[iata]["ceiling"], l.base * 100)
        except: continue
    return res

weather_data = fetch_wx(airports)

# SIDEBAR HUD CONTROL
st.sidebar.title("🔧 HUD CONTROL")
ui_visible = st.sidebar.checkbox("MASTER HUD TOGGLE", value=True)
if 'minimized' not in st.session_state: st.session_state.minimized = False
if st.sidebar.button("RESET HUD"):
    st.session_state.investigate_iata = "None"
    st.session_state.minimized = False
    st.rerun()

# SEARCH LOGIC
search_iata = st.sidebar.text_input("IATA SEARCH", "").upper()
if search_iata in airports: st.session_state.investigate_iata = search_iata

# DATA PROCESSING
active_alerts = {}; counts = {"Cityflyer": {"G":0,"A":0,"R":0}, "Euroflyer": {"G":0,"A":0,"R":0}}; map_markers = []
for iata, d in weather_data.items():
    info = airports[iata]; xw = round(abs(d['w_spd'] * math.sin(math.radians(d['w_dir'] - info['rwy']))), 1)
    color = "#008000"; a_type = None; reason = ""
    if xw > 25: a_type = "red"; reason = "X-WIND"
    elif d['vis'] < 800: a_type = "red"; reason = "LOW VIS"
    elif d['ceiling'] < 200: a_type = "red"; reason = "CEILING"
    elif xw > 18 or d['vis'] < 1500 or d['ceiling'] < 500: a_type = "amber"; reason = "MARGINAL"
    
    if a_type:
        active_alerts[iata] = {"type": a_type, "reason": reason, "vis": d['vis'], "cig": d['ceiling'], "xw": xw, "m": d['raw_m'], "t": d['raw_t']}
        color = "#d6001a" if a_type == "red" else "#eb8f34"
        counts[info['fleet']]["R" if a_type=="red" else "A"] += 1
    else: counts[info['fleet']]["G"] += 1
    map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "m": d['raw_m'], "t": d['raw_t']})

# 1. THE MAP
map_center = [48.0, 5.0]; zoom = 5
if st.session_state.investigate_iata in airports:
    target = airports[st.session_state.investigate_iata]
    map_center = [target["lat"], target["lon"]]; zoom = 10

m = folium.Map(location=map_center, zoom_start=zoom, tiles="CartoDB dark_matter", zoom_control=False)
for mkr in map_markers:
    popup_html = f"""<div style="width:400px; color:black;"><b>METAR:</b> {mkr['m']}<br><br><b>TAF:</b> {mkr['t']}</div>"""
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=10 if mkr['iata'] == st.session_state.investigate_iata else 6, color=mkr['color'], fill=True, fill_opacity=0.8, popup=folium.Popup(popup_html, max_width=450)).add_to(m)
st_folium(m, width=2200, height=1100, key="fullscreen_occ")

# 2. UI HUD
if ui_visible:
    # Stats (Top Left)
    st.markdown(f"""<div class="floating-stats"><h4 style="margin:0;">FLEET STATUS</h4><hr style="margin:5px 0; border:0.5px solid #005a9c;"><div style="display:flex; justify-content:space-between; font-size:12px;"><div><b>CF:</b> {counts['Cityflyer']['G']}G|{counts['Cityflyer']['A']}A|{counts['Cityflyer']['R']}R</div><div><b>EF:</b> {counts['Euroflyer']['G']}G|{counts['Euroflyer']['A']}A|{counts['Euroflyer']['R']}R</div></div></div>""", unsafe_allow_html=True)
    
    # Alerts (Mid Right)
    with st.container():
        st.markdown('<div class="floating-alerts">', unsafe_allow_html=True)
        st.write("⚠️ LIVE ALERTS")
        for iata, d in active_alerts.items():
            if st.button(f"{iata}: {d['reason']}", key=f"btn_{iata}", type="primary" if d['type'] == "red" else "secondary"):
                st.session_state.investigate_iata = iata
                st.session_state.minimized = False
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# 3. MINIMIZABLE ANALYSIS
if st.session_state.investigate_iata in active_alerts and ui_visible:
    d = active_alerts[st.session_state.investigate_iata]
    
    if st.session_state.minimized:
        if st.button(f"🔼 {st.session_state.investigate_iata} IMPACT DETECTED - CLICK TO EXPAND", key="expand_btn"):
            st.session_state.minimized = False
            st.rerun()
    else:
        st.markdown(f"""
        <div class="floating-analysis">
            <h3 style="margin:0;">{st.session_state.investigate_iata} OPERATIONAL IMPACT</h3>
            <p><b>DETECTION:</b> {d['reason']} alert. Current conditions below fleet operating limits.</p>
            <p><b>CONSEQUENCE:</b> This may cause diversions or ATC slots. Long delays expected to the operation.</p>
            <hr style="border:0.5px solid #ddd;">
            <p style="font-size:11px; font-family:monospace; background:#f4f4f4; padding:8px;"><b>TAF:</b> {d['t']}</p>
        </div>
        """, unsafe_allow_html=True)
        c1, c2 = st.columns([8, 2])
        with c1: 
            if st.button("🔽 MINIMIZE PANEL", key="min_btn"):
                st.session_state.minimized = True
                st.rerun()
        with c2:
            if st.button("✖ CLOSE", key="close_btn"):
                st.session_state.investigate_iata = "None"
                st.rerun()
