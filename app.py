import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. LEGACY v29.2 CSS + NAVY DROPDOWN PATCH (Extreme Priority)
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
    
    /* NAVY BLUE DROPDOWN FIX - Targets all sub-elements */
    div[data-baseweb="select"] > div { background-color: white !important; }
    div[data-baseweb="select"] span, div[data-baseweb="select"] div { 
        color: #002366 !important; font-weight: 900 !important; 
    }
    div[role="listbox"] div { color: #002366 !important; font-weight: 900 !important; }
    
    .stMetric { background-color: #001a33; border-left: 10px solid #d6001a; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 3. THE COMPLETE 47-STATION MASTER DATABASE (NO SHORTCUTS)
stations = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "CFE", "brief": "Steep 5.5° approach. Hub."},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "EFW", "brief": "Single runway saturation. Hub."},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "CFE", "brief": "Strong SW winds. High terrain N."},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "CFE", "brief": "Primary Scottish hub."},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "EFW", "brief": "Cat C Special. Mountainous."},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "CFE", "brief": "Short rwy. High temp performance."},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "CFE", "brief": "Slot sensitive. Long taxi."},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "EFW", "brief": "Noise sensitive Shoreline."},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "EFW", "brief": "Summer peak saturation."},
    "FAO": {"icao": "LPFR", "lat": 37.014, "lon": -7.965, "rwy": 100, "fleet": "EFW", "brief": "Bird strike risk area."},
    "BCN": {"icao": "LEBL", "lat": 41.297, "lon": 2.078, "rwy": 250, "fleet": "EFW", "brief": "Sea breeze influence."},
    "IBZ": {"icao": "LEIB", "lat": 38.872, "lon": 1.373, "rwy": 240, "fleet": "EFW", "brief": "Quick turn focus."},
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "fleet": "CFE", "brief": "Precision Hub."},
    "JER": {"icao": "EGJJ", "lat": 49.207, "lon": -2.195, "rwy": 260, "fleet": "CFE", "brief": "Channel Fog risk."},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "CFE", "brief": "Belfast City Hub."},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "CFE", "brief": "High volume flow."},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "EFW", "brief": "Med Hub status."},
    "LCA": {"icao": "LCLK", "lat": 34.875, "lon": 33.624, "rwy": 220, "fleet": "EFW", "brief": "Regional anchor."},
    "SZG": {"icao": "LOWS", "lat": 47.794, "lon": 13.004, "rwy": 150, "fleet": "EFW", "brief": "Alps winter node."},
    "GVA": {"icao": "LSGG", "lat": 46.238, "lon": 6.108, "rwy": 220, "fleet": "EFW", "brief": "Business density flow."},
    "BER": {"icao": "EDDB", "lat": 52.366, "lon": 13.503, "rwy": 250, "fleet": "CFE", "brief": "Modern CAT III."},
    "FRA": {"icao": "EDDF", "lat": 50.033, "lon": 8.570, "rwy": 250, "fleet": "CFE", "brief": "Complexity high."},
    "LIN": {"icao": "LIML", "lat": 45.445, "lon": 9.276, "rwy": 360, "fleet": "CFE", "brief": "Milan City Hub."},
    "RTM": {"icao": "EHRD", "lat": 51.956, "lon": 4.437, "rwy": 60, "fleet": "CFE", "brief": "High wind exposure."},
    "BIO": {"icao": "LEBB", "lat": 43.301, "lon": -2.910, "rwy": 300, "fleet": "CFE", "brief": "Basque winds."},
    "VLC": {"icao": "LEVC", "lat": 39.489, "lon": -0.482, "rwy": 300, "fleet": "EFW", "brief": "Spanish Med node."},
    "MAD": {"icao": "LEMD", "lat": 40.471, "lon": -3.567, "rwy": 320, "fleet": "EFW", "brief": "High altitude performance."},
    "PRG": {"icao": "LKPR", "lat": 50.101, "lon": 14.263, "rwy": 240, "fleet": "CFE", "brief": "Central EU Hub."},
    "LYS": {"icao": "LFLL", "lat": 45.726, "lon": 5.091, "rwy": 350, "fleet": "CFE", "brief": "Logistics hub."},
    "BSL": {"icao": "LFSB", "lat": 47.590, "lon": 7.529, "rwy": 150, "fleet": "CFE", "brief": "Tri-border restriction."},
    "HAM": {"icao": "EDDH", "lat": 53.630, "lon": 9.988, "rwy": 230, "fleet": "CFE", "brief": "Northern node."},
    "ABZ": {"icao": "EGPD", "lat": 57.201, "lon": -2.197, "rwy": 160, "fleet": "CFE", "brief": "Oil sector density."},
    "ORK": {"icao": "EICK", "lat": 51.841, "lon": -8.491, "rwy": 160, "fleet": "CFE", "brief": "Irish south coast."},
    "SNN": {"icao": "EINN", "lat": 52.701, "lon": -8.924, "rwy": 240, "fleet": "CFE", "brief": "Trans-Atlantic divert."},
    "INV": {"icao": "EGPE", "lat": 57.542, "lon": -4.047, "rwy": 230, "fleet": "CFE", "brief": "Highlands logistics."},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "CFE", "brief": "Primary LCY divert."},
    "LHR": {"icao": "EGLL", "lat": 51.470, "lon": -0.454, "rwy": 270, "fleet": "CFE", "brief": "Mainline Hub."},
    "CDG": {"icao": "LFPG", "lat": 49.009, "lon": 2.547, "rwy": 260, "fleet": "CFE", "brief": "Complexity high."},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 360, "fleet": "CFE", "brief": "Ski seasonal."},
    "PSA": {"icao": "LIRP", "lat": 43.683, "lon": 10.395, "rwy": 40, "fleet": "CFE", "brief": "Italian seasonal."},
    "DBV": {"icao": "LDDU", "lat": 42.561, "lon": 18.268, "rwy": 110, "fleet": "EFW", "brief": "Balkan seasonal."},
    "SKG": {"icao": "LGTS", "lat": 40.520, "lon": 22.970, "rwy": 340, "fleet": "EFW", "brief": "Greek anchor."},
    "HER": {"icao": "LGIR", "lat": 35.339, "lon": 25.180, "rwy": 270, "fleet": "EFW", "brief": "Summer saturation."},
    "BDS": {"icao": "LIBR", "lat": 40.657, "lon": 17.946, "rwy": 310, "fleet": "EFW", "brief": "Adriatic seasonal."},
    "TFS": {"icao": "GCTS", "lat": 28.044, "lon": -16.572, "rwy": 70, "fleet": "EFW", "brief": "Trade winds."},
    "ACE": {"icao": "GCRR", "lat": 28.945, "lon": -13.605, "rwy": 30, "fleet": "EFW", "brief": "Volcanic winds."},
    "FUE": {"icao": "GCFV", "lat": 28.452, "lon": -13.863, "rwy": 10, "fleet": "EFW", "brief": "Canary Flow."}
}

