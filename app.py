import streamlit as st
import folium
from streamlit_folium import st_folium
from avwx import Metar, Taf
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC HUD", page_icon="✈️")

# 2. LAYERED UI STYLING
st.markdown("""
    <style>
    .main .block-container { padding: 0; max-width: 100%; }
    html, body, [class*="st-"], div, p, h1, h2, h3, h4, label { color: white !important; }
    [data-testid="stSidebar"] { background-color: #002366 !important; }

    /* FLOATING DASHBOARD */
    .floating-stats {
        position: absolute; top: 10px; left: 60px; z-index: 1000;
        background: rgba(0, 35, 102, 0.8); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; min-width: 350px;
    }
    
    /* FLOATING ALERTS */
    .floating-alerts {
        position: absolute; top: 10px; right: 20px; z-index: 1000;
        background: rgba(0, 35, 102, 0.8); padding: 15px; border-radius: 8px;
        border: 1px solid #005a9c; width: 300px; max-height: 70vh; overflow-y: auto;
    }

    /* BOTTOM ANALYSIS */
    .floating-analysis {
        position: absolute; bottom: 40px; left: 50%; transform: translateX(-50%);
        z-index: 1001; background: rgba(255, 255, 255, 0.95); padding: 20px; 
        border-radius: 8px; width: 80%; max-width: 900px; 
        border-top: 10px solid #002366; color: #002366 !important;
    }
    .floating-analysis * { color: #002366 !important; }

    div.stButton > button[kind="primary"] { background-color: #d6001a !important; color: white !important; font-weight: bold; width: 100%; }
    div.stButton > button[kind="secondary"] { background-color: #eb8f34 !important; color: white !important; font-weight: bold; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# 3. COMPLETE 42 AIRPORT DATABASE
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
def get_fleet_weather(airport_dict):
    results = {}
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
            results[iata] = {"vis": v, "w_dir": m.data.wind_direction.value if m.data.wind_direction else 0, "w_spd": m.data.wind_speed.value if m.data.wind_speed else 0, "ceiling": c, "raw_metar": m.raw, "raw_taf": t.raw}
        except: continue
    return results

weather_data = get_fleet_weather(airports)

# SIDEBAR
st.sidebar.title("🔧 OCC HUD Settings")
ui_visible = st.sidebar.checkbox("Show HUD Elements", value=True)
search_iata = st.sidebar.text_input("IATA Search", "").upper()
fleet_filter = st.sidebar.multiselect("Active Fleet", ["Cityflyer", "Euroflyer"], default=["Cityflyer", "Euroflyer"])

if st.sidebar.button("🔄 Force Refresh"):
    st.cache_data.clear()
    st.rerun()

if 'investigate_iata' not in st.session_state: st.session_state.investigate_iata = "None"
if search_iata in airports: st.session_state.investigate_iata = search_iata

# PROCESS ALERTS
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
        elif xw > 18 or data['vis'] < 1500 or data['ceiling'] < 500:
            alert_type = "amber"; reason = "MARGINAL"
            
        if alert_type:
            active_alerts[iata] = {"type": alert_type, "reason": reason, "vis": data['vis'], "ceiling": data['ceiling'], "xw": xw, "metar": data['raw_metar'], "taf": data['raw_taf']}
            color = "#d6001a" if alert_type == "red" else "#eb8f34"
            counts[info['fleet']]["red" if alert_type=="red" else "orange"] += 1
        else: counts[info['fleet']]["green"] += 1
        map_markers.append({"iata": iata, "lat": info['lat'], "lon": info['lon'], "color": color, "metar": data['raw_metar'], "taf": data['raw_taf']})

# 1. FULLSCREEN MAP
map_center = [48.0, 5.0]; zoom = 5
if st.session_state.investigate_iata in airports:
    target = airports[st.session_state.investigate_iata]
    map_center = [target["lat"], target["lon"]]; zoom = 10

m = folium.Map(location=map_center, zoom_start=zoom, tiles="CartoDB dark_matter", zoom_control=False)
for mkr in map_markers:
    popup_html = f"""<div style="width:400px; color:black;"><b>METAR:</b> {mkr['metar']}<br><br><b>TAF:</b> {mkr['taf']}</div>"""
    folium.CircleMarker(location=[mkr['lat'], mkr['lon']], radius=10 if mkr['iata'] == st.session_state.investigate_iata else 6, color=mkr['color'], fill=True, fill_opacity=0.8, popup=folium.Popup(popup_html, max_width=450)).add_to(m)

st_folium(m, width=2200, height=1000, key="fullscreen_occ")

# 2. FLOATING UI
if ui_visible:
    st.markdown(f"""<div class="floating-stats"><h4 style="margin:0;">BA OCC FLEET STATUS</h4><hr style="margin:5px 0;"><div style="display:flex; justify-content:space-between;"><div><b>CF:</b> {counts['Cityflyer']['green']}G | {counts['Cityflyer']['orange']}A | {counts['Cityflyer']['red']}R</div><div><b>EF:</b> {counts['Euroflyer']['green']}G | {counts['Euroflyer']['orange']}A | {counts['Euroflyer']['red']}R</div></div></div>""", unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="floating-alerts">', unsafe_allow_html=True)
        st.write("⚠️ LIVE ALERTS")
        for iata, d in active_alerts.items():
            if st.button(f"{iata}: {d['reason']}", key=f"btn_{iata}", type="primary" if d['type'] == "red" else "secondary"):
                st.session_state.investigate_iata = iata
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# 3. ANALYSIS OVERLAY
if st.session_state.investigate_iata in active_alerts and ui_visible:
    d = active_alerts[st.session_state.investigate_iata]
    st.markdown(f"""<div class="floating-analysis"><h3>{st.session_state.investigate_iata} Impact Deep-Dive</h3><p><b>Issue:</b> {d['reason']} detected. Conditions currently below operating limits.</p><p><b>Impact:</b> This may cause diversions or ATC slots. Long delays expected to the operation.</p><hr><p style="font-size:12px;"><b>Full TAF:</b> {d['taf']}</p></div>""", unsafe_allow_html=True)
    if st.button("Close Analysis"):
        st.session_state.investigate_iata = "None"; st.rerun()
