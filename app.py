import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC MASTER HUD v35.47", page_icon="✈️")

# 2. ADVANCED CSS: High-Contrast & HD UI
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 18px; border: 2px solid #d6001a; display: flex; justify-content: space-between; font-weight: bold; border-radius: 8px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 420px !important; border-right: 3px solid #d6001a; }
    
    /* NAVY BLUE DROPDOWN FIX */
    div[data-baseweb="select"] > div { background-color: #ffffff !important; border: 2px solid #d6001a !important; }
    div[data-baseweb="select"] * { color: #002366 !important; font-weight: 900 !important; font-size: 1.1rem !important; }
    
    /* HIGH VISIBILITY POPUP */
    .wx-status-header { font-size: 1.8rem !important; font-weight: 900; margin-bottom: 5px; }
    .wx-data-box { font-size: 1.3rem !important; font-family: 'Courier New', monospace; color: #000; background: #e6e6e6; padding: 15px; border-radius: 4px; border: 2px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# 3. FULL 47-STATION OPERATIONAL NETWORK (RAG ENABLED)
stations = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "CFE", "brief": "Steep 5.5 deg approach."},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "EFW", "brief": "Holding likely TIMBA/WILLO."},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "CFE", "brief": "Strong SW winds."},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "CFE", "brief": "Primary Scottish hub."},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "CFE", "brief": "Belfast City Hub."},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "CFE", "brief": "Long taxi polderbaan."},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "CFE", "brief": "Short rwy. High temp perf."},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "EFW", "brief": "Mountainous Cat C."},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "EFW", "brief": "Noise sensitive Shoreline."},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "EFW", "brief": "Summer peak saturation."},
    "IBZ": {"icao": "LEIB", "lat": 38.872, "lon": 1.373, "rwy": 240, "fleet": "EFW", "brief": "Quick turn focus."},
    "AGP": {"icao": "LEMG", "lat": 36.674, "lon": -4.499, "rwy": 130, "fleet": "EFW", "brief": "Levanter winds."},
    "VCE": {"icao": "LIPZ", "lat": 45.505, "lon": 12.351, "rwy": 40, "fleet": "EFW", "brief": "Winter fog LVP area."},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "CFE", "brief": "High volume flow."},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "EFW", "brief": "Med Hub status."},
    "LCA": {"icao": "LCLK", "lat": 34.875, "lon": 33.624, "rwy": 220, "fleet": "EFW", "brief": "Regional EFW anchor."},
    "SZG": {"icao": "LOWS", "lat": 47.794, "lon": 13.004, "rwy": 150, "fleet": "EFW", "brief": "Alps gateway."},
    "GVA": {"icao": "LSGG", "lat": 46.238, "lon": 6.108, "rwy": 220, "fleet": "EFW", "brief": "Business density flow."},
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "fleet": "CFE", "brief": "Precision hub hub."},
    "BER": {"icao": "EDDB", "lat": 52.366, "lon": 13.503, "rwy": 250, "fleet": "CFE", "brief": "Modern CAT III."},
    "FRA": {"icao": "EDDF", "lat": 50.033, "lon": 8.570, "rwy": 250, "fleet": "CFE", "brief": "Ground movement complexity."},
    "LIN": {"icao": "LIML", "lat": 45.445, "lon": 9.276, "rwy": 360, "fleet": "CFE", "brief": "Milan City Hub."},
    "RTM": {"icao": "EHRD", "lat": 51.956, "lon": 4.437, "rwy": 60, "fleet": "CFE", "brief": "High wind exposure."},
    "JER": {"icao": "EGJJ", "lat": 49.207, "lon": -2.195, "rwy": 260, "fleet": "CFE", "brief": "Channel sea fog risk."},
    "BIO": {"icao": "LEBB", "lat": 43.301, "lon": -2.910, "rwy": 300, "fleet": "CFE", "brief": "Basque winds turbulence."},
    "VLC": {"icao": "LEVC", "lat": 39.489, "lon": -0.482, "rwy": 300, "fleet": "EFW", "brief": "Regional alternate."},
    "BCN": {"icao": "LEBL", "lat": 41.297, "lon": 2.078, "rwy": 250, "fleet": "EFW", "brief": "Med dependent flow."},
    "MAD": {"icao": "LEMD", "lat": 40.471, "lon": -3.567, "rwy": 320, "fleet": "EFW", "brief": "High altitude perf check."},
    "PRG": {"icao": "LKPR", "lat": 50.101, "lon": 14.263, "rwy": 240, "fleet": "CFE", "brief": "Central EU gateway."},
    "LYS": {"icao": "LFLL", "lat": 45.726, "lon": 5.091, "rwy": 350, "fleet": "CFE", "brief": "Logistics hub."},
    "BSL": {"icao": "LFSB", "lat": 47.590, "lon": 7.529, "rwy": 150, "fleet": "CFE", "brief": "Tri-border restriction."},
    "HAM": {"icao": "EDDH", "lat": 53.630, "lon": 9.988, "rwy": 230, "fleet": "CFE", "brief": "Northern German node."},
    "ABZ": {"icao": "EGPD", "lat": 57.201, "lon": -2.197, "rwy": 160, "fleet": "CFE", "brief": "Oil sector density."},
    "ORK": {"icao": "EICK", "lat": 51.841, "lon": -8.491, "rwy": 160, "fleet": "CFE", "brief": "Irish south coast."},
    "SNN": {"icao": "EINN", "lat": 52.701, "lon": -8.924, "rwy": 240, "fleet": "CFE", "brief": "Trans-Atlantic divert."},
    "INV": {"icao": "EGPE", "lat": 57.542, "lon": -4.047, "rwy": 230, "fleet": "CFE", "brief": "Highlands logistics."},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "CFE", "brief": "Primary LCY divert."},
    "LHR": {"icao": "EGLL", "lat": 51.470, "lon": -0.454, "rwy": 270, "fleet": "CFE", "brief": "Mainline Hub positioning."},
    "CDG": {"icao": "LFPG", "lat": 49.009, "lon": 2.547, "rwy": 260, "fleet": "CFE", "brief": "Complex ground ops."},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 360, "fleet": "CFE", "brief": "Ski seasonal Cat C."},
    "GIG": {"icao": "SBGL", "lat": -22.81, "lon": -43.25, "rwy": 150, "fleet": "EFW", "brief": "Long-haul regional."},
    "PSA": {"icao": "LIRP", "lat": 43.683, "lon": 10.395, "rwy": 40, "fleet": "CFE", "brief": "Italian seasonal."},
    "VLC": {"icao": "LEVC", "lat": 39.489, "lon": -0.482, "rwy": 300, "fleet": "EFW", "brief": "Spanish Med node."},
    "BDS": {"icao": "LIBR", "lat": 40.657, "lon": 17.946, "rwy": 310, "fleet": "EFW", "brief": "Adriatic seasonal."},
    "SKG": {"icao": "LGTS", "lat": 40.520, "lon": 22.970, "rwy": 340, "fleet": "EFW", "brief": "Greek regional anchor."},
    "HER": {"icao": "LGIR", "lat": 35.339, "lon": 25.180, "rwy": 270, "fleet": "EFW", "brief": "Summer slot saturate."},
    "DBV": {"icao": "LDDU", "lat": 42.561, "lon": 18.268, "rwy": 110, "fleet": "EFW", "brief": "Balkan seasonal hub."}
}