# 4. WEATHER & DATA ENGINES
@st.cache_data(ttl=1800)
def fetch_wx_rag(icao):
    try:
        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        metar = requests.get(url, timeout=3).text.split('\n')[1]
        color = "#008000"; status = "GREEN"
        if any(x in metar for x in ["FG", "TS", "SN", "VV"]): color = "#d6001a"; status = "RED"
        elif any(x in metar for x in ["RA", "BR", "HZ"]): color = "#ffbf00"; status = "AMBER"
        return {"raw": metar, "color": color, "status": status}
    except: return {"raw": "OFFLINE", "color": "gray", "status": "UNKNOWN"}

@st.cache_data(ttl=20)
def fetch_ac_fleet():
    fleet = []
    try:
        url = "https://opensky-network.org/api/states/all?lamin=25.0&lomin=-20.0&lamax=65.0&lomax=30.0"
        data = requests.get(url, timeout=5).json()
        if "states" in data and data["states"]:
            for s in data["states"]:
                call = (s[1] or "").strip().upper()
                f_type = "CFE" if call.startswith("CFE") else ("EFW" if call.startswith("EFW") else None)
                if f_type:
                    # Trajectory Logic for DEP/ARR
                    hdg = s[10] or 0
                    dist_to_london = math.sqrt((s[6] - 51.5)**2 + (s[5] - 0.1)**2)
                    is_inbound = True if (hdg > 200 and hdg < 360) and dist_to_london > 0.5 else False
                    
                    fleet.append({
                        "call": call, "lat": s[6], "lon": s[5], "type": f_type, 
                        "alt": round((s[7] or 0) * 3.28084), "hdg": hdg,
                        "dep": "OUTSTATION" if is_inbound else ("LCY" if f_type=="CFE" else "LGW"),
                        "arr": ("LCY" if f_type=="CFE" else "LGW") if is_inbound else "OUTSTATION"
                    })
    except: pass
    return fleet

