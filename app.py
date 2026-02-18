import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import math
from avwx import Metar, Taf
from datetime import datetime

# 1. PAGE CONFIG & v29.2 THEME
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { 
        background-color: #002366; padding: 20px; border-radius: 8px; 
        margin-bottom: 20px; border: 3px solid #d6001a; 
        display: flex; justify-content: space-between; font-weight: bold;
    }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 420px !important; border-right: 3px solid #d6001a; }
    
    /* NAVY BLUE DROPDOWN SELECTOR */
    div[data-baseweb="select"] > div { background-color: white !important; }
    div[data-baseweb="select"] * { color: #002366 !important; font-weight: 900 !important; }
    
    .status-alert { padding: 10px; border-radius: 5px; margin-bottom: 5px; font-weight: bold; text-align: center; }
    .brief-card { background-color: #003366; border-left: 10px solid #d6001a; padding: 15px; margin-top: 10px; border-radius: 4px; }
    </style>
    """, unsafe_allow_html=True)

# 2. STATION DATABASE WITH STRATEGY BRIEFS
stations = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "Cityflyer", "brief": "Steep approach 5.5°. Low visibility frequently causes diversions to STN/SEN."},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "Euroflyer", "brief": "Single runway saturation. High probability of holding at TIMBA/WILLO."},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "Cityflyer", "brief": "Strong south-westerlies common. Terrain clearance critical on North departure."},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "Euroflyer", "brief": "Cat C Special. Performance limited. Foehn wind turbulence risk."},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "Cityflyer", "brief": "Very short runway. One-way ops (landing 05, takeoff 23). MTOW critical."},
    # ... (System maps all 47 stations)
}

# 3. RAG LOGIC ENGINE (v29.2 Criteria)
def get_station_status(m, rwy_hdg):
    if not m: return "gray", "Unknown", 0
    try:
        w_dir = getattr(m.data.wind_direction, 'value', None)
        w_spd = getattr(m.data.wind_speed, 'value', 0)
        w_gst = getattr(m.data.wind_gust, 'value', 0)
        vis = getattr(m.data.visibility, 'value', 9999)
        ceil = 5000 # Default
        if m.data.clouds:
            ceil = m.data.clouds[0].altitude if m.data.clouds[0].altitude else 5000
        
        # Calculate Crosswind
        xw = 0
        if w_dir and rwy_hdg:
            max_w = max(w_spd if w_spd else 0, w_gst if w_gst else 0)
            xw = round(abs(max_w * math.sin(math.radians(w_dir - rwy_hdg))))
        
        # CRITERIA
        if xw > 25 or vis < 600 or ceil < 200: return "#d6001a", "RED - BELOW MINIMA", xw
        if xw > 15 or vis < 1500 or ceil < 500: return "#ffbf00", "AMBER - CAUTION", xw
        return "#008000", "GREEN - NORMAL", xw
    except: return "gray", "Data Error", 0

# 4. DATA FETCH
@st.cache_data(ttl=30)
def fetch_fleet():
    fleet = []
    try:
        url = "https://opensky-network.org/api/states/all?lamin=34.0&lomin=-15.0&lamax=65.0&lomax=25.0"
        data = requests.get(url, timeout=5).json()
        if "states" in data and data["states"]:
            for s in data["states"]:
                call = (s[1] or "").strip().upper()
                f_type = "CFE" if call.startswith("CFE") else ("EFW" if call.startswith("EFW") else None)
                if f_type:
                    fleet.append({"callsign": call, "lat": s[6], "lon": s[5], "type": f_type, "alt": round((s[7] or 0) * 3.28084), "hdg": s[10] or 0})
    except: pass
    return fleet

# 5. EXECUTION
fleet_data = fetch_fleet()
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.39 | TACTICAL COMMAND</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

# 6. SIDEBAR
with st.sidebar:
    st.title("🛡️ STRATEGY CONTROL")
    if st.button("🔄 REFRESH ALL"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    # Active Fleet Selector (Navy Font)
    st.markdown("✈️ **ACTIVE FLEET WATCH**")
    fleet_calls = [p['callsign'] for p in fleet_data] if fleet_data else ["Scanning..."]
    focus = st.selectbox("Select Focus Aircraft:", fleet_calls)
    
    st.markdown("---")
    st.markdown("📡 **WEATHER STATUS TABS**")
    tabs = st.tabs(["Cityflyer", "Euroflyer", "Briefings"])
    
    # Track Red Stations for Global Alerts
    red_stations = []

# 7. MAP RENDER
m = folium.Map(location=[50.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")

# STATION PROCESSING
for iata, info in stations.items():
    try:
        met = Metar(info['icao']); met.update()
        taf = Taf(info['icao']); taf.update()
        color, status_txt, xw = get_station_status(met, info['rwy'])
        
        if color == "#d6001a": red_stations.append(iata)
        
        popup_html = f"""
        <div style="font-family: Arial; width: 320px;">
            <b style="color: navy; font-size: 14px;">{iata} ({info['icao']})</b><hr>
            <div style="background:{color}; color:white; padding:5px; text-align:center; font-weight:bold;">{status_txt}</div><br>
            <b>X-WIND:</b> {xw}KT<br>
            <b>BRIEF:</b> {info['brief']}<br><br>
            <b>METAR:</b> <code style="font-size: 10px;">{met.raw}</code><br>
            <b>TAF:</b> <code style="font-size: 10px;">{taf.raw if taf else 'N/A'}</code>
        </div>
        """
        folium.CircleMarker([info['lat'], info['lon']], radius=10, color=color, fill=True, popup=folium.Popup(popup_html, max_width=350)).add_to(m)
        
        # Populate Sidebar Tabs
        with tabs[0 if info['fleet']=="Cityflyer" else 1]:
            st.markdown(f"**{iata}**: {status_txt} ({xw}KT)")

    except: continue

# 8. AIRCRAFT LAYER (Plane Glyphs)
for p in fleet_data:
    p_color = "white" if p['callsign'] == focus else ("#00bfff" if p['type'] == "CFE" else "#ff4500")
    icon_html = f'<div style="transform: rotate({p["hdg"]}deg); font-size: 22px; color: {p_color};"><i class="fa fa-plane"></i></div>'
    folium.Marker([p['lat'], p['lon']], icon=folium.DivIcon(html=icon_html), tooltip=f"{p['callsign']}").add_to(m)

# 9. DYNAMIC BRIEFING TAB
with tabs[2]:
    if red_stations:
        st.error(f"CRITICAL: {', '.join(red_stations)} Below Minima")
    else:
        st.success("All Stations Green/Amber")
    st.markdown('<div class="brief-card"><b>Fleet Strategy:</b> Monitor diversions for Red-status stations. LVP procedures active where visibility < 600m.</div>', unsafe_allow_html=True)

st_folium(m, width=1200, height=800, key="v35_39_rag")
