import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC MASTER HUD", page_icon="✈️")

# 2. LEGACY CSS & HIGH-VISIBILITY UI
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 3px solid #d6001a; display: flex; justify-content: space-between; font-weight: bold; border-radius: 8px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 420px !important; border-right: 3px solid #d6001a; }
    
    /* NAVY BLUE DROPDOWN FIX */
    div[data-baseweb="select"] > div { background-color: white !important; }
    div[data-baseweb="select"] * { color: #002366 !important; font-weight: 900 !important; }
    
    /* HIGH VISIBILITY POPUP */
    .wx-status { font-size: 1.6rem !important; font-weight: 800; margin-bottom: 12px; }
    .wx-data { font-size: 1.3rem !important; font-family: 'Courier New', monospace; color: #000; background: #f0f0f0; padding: 10px; border-radius: 5px; line-height: 1.4; }
    .brief-text { font-size: 1.1rem; color: #333; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 3. THE 47-STATION OPERATIONAL NETWORK
stations = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "CFE", "brief": "Steep 5.5° approach. Divert: STN/SEN."},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "EFW", "brief": "Single runway saturation. Holding likely."},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "CFE", "brief": "Strong SW winds. High terrain N."},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "CFE", "brief": "Primary Scottish divert hub."},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "CFE", "brief": "Belfast City Hub."},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "CFE", "brief": "Primary LCY divert station."},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "CFE", "brief": "Taxi times high. Slot sensitive."},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "CFE", "brief": "Perf limited. Short rwy. Seasonal winds."},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "EFW", "brief": "Cat C Special. Mountainous terrain."},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "EFW", "brief": "Noise sensitive Shoreline approach."},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "EFW", "brief": "Summer peak saturation."},
    "IBZ": {"icao": "LEIB", "lat": 38.872, "lon": 1.373, "rwy": 240, "fleet": "EFW", "brief": "Quick turn focus."},
    "FAO": {"icao": "LPFR", "lat": 37.014, "lon": -7.965, "rwy": 100, "fleet": "EFW", "brief": "Bird strike risk area."},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "EFW", "brief": "Med Hub status."},
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "fleet": "CFE", "brief": "Precision Hub flow."},
    "BER": {"icao": "EDDB", "lat": 52.366, "lon": 13.503, "rwy": 250, "fleet": "CFE", "brief": "Modern CAT III facility."},
    "FRA": {"icao": "EDDF", "lat": 50.033, "lon": 8.570, "rwy": 250, "fleet": "CFE", "brief": "Complexity high density."},
    "LIN": {"icao": "LIML", "lat": 45.445, "lon": 9.276, "rwy": 360, "fleet": "CFE", "brief": "Milan City Hub."},
    "JER": {"icao": "EGJJ", "lat": 49.207, "lon": -2.195, "rwy": 260, "fleet": "CFE", "brief": "Channel Fog risk."},
    "SZG": {"icao": "LOWS", "lat": 47.794, "lon": 13.004, "rwy": 150, "fleet": "EFW", "brief": "Alps winter node."},
    "BIO": {"icao": "LEBB", "lat": 43.301, "lon": -2.910, "rwy": 300, "fleet": "CFE", "brief": "Basque winds."},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 360, "fleet": "CFE", "brief": "Cat C Seasonal."},
    "LHR": {"icao": "EGLL", "lat": 51.470, "lon": -0.454, "rwy": 270, "fleet": "CFE", "brief": "LHR Mainline Hub."},
    "MAN": {"icao": "EGCC", "lat": 53.353, "lon": -2.274, "rwy": 230, "fleet": "CFE", "brief": "North Alternate."},
    # Mapping for all 47 stations logic...
}

# 4. CALLSIGN TRANSLATOR (CFE/EFW -> BA)
callsign_to_ba = {
    "CFE74H": "BA8715",
    "CFE74R": "BA8716",
    "CFE12A": "BA8450",
    "EFW22B": "BA2650"
}

def translate_flight(call):
    return callsign_to_ba.get(call, call.replace("CFE", "BA").replace("EFW", "BA"))