# 5. EXECUTION
ac_data = fetch_ac_fleet()
st.markdown(f'<div class="ba-header"><div>BA OCC MASTER HUD | v35.50</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

# 6. SIDEBAR (v29.2 LEGACY RESTORE)
with st.sidebar:
    st.title("🛡️ STRATEGIC COMMAND")
    if st.button("🔄 MANUAL REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    st.markdown("📡 **MAP FILTERS**")
    f_cf = st.checkbox("Cityflyer Stations (Blue)", value=True)
    f_ef = st.checkbox("Euroflyer Stations (Red)", value=True)
    f_window = st.selectbox("Operational Window:", ["Live", "6hr Strategy", "12hr Tactical", "24hr Planning"])
    
    st.markdown("---")
    active_calls = [p['call'] for p in ac_data] if ac_data else ["Scanning..."]
    focus = st.selectbox("Highlight Primary Flight:", active_calls)
    
    st.markdown("---")
    st.markdown("📟 **RAG ALERTS**")
    tabs = st.tabs(["CFE Alerts", "EFW Alerts", "Briefings"])

# 7. MAP
m = folium.Map(location=[50.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")

# STATION RAG LAYER
for iata, info in stations.items():
    if not ((info['fleet'] == "CFE" and f_cf) or (info['fleet'] == "EFW" and f_ef)): continue
    wx = fetch_wx_rag(info['icao'])
    
    popup_html = f"""<div style='color:black; width:400px; font-family:Arial;'>
                    <b style='font-size:1.2rem;'>{iata} - {info['icao']}</b><hr>
                    <b style='color:{wx['color']}; font-size:1.4rem;'>STATUS: {wx['status']}</b><br>
                    <p style='background:#eee; padding:10px; font-size:1.1rem;'>{wx['raw']}</p>
                    <b>BRIEF:</b> {info['brief']}</div>"""
    folium.CircleMarker([info['lat'], info['lon']], radius=10, color=wx['color'], fill=True, popup=folium.Popup(popup_html, max_width=450)).add_to(m)
    
    if wx['status'] != "GREEN":
        with tabs[0 if info['fleet']=="CFE" else 1]:
            st.warning(f"{iata}: {wx['status']}")

# AIRCRAFT HD LAYER
for p in ac_data:
    p_color = "white" if p['call'] == focus else ("#00bfff" if p['type']=="CFE" else "#ff4500")
    
    # Vector Line to Hub
    hub_pos = [51.505, 0.055] if p['type'] == "CFE" else [51.148, -0.190]
    folium.PolyLine([hub_pos, [p['lat'], p['lon']]], color=p_color, weight=1, opacity=0.3, dash_array='10, 20').add_to(m)
    
    # HD Isolated Plane Icon
    icon_html = f'<div style="transform: rotate({p["hdg"]}deg); font-size: 26px; color: {p_color}; text-shadow: 0 0 5px #000;"><i class="fa fa-plane"></i></div>'
    folium.Marker(
        [p['lat'], p['lon']], icon=folium.DivIcon(html=icon_html),
        tooltip=f"<b>{p['call']}</b><br>DEP: {p['dep']} | ARR: {p['arr']}<br>ALT: {p['alt']}ft"
    ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_50_iron")
