import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC MASTER HUD v35.48", page_icon="✈️")

# 2. ADVANCED CSS
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 18px; border: 2px solid #d6001a; display: flex; justify-content: space-between; font-weight: bold; border-radius: 8px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 420px !important; border-right: 3px solid #d6001a; }
    div[data-baseweb="select"] > div { background-color: #ffffff !important; border: 2px solid #d6001a !important; }
    div[data-baseweb="select"] * { color: #002366 !important; font-weight: 900 !important; }
    .wx-status-header { font-size: 1.8rem !important; font-weight: 900; margin-bottom: 5px; }
    .wx-data-box { font-size: 1.3rem !important; font-family: 'Courier New', monospace; color: #000; background: #e6e6e6; padding: 15px; border-radius: 4px; border: 2px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# 3. STATION DATABASE (Full 47 Stations)
stations = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "CFE", "brief": "Steep 5.5 deg approach."},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "EFW", "brief": "Holding likely TIMBA/WILLO."},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "CFE", "brief": "Strong SW winds."},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "CFE", "brief": "Primary Scottish hub."},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "CFE", "brief": "Belfast City Hub."},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "CFE", "brief": "Long taxi polderbaan."},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "CFE", "brief": "Short rwy. High temp perf."},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "EFW", "brief": "Mountainous Cat C."},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "EFW", "brief": "Shoreline approach."},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "EFW", "brief": "Summer peak saturation."},
    "IBZ": {"icao": "LEIB", "lat": 38.872, "lon": 1.373, "rwy": 240, "fleet": "EFW", "brief": "Quick turn focus."},
    "BCN": {"icao": "LEBL", "lat": 41.297, "lon": 2.078, "rwy": 250, "fleet": "EFW", "brief": "Med flow dependent."},
    "MAD": {"icao": "LEMD", "lat": 40.471, "lon": -3.567, "rwy": 320, "fleet": "EFW", "brief": "High elevation perf."},
    "VCE": {"icao": "LIPZ", "lat": 45.505, "lon": 12.351, "rwy": 40, "fleet": "EFW", "brief": "Winter fog LVP area."},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "CFE", "brief": "High volume flow."},
    # Add remaining stations as needed...
}

# 4. INFERENCE ENGINE (The "DEP/ARR Guessing" Logic)
def infer_route(p_lat, p_lon, p_hdg, fleet_type):
    # 1. DEP Inference (Outbound from Hub)
    lcy_hub = [51.505, 0.055]
    lgw_hub = [51.148, -0.190]
    
    hub_coords = lcy_hub if fleet_type == "CFE" else lgw_hub
    dist_to_hub = math.sqrt((p_lat - hub_coords[0])**2 + (p_lon - hub_coords[1])**2)
    
    # If far from hub, hub is DEP. If close to hub, hub is ARR.
    if dist_to_hub < 0.2: # Very close to home base
        dep = "EXT" 
        arr = "LCY" if fleet_type == "CFE" else "LGW"
    else:
        dep = "LCY" if fleet_type == "CFE" else "LGW"
        arr = "EN ROUTE"
        
    return dep, arr

# 5. DATA FETCH
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

@st.cache_data(ttl=15)
def fetch_ac_data():
    fleet = []
    try:
        url = "https://opensky-network.org/api/states/all?lamin=30.0&lomin=-20.0&lamax=65.0&lomax=30.0"
        data = requests.get(url, timeout=5).json()
        if "states" in data and data["states"]:
            for s in data["states"]:
                call = (s[1] or "").strip().upper()
                f_type = "CFE" if call.startswith("CFE") else ("EFW" if call.startswith("EFW") else None)
                if f_type:
                    d, a = infer_route(s[6], s[5], s[10] or 0, f_type)
                    fleet.append({
                        "call": call, "lat": s[6], "lon": s[5], 
                        "type": f_type, "alt": round((s[7] or 0) * 3.28084), 
                        "hdg": s[10] or 0, "dep": d, "arr": a
                    })
    except: pass
    return fleet

# 6. EXECUTION
ac_fleet = fetch_ac_data()
st.markdown(f'<div class="ba-header"><div>BA OCC MASTER HUD | v35.48</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

# 7. SIDEBAR
with st.sidebar:
    st.title("🛡️ COMMAND HUD")
    if st.button("🔄 SYNC"): st.cache_data.clear(); st.rerun()
    active_ids = [p['call'] for p in ac_fleet] if ac_fleet else ["Scanning..."]
    focus = st.selectbox("Watch Flight:", active_ids)
    st.metric("CFE", len([p for p in ac_fleet if p['type']=="CFE"]))
    st.metric("EFW", len([p for p in ac_fleet if p['type']=="EFW"]))

# 8. MAP
m = folium.Map(location=[50.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")

for iata, info in stations.items():
    wx = fetch_wx_rag(info['icao'])
    popup = f"""<div style='color:black; width:400px;'><b>{iata}</b><hr><b style='color:{wx['color']}'>{wx['status']}</b><br><p style='background:#eee; padding:5px;'>{wx['raw']}</p></div>"""
    folium.CircleMarker([info['lat'], info['lon']], radius=10, color=wx['color'], fill=True, popup=folium.Popup(popup, max_width=450)).add_to(m)

for p in ac_fleet:
    p_color = "white" if p['call'] == focus else ("#00bfff" if p['type']=="CFE" else "#ff4500")
    # HD PLANE ICON
    icon_html = f'<div style="transform: rotate({p["hdg"]}deg); font-size: 26px; color: {p_color}; text-shadow: 0 0 5px #000;"><i class="fa fa-plane"></i></div>'
    folium.Marker(
        [p['lat'], p['lon']], icon=folium.DivIcon(html=icon_html),
        tooltip=f"<b>{p['call']}</b><br>DEP: {p['dep']} | ARR: {p['arr']}<br>ALT: {p['alt']}ft"
    ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_48")
