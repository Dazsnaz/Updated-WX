import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import math
from datetime import datetime, timedelta

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC MASTER HUD", page_icon="✈️")

# 2. LEGACY CSS (v29.2) + UI POLISH
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 3px solid #d6001a; display: flex; justify-content: space-between; font-weight: bold; border-radius: 8px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 420px !important; border-right: 3px solid #d6001a; }
    
    /* NAVY BLUE DROPDOWN FIX */
    div[data-baseweb="select"] > div { background-color: white !important; }
    div[data-baseweb="select"] * { color: #002366 !important; font-weight: 900 !important; }
    
    /* HIGH VISIBILITY POPUP TEXT */
    .wx-status { font-size: 1.4rem !important; font-weight: bold; margin-bottom: 10px; }
    .wx-data { font-size: 1.1rem !important; font-family: 'Courier New', monospace; color: #000; }
    </style>
    """, unsafe_allow_html=True)

# 3. THE DEFINITIVE 47-STATION NETWORK (Hardcoded)
stations = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "CFE", "brief": "Steep 5.5° approach. Divert: STN/SEN."},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "EFW", "brief": "Single runway saturation. Holding likely."},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "CFE", "brief": "Strong SW winds. High terrain N."},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "CFE", "brief": "Primary Scottish divert hub."},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "CFE", "brief": "Belfast City Hub."},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "CFE", "brief": "Primary LCY divert station."},
    "ABZ": {"icao": "EGPD", "lat": 57.201, "lon": -2.197, "rwy": 160, "fleet": "CFE", "brief": "North Sea ops hub."},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "CFE", "brief": "High volume flow."},
    "ORK": {"icao": "EICK", "lat": 51.841, "lon": -8.491, "rwy": 160, "fleet": "CFE", "brief": "Southern Ireland node."},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "CFE", "brief": "Taxi times high. Slot sensitive."},
    "RTM": {"icao": "EHRD", "lat": 51.956, "lon": 4.437, "rwy": 60, "fleet": "CFE", "brief": "Coastal wind exposure."},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "CFE", "brief": "Performance critical. Short rwy."},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "EFW", "brief": "Cat C Special. Mountainous."},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "EFW", "brief": "Noise sensitive Shoreline approach."},
    "IBZ": {"icao": "LEIB", "lat": 38.872, "lon": 1.373, "rwy": 240, "fleet": "EFW", "brief": "Seasonal peak saturation."},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "EFW", "brief": "Major leisure hub flow."},
    "FAO": {"icao": "LPFR", "lat": 37.014, "lon": -7.965, "rwy": 100, "fleet": "EFW", "brief": "Bird strike risk area."},
    "AGP": {"icao": "LEMG", "lat": 36.674, "lon": -4.499, "rwy": 130, "fleet": "EFW", "brief": "Dual rwy. Levanter winds."},
    "BCN": {"icao": "LEBL", "lat": 41.297, "lon": 2.078, "rwy": 250, "fleet": "EFW", "brief": "Sea breeze influence."},
    "MAD": {"icao": "LEMD", "lat": 40.471, "lon": -3.567, "rwy": 320, "fleet": "EFW", "brief": "High altitude performance hub."},
    "VCE": {"icao": "LIPZ", "lat": 45.505, "lon": 12.351, "rwy": 40, "fleet": "EFW", "brief": "Winter fog LVP area."},
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "fleet": "CFE", "brief": "Precision Hub."},
    "GVA": {"icao": "LSGG", "lat": 46.238, "lon": 6.108, "rwy": 220, "fleet": "EFW", "brief": "Lake Geneva winds."},
    "LIN": {"icao": "LIML", "lat": 45.445, "lon": 9.276, "rwy": 360, "fleet": "CFE", "brief": "Milan City Hub."},
    "PRG": {"icao": "LKPR", "lat": 50.101, "lon": 14.263, "rwy": 240, "fleet": "CFE", "brief": "Central EU Hub."},
    "BER": {"icao": "EDDB", "lat": 52.366, "lon": 13.503, "rwy": 250, "fleet": "CFE", "brief": "Berlin Gateway."},
    "FRA": {"icao": "EDDF", "lat": 50.033, "lon": 8.570, "rwy": 250, "fleet": "CFE", "brief": "Global Hub density."},
    "MUC": {"icao": "EDDM", "lat": 48.353, "lon": 11.786, "rwy": 260, "fleet": "CFE", "brief": "De-icing priority."},
    "CDG": {"icao": "LFPG", "lat": 49.009, "lon": 2.547, "rwy": 260, "fleet": "CFE", "brief": "Major Hub complexity."},
    "JER": {"icao": "EGJJ", "lat": 49.207, "lon": -2.195, "rwy": 260, "fleet": "CFE", "brief": "Channel Fog risk."},
    "GIG": {"icao": "SBGL", "lat": -22.81, "lon": -43.25, "rwy": 150, "fleet": "EFW", "brief": "Intl Seasonal."},
    "SZG": {"icao": "LOWS", "lat": 47.794, "lon": 13.004, "rwy": 150, "fleet": "EFW", "brief": "Ski Hub."},
    "BIO": {"icao": "LEBB", "lat": 43.301, "lon": -2.910, "rwy": 300, "fleet": "CFE", "brief": "Basque winds."},
    "VLC": {"icao": "LEVC", "lat": 39.489, "lon": -0.482, "rwy": 300, "fleet": "EFW", "brief": "Med Alternate."},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 360, "fleet": "CFE", "brief": "Cat C Special."},
    "DUS": {"icao": "EDDL", "lat": 51.289, "lon": 6.766, "rwy": 230, "fleet": "CFE", "brief": "German Regional."},
    "BSL": {"icao": "LFSB", "lat": 47.590, "lon": 7.529, "rwy": 150, "fleet": "CFE", "brief": "Border Hub."},
    "HAM": {"icao": "EDDH", "lat": 53.630, "lon": 9.988, "rwy": 230, "fleet": "CFE", "brief": "Northern Hub."},
    "LHR": {"icao": "EGLL", "lat": 51.470, "lon": -0.454, "rwy": 270, "fleet": "CFE", "brief": "Base Ops."},
    "BFS": {"icao": "EGAA", "lat": 54.657, "lon": -6.215, "rwy": 250, "fleet": "CFE", "brief": "Intl Alternate."},
    "LYS": {"icao": "LFLL", "lat": 45.726, "lon": 5.091, "rwy": 350, "fleet": "CFE", "brief": "Lyon Logistics."},
    "SOU": {"icao": "EGHI", "lat": 50.950, "lon": -1.356, "rwy": 20, "fleet": "CFE", "brief": "Regional S."},
    "EXT": {"icao": "EGTE", "lat": 50.734, "lon": -3.413, "rwy": 260, "fleet": "CFE", "brief": "Regional SW."},
    "LBA": {"icao": "EGNM", "lat": 53.865, "lon": -1.660, "rwy": 320, "fleet": "CFE", "brief": "North Regional."},
    "MAN": {"icao": "EGCC", "lat": 53.353, "lon": -2.274, "rwy": 230, "fleet": "CFE", "brief": "Major Alternate."},
    "PSA": {"icao": "LIRP", "lat": 43.683, "lon": 10.395, "rwy": 40, "fleet": "CFE", "brief": "Italian Seasonal."},
    "FUE": {"icao": "GCFV", "lat": 28.452, "lon": -13.863, "rwy": 10, "fleet": "EFW", "brief": "Canary Flow."}
}

# 4. DATA ENGINES
@st.cache_data(ttl=600)
def fetch_wx_master(icao):
    try:
        m_url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        t_url = f"https://tgftp.nws.noaa.gov/data/forecasts/taf/stations/{icao}.TXT"
        metar = requests.get(m_url, timeout=3).text.split('\n')[1]
        taf = requests.get(t_url, timeout=3).text.split('\n')[1]
        return metar, taf
    except: return "WEATHER DATA OFFLINE", "TAF UNAVAILABLE"

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
                    # Logic to convert ATC Callsign to Flight Number (Example: CFE12A -> BA8451)
                    # For visualization, we will display the commercial ID
                    flight_num = call.replace("CFE", "BA").replace("EFW", "BA")
                    fleet.append({
                        "callsign": call, "flight": flight_num, "lat": s[6], "lon": s[5], 
                        "type": f_type, "alt": round((s[7] or 0) * 3.28084), "hdg": s[10] or 0
                    })
    except: pass
    return fleet

# 5. EXECUTION
fleet_data = fetch_fleet()
st.markdown(f'<div class="ba-header"><div>BA OCC MASTER HUD v35.43</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

# 6. SIDEBAR
with st.sidebar:
    st.title("🛡️ STRATEGIC COMMAND")
    if st.button("🔄 REFRESH DATA"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    # DROPDOWN: Navy Font
    fleet_ids = [p['flight'] for p in fleet_data] if fleet_data else ["Scanning..."]
    focus = st.selectbox("Select BA Flight Number:", fleet_ids)
    
    st.markdown("---")
    st.metric("Cityflyer (CFE)", len([p for p in fleet_data if p['type']=="CFE"]))
    st.metric("Euroflyer (EFW)", len([p for p in fleet_data if p['type']=="EFW"]))
    
# 7. MAP RENDER
m = folium.Map(location=[50.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")

# STATION RENDER
for iata, info in stations.items():
    metar, taf = fetch_wx_master(info['icao'])
    color = "blue" if info['fleet'] == "CFE" else "red"
    
    popup_html = f"""
    <div style="font-family: Arial; width: 400px; color: black;">
        <b style="font-size: 1.2rem;">{iata} - {info['icao']}</b><hr>
        <div class="wx-status" style="color: {'red' if 'FG' in metar or 'TS' in metar else 'green'};">STATUS: {'ALERT' if 'FG' in metar or 'TS' in metar else 'NORMAL'}</div>
        <b>METAR (LIVE):</b><br><p class="wx-data">{metar}</p>
        <b>TAF (FORECAST):</b><br><p class="wx-data">{taf}</p>
        <br><b>STRATEGY BRIEF:</b><br>{info['brief']}
    </div>
    """
    folium.CircleMarker(
        [info['lat'], info['lon']], radius=10, color=color, fill=True,
        popup=folium.Popup(popup_html, max_width=450)
    ).add_to(m)

# AIRCRAFT RENDER (PLANE GLYPHS + DEPARTURE TRACKS)
for p in fleet_data:
    p_color = "white" if p['flight'] == focus else ("#00bfff" if p['type']=="CFE" else "#ff4500")
    
    # 1. ADD TRACK (Dashed line from Hub)
    hub_pos = [51.505, 0.055] if p['type'] == "CFE" else [51.148, -0.190]
    folium.PolyLine(
        [hub_pos, [p['lat'], p['lon']]], 
        color=p_color, weight=1, opacity=0.5, dash_array='5, 10'
    ).add_to(m)
    
    # 2. ADD ROTATING PLANE ICON
    icon_html = f'<div style="transform: rotate({p["hdg"]}deg); font-size: 24px; color: {p_color};"><i class="fa fa-plane"></i></div>'
    folium.Marker(
        [p['lat'], p['lon']], 
        icon=folium.DivIcon(html=icon_html),
        tooltip=f"FLIGHT: {p['flight']} (ATC: {p['callsign']}) | ALT: {p['alt']}ft"
    ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_43_final")
