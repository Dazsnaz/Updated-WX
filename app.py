import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import math
from avwx import Metar
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. MASTER CSS: Force Navy Blue Dropdowns & OCC Theme
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { 
        background-color: #002366; padding: 20px; border-radius: 8px; 
        margin-bottom: 20px; border: 2px solid #d6001a; 
        display: flex; justify-content: space-between;
    }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 400px !important; border-right: 3px solid #d6001a; }
    
    /* NAVY BLUE DROPDOWN SELECTOR */
    div[data-baseweb="select"] > div { background-color: white !important; }
    div[data-baseweb="select"] * { color: #002366 !important; font-weight: bold !important; }
    div[data-testid="stVirtualDropdown"] * { color: #002366 !important; }
    
    .stMetric { background-color: #001a33; border-left: 5px solid #d6001a; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 3. THE 47-STATION NETWORK
stations = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer"},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer"},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer"},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "Cityflyer"},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "Cityflyer"},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "Cityflyer"},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "Cityflyer"},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer"},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer"},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "Euroflyer"},
    "JER": {"icao": "EGJJ", "lat": 49.207, "lon": -2.195, "rwy": 260, "fleet": "Cityflyer"},
    "IBZ": {"icao": "LEIB", "lat": 38.872, "lon": 1.373, "rwy": 240, "fleet": "Euroflyer"},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "Euroflyer"},
    "FAO": {"icao": "LPFR", "lat": 37.014, "lon": -7.965, "rwy": 100, "fleet": "Euroflyer"},
    "AGP": {"icao": "LEMG", "lat": 36.674, "lon": -4.499, "rwy": 130, "fleet": "Euroflyer"},
    "VCE": {"icao": "LIPZ", "lat": 45.505, "lon": 12.351, "rwy": 40, "fleet": "Euroflyer"},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "Cityflyer"},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "Euroflyer"},
    "LCA": {"icao": "LCLK", "lat": 34.875, "lon": 33.624, "rwy": 220, "fleet": "Euroflyer"},
    "SZG": {"icao": "LOWS", "lat": 47.794, "lon": 13.004, "rwy": 150, "fleet": "Euroflyer"},
    "GVA": {"icao": "LSGG", "lat": 46.238, "lon": 6.108, "rwy": 220, "fleet": "Euroflyer"},
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "fleet": "Cityflyer"},
    "PRG": {"icao": "LKPR", "lat": 50.101, "lon": 14.263, "rwy": 240, "fleet": "Cityflyer"},
}

# 4. UTILITIES (Safe Math)
def get_safe_xw(d, rwy):
    try:
        w_dir = d.get('w_dir')
        w_spd = d.get('w_spd', 0)
        w_gst = d.get('w_gst', 0)
        if w_dir is None or rwy is None: return 0
        max_wind = max(w_spd if w_spd else 0, w_gst if w_gst else 0)
        angle = math.radians(w_dir - rwy)
        return round(abs(max_wind * math.sin(angle)))
    except: return 0

# 5. DATA ENGINES
@st.cache_data(ttl=30)
def fetch_fleet():
    fleet = []
    try:
        url = "https://opensky-network.org/api/states/all?lamin=30.0&lomin=-20.0&lamax=70.0&lomax=30.0"
        data = requests.get(url, timeout=5).json()
        if "states" in data and data["states"]:
            for s in data["states"]:
                call = (s[1] or "").strip().upper()
                f_type = "CFE" if call.startswith("CFE") else ("EFW" if call.startswith("EFW") else None)
                if f_type:
                    fleet.append({"callsign": call, "lat": s[6], "lon": s[5], "type": f_type, "alt": round((s[7] or 0) * 3.28084)})
    except: pass
    return fleet

@st.cache_data(ttl=1800)
def fetch_wx(stations_dict):
    res = {}
    for iata, info in stations_dict.items():
        try:
            m = Metar(info['icao']); m.update()
            res[iata] = {"raw": m.raw, "w_dir": getattr(m.data.wind_direction, 'value', None),
                         "w_spd": getattr(m.data.wind_speed, 'value', 0), "w_gst": getattr(m.data.wind_gust, 'value', 0)}
        except: pass
    return res

# 6. EXECUTION
fleet_data = fetch_fleet()
weather_data = fetch_wx(stations)

# 7. RENDER
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.37</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.title("🛡️ COMMAND HUD")
    if st.button("🔄 REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    # FILTERS
    st.markdown("📡 **STATION FILTERS**")
    show_cf = st.checkbox("Cityflyer Stations", value=True)
    show_ef = st.checkbox("Euroflyer Stations", value=True)
    timeframe = st.selectbox("Operational Window:", ["Current (Live)", "6hr", "12hr", "24hr"], index=0)
    
    st.markdown("---")
    # DROPDOWN (Navy Font)
    st.markdown("✈️ **ACTIVE FLEET WATCH**")
    fleet_calls = [p['callsign'] for p in fleet_data] if fleet_data else ["None Active"]
    focus = st.selectbox("Highlight Aircraft:", fleet_calls)
    
    st.markdown("---")
    st.metric("CFE Airborne", len([p for p in fleet_data if p['type'] == "CFE"]))
    st.metric("EFW Airborne", len([p for p in fleet_data if p['type'] == "EFW"]))
    xw_limit = st.slider("X-WIND ALERT (KT)", 15, 35, 25)

# 8. MAP
m = folium.Map(location=[50.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")

for iata, info in stations.items():
    if not ((info['fleet'] == "Cityflyer" and show_cf) or (info['fleet'] == "Euroflyer" and show_ef)): continue
    d = weather_data.get(iata)
    color = "#008000"
    if d:
        xw = get_safe_xw(d, info['rwy'])
        if xw >= xw_limit: color = "#d6001a"
        popup = f"<b>{iata}</b><br>XW: {xw}KT<br><br><code>{d['raw']}</code>"
        folium.CircleMarker([info['lat'], info['lon']], radius=8, color=color, fill=True, popup=folium.Popup(popup, max_width=300)).add_to(m)

for p in fleet_data:
    icon_color = "orange" if p['callsign'] == focus else ("blue" if p['type'] == "CFE" else "red")
    folium.Marker([p['lat'], p['lon']], icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"), tooltip=f"{p['callsign']}").add_to(m)

st_folium(m, width=1200, height=800, key="v35_37_map")