# 5. DATA ENGINES
@st.cache_data(ttl=600)
def fetch_wx_heavy(icao):
    try:
        m_url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        t_url = f"https://tgftp.nws.noaa.gov/data/forecasts/taf/stations/{icao}.TXT"
        metar = requests.get(m_url, timeout=3).text.split('\n')[1]
        taf = requests.get(t_url, timeout=3).text.split('\n')[1]
        return metar, taf
    except: return "DATA LINK OFFLINE", "FORECAST UNAVAILABLE"

@st.cache_data(ttl=30)
def fetch_fleet():
    fleet = []
    try:
        url = "https://opensky-network.org/api/states/all?lamin=30.0&lomin=-20.0&lamax=65.0&lomax=30.0"
        data = requests.get(url, timeout=5).json()
        if "states" in data and data["states"]:
            for s in data["states"]:
                call = (s[1] or "").strip().upper()
                f_type = "CFE" if call.startswith("CFE") else ("EFW" if call.startswith("EFW") else None)
                if f_type:
                    fleet.append({
                        "callsign": call, "flight": translate_flight(call),
                        "lat": s[6], "lon": s[5], "type": f_type, 
                        "alt": round((s[7] or 0) * 3.28084), "hdg": s[10] or 0,
                        "origin": "LCY" if f_type == "CFE" else "LGW",
                        "dest": "EN ROUTE" # Placeholder for dynamic route mapping
                    })
    except: pass
    return fleet

# 6. EXECUTION
fleet_data = fetch_fleet()
st.markdown(f'<div class="ba-header"><div>BA OCC MASTER HUD v35.44</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

# 7. SIDEBAR
with st.sidebar:
    st.title("🛡️ STRATEGIC COMMAND")
    if st.button("🔄 REFRESH FEED"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    flight_nums = [p['flight'] for p in fleet_data] if fleet_data else ["Scanning..."]
    focus = st.selectbox("Watch Flight Number:", flight_nums)
    
    st.markdown("---")
    st.metric("Cityflyer Airborne", len([p for p in fleet_data if p['type']=="CFE"]))
    st.metric("Euroflyer Airborne", len([p for p in fleet_data if p['type']=="EFW"]))

# 8. MAP RENDER
m = folium.Map(location=[50.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")

# STATION RENDER (High-Vis Weather)
for iata, info in stations.items():
    metar, taf = fetch_wx_heavy(info['icao'])
    color = "blue" if info['fleet'] == "CFE" else "red"
    
    popup_html = f"""
    <div style="font-family: Arial; width: 450px; color: black;">
        <b style="font-size: 1.4rem;">{iata} - {info['icao']}</b><hr>
        <div class="wx-status">METAR (LIVE)</div>
        <p class="wx-data">{metar}</p>
        <div class="wx-status">TAF (FORECAST)</div>
        <p class="wx-data">{taf}</p>
        <div class="brief-text"><b>STRATEGY:</b> {info['brief']}</div>
    </div>
    """
    folium.CircleMarker(
        [info['lat'], info['lon']], radius=10, color=color, fill=True,
        popup=folium.Popup(popup_html, max_width=500)
    ).add_to(m)

# AIRCRAFT RENDER (GLYPHS + ROUTE TRACKS)
for p in fleet_data:
    p_color = "white" if p['flight'] == focus else ("#00bfff" if p['type']=="CFE" else "#ff4500")
    
    # 1. ADD TRACK LINE (Departure Path)
    hub_pos = [51.505, 0.055] if p['type'] == "CFE" else [51.148, -0.190]
    folium.PolyLine([hub_pos, [p['lat'], p['lon']]], color=p_color, weight=1, opacity=0.4, dash_array='10, 20').add_to(m)
    
    # 2. ADD ROTATING PLANE GLYPH
    icon_html = f'<div style="transform: rotate({p["hdg"]}deg); font-size: 26px; color: {p_color};"><i class="fa fa-plane"></i></div>'
    folium.Marker(
        [p['lat'], p['lon']], 
        icon=folium.DivIcon(html=icon_html),
        tooltip=f"<b>{p['flight']}</b><br>FROM: {p['origin']}<br>TO: {p['dest']}<br>ALT: {p['alt']}ft"
    ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_44_final")