# 4. DATA ENGINE
@st.cache_data(ttl=1800) # Weather Update: 30m
def fetch_wx_status(icao):
    try:
        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        metar = requests.get(url, timeout=3).text.split('\n')[1]
        color = "#008000"; status = "GREEN"
        if any(x in metar for x in ["FG", "TS", "SN", "VV"]): color = "#d6001a"; status = "RED"
        elif any(x in metar for x in ["RA", "BR", "HZ"]): color = "#ffbf00"; status = "AMBER"
        return {"raw": metar, "color": color, "status": status}
    except: return {"raw": "OFFLINE", "color": "gray", "status": "UNKNOWN"}

@st.cache_data(ttl=20) # Aircraft Update: 20s
def fetch_aircraft():
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
                        "call": call, "lat": s[6], "lon": s[5], 
                        "type": f_type, "alt": round((s[7] or 0) * 3.28084), 
                        "hdg": s[10] or 0, "dep": "UKN", "arr": "UKN" # Logic can map these if needed
                    })
    except: pass
    return fleet

# 5. EXECUTION
ac_fleet = fetch_aircraft()
st.markdown(f'<div class="ba-header"><div>BA OCC MASTER HUD | v35.47</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

# 6. SIDEBAR
with st.sidebar:
    st.title("🛡️ STRATEGIC COMMAND")
    if st.button("🔄 MANUAL DATA SYNC"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    active_ids = [p['call'] for p in ac_fleet] if ac_fleet else ["Scanning..."]
    focus = st.selectbox("Watch Flight Callsign:", active_ids)
    
    st.metric("Cityflyer Airborne", len([p for p in ac_fleet if p['type']=="CFE"]))
    st.metric("Euroflyer Airborne", len([p for p in ac_fleet if p['type']=="EFW"]))
    
    st.markdown("---")
    st.markdown("📟 **RAG STATION ALERTS**")
    tabs = st.tabs(["Cityflyer", "Euroflyer", "Briefings"])

# 7. MAP (RAG Logic + Vector HD Glyphs)
m = folium.Map(location=[50.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")

# STATION RENDERING
for iata, info in stations.items():
    wx = fetch_wx_status(info['icao'])
    popup_html = f"""
    <div style="font-family: Arial; width: 450px; color: black;">
        <b style="font-size: 1.4rem;">{iata} - {info['icao']}</b><hr>
        <div class="wx-status-header" style="color: {wx['color']};">STATUS: {wx['status']}</div>
        <p class="wx-data-box">{wx['raw']}</p>
        <div style="margin-top: 10px;"><b>BRIEF:</b> {info['brief']}</div>
    </div>
    """
    folium.CircleMarker(
        [info['lat'], info['lon']], radius=10, color=wx['color'], fill=True,
        popup=folium.Popup(popup_html, max_width=480)
    ).add_to(m)
    
    if wx['status'] != "GREEN":
        with tabs[0 if info['fleet']=="CFE" else 1]:
            st.warning(f"{iata}: {wx['status']}")

# AIRCRAFT RENDERING
for p in ac_fleet:
    p_color = "white" if p['call'] == focus else ("#00bfff" if p['type']=="CFE" else "#ff4500")
    
    # Vector Trail
    hub = [51.505, 0.055] if p['type'] == "CFE" else [51.148, -0.190]
    folium.PolyLine([hub, [p['lat'], p['lon']]], color=p_color, weight=1, opacity=0.3, dash_array='10, 20').add_to(m)
    
    # HD Isolated Plane Icon
    icon_html = f'<div style="transform: rotate({p["hdg"]}deg); font-size: 26px; color: {p_color}; text-shadow: 0 0 5px #000;"><i class="fa fa-plane"></i></div>'
    folium.Marker(
        [p['lat'], p['lon']], icon=folium.DivIcon(html=icon_html),
        tooltip=f"<b>CALLSIGN: {p['call']}</b><br>DEP: {p['dep']} | ARR: {p['arr']}<br>ALT: {p['alt']}ft"
    ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_47_final")
