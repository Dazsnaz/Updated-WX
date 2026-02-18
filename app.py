import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import math
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. LEGACY v29.2 UI RESTORATION (The "Better Look" CSS)
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { 
        background-color: #002366; padding: 20px; border-radius: 8px; 
        margin-bottom: 20px; border: 3px solid #d6001a; 
        display: flex; justify-content: space-between; font-weight: bold;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    [data-testid="stSidebar"] { background-color: #002366 !important; min-width: 450px !important; border-right: 3px solid #d6001a; }
    
    /* v29.2 NAVY BLUE DROPDOWN FIX */
    div[data-baseweb="select"] > div { background-color: white !important; }
    div[data-baseweb="select"] * { color: #002366 !important; font-weight: 900 !important; }
    
    /* STRATEGY BRIEF CARDS */
    .strategy-card { 
        background-color: #003366; border-left: 10px solid #d6001a; 
        padding: 15px; border-radius: 5px; margin-bottom: 10px; border-top: 1px solid #444;
    }
    .stMetric { background-color: #011627; border: 1px solid #d6001a; padding: 15px; border-radius: 5px; }
    .wx-data-box { 
        font-family: 'Courier New', monospace; background: #e6e6e6; 
        color: #000; padding: 12px; border-radius: 4px; font-size: 1.1rem; line-height: 1.3;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. THE FULL 47-STATION STRATEGIC DATABASE (v29.2 Content)
stations = {
    "LCY": {"icao": "EGLC", "lat": 51.505, "lon": 0.055, "rwy": 270, "fleet": "CFE", "brief": "Steep 5.5° approach. Low Vis Hub. Divert: STN/SEN."},
    "LGW": {"icao": "EGKK", "lat": 51.148, "lon": -0.190, "rwy": 260, "fleet": "EFW", "brief": "Single rwy saturation. Holding TIMBA/WILLO."},
    "EDI": {"icao": "EGPH", "lat": 55.950, "lon": -3.363, "rwy": 240, "fleet": "CFE", "brief": "Strong SW winds. High terrain N departure."},
    "GLA": {"icao": "EGPF", "lat": 55.871, "lon": -4.433, "rwy": 230, "fleet": "CFE", "brief": "Scottish Hub. Primary divert for EDI."},
    "INN": {"icao": "LOWI", "lat": 47.260, "lon": 11.344, "rwy": 260, "fleet": "EFW", "brief": "Cat C Special. Performance limited. Foehn wind turbulence."},
    "FLR": {"icao": "LIRQ", "lat": 43.810, "lon": 11.205, "rwy": 50, "fleet": "CFE", "brief": "Short rwy. One-way ops. High temp payload restrictions."},
    "AMS": {"icao": "EHAM", "lat": 52.313, "lon": 4.764, "rwy": 180, "fleet": "CFE", "brief": "Slot constrained. Long taxi times (>20m)."},
    "NCE": {"icao": "LFMN", "lat": 43.665, "lon": 7.215, "rwy": 40, "fleet": "EFW", "brief": "Noise sensitive Shoreline approach."},
    "PMI": {"icao": "LEPA", "lat": 39.551, "lon": 2.738, "rwy": 240, "fleet": "EFW", "brief": "Holiday peak saturation. ATC flow restrictions."},
    "FAO": {"icao": "LPFR", "lat": 37.014, "lon": -7.965, "rwy": 100, "fleet": "EFW", "brief": "Bird strike risk area. Strong coastal gusts."},
    "IBZ": {"icao": "LEIB", "lat": 38.872, "lon": 1.373, "rwy": 240, "fleet": "EFW", "brief": "Quick turn focus. Limited stand availability."},
    "ZRH": {"icao": "LSZH", "lat": 47.458, "lon": 8.548, "rwy": 160, "fleet": "CFE", "brief": "High precision hub. Complex integration."},
    "JER": {"icao": "EGJJ", "lat": 49.207, "lon": -2.195, "rwy": 260, "fleet": "CFE", "brief": "Channel sea fog risk. Primary island link."},
    "BHD": {"icao": "EGAC", "lat": 54.618, "lon": -5.872, "rwy": 220, "fleet": "CFE", "brief": "Belfast City Hub. Strict noise abatement."},
    "DUB": {"icao": "EIDW", "lat": 53.421, "lon": -6.270, "rwy": 280, "fleet": "CFE", "brief": "High volume cross-sea flow."},
    "MLA": {"icao": "LMML", "lat": 35.857, "lon": 14.477, "rwy": 310, "fleet": "EFW", "brief": "Med hub. Dust/Vis interference likely."},
    "LCA": {"icao": "LCLK", "lat": 34.875, "lon": 33.624, "rwy": 220, "fleet": "EFW", "brief": "Regional EFW anchor station."},
    "SZG": {"icao": "LOWS", "lat": 47.794, "lon": 13.004, "rwy": 150, "fleet": "EFW", "brief": "Alps winter gateway. De-icing priority."},
    "GVA": {"icao": "LSGG", "lat": 46.238, "lon": 6.108, "rwy": 220, "fleet": "EFW", "brief": "Business density flow. Lake winds."},
    "BER": {"icao": "EDDB", "lat": 52.366, "lon": 13.503, "rwy": 250, "fleet": "CFE", "brief": "Modern CAT III facility."},
    "FRA": {"icao": "EDDF", "lat": 50.033, "lon": 8.570, "rwy": 250, "fleet": "CFE", "brief": "Ground movement complexity. Heavy hub."},
    "BCN": {"icao": "LEBL", "lat": 41.297, "lon": 2.078, "rwy": 250, "fleet": "EFW", "brief": "Sea breeze influence. Dual rwy ops."},
    "MAD": {"icao": "LEMD", "lat": 40.471, "lon": -3.567, "rwy": 320, "fleet": "EFW", "brief": "High altitude performance. Complex ground."},
    "PRG": {"icao": "LKPR", "lat": 50.101, "lon": 14.263, "rwy": 240, "fleet": "CFE", "brief": "Central EU gateway node."},
    "ABZ": {"icao": "EGPD", "lat": 57.201, "lon": -2.197, "rwy": 160, "fleet": "CFE", "brief": "Oil sector logistics. Wind exposed."},
    "STN": {"icao": "EGSS", "lat": 51.885, "lon": 0.235, "rwy": 220, "fleet": "CFE", "brief": "Primary LCY divert. 24hr ops."},
    "LHR": {"icao": "EGLL", "lat": 51.470, "lon": -0.454, "rwy": 270, "fleet": "CFE", "brief": "Mainline Hub positioning ops."},
    "MUC": {"icao": "EDDM", "lat": 48.353, "lon": 11.786, "rwy": 260, "fleet": "CFE", "brief": "Heavy winter de-icing volume."},
    "DUS": {"icao": "EDDL", "lat": 51.289, "lon": 6.766, "rwy": 230, "fleet": "CFE", "brief": "Rhein-Ruhr regional anchor."},
    "HAM": {"icao": "EDDH", "lat": 53.630, "lon": 9.988, "rwy": 230, "fleet": "CFE", "brief": "Northern German hub node."},
    "BSL": {"icao": "LFSB", "lat": 47.590, "lon": 7.529, "rwy": 150, "fleet": "CFE", "brief": "Tri-border flow restrictions."},
    "LYS": {"icao": "LFLL", "lat": 45.726, "lon": 5.091, "rwy": 350, "fleet": "CFE", "brief": "Rhone valley winds. Logistics hub."},
    "VLC": {"icao": "LEVC", "lat": 39.489, "lon": -0.482, "rwy": 300, "fleet": "EFW", "brief": "Valencia coastal node."},
    "AGP": {"icao": "LEMG", "lat": 36.674, "lon": -4.499, "rwy": 130, "fleet": "EFW", "brief": "Dual rwy. Levanter wind focus."},
    "PSA": {"icao": "LIRP", "lat": 43.683, "lon": 10.395, "rwy": 40, "fleet": "CFE", "brief": "Tuscan seasonal link."},
    "CMF": {"icao": "LFLB", "lat": 45.638, "lon": 5.880, "rwy": 360, "fleet": "CFE", "brief": "Cat C Special. Ski winter node."},
    "BIO": {"icao": "LEBB", "lat": 43.301, "lon": -2.910, "rwy": 300, "fleet": "CFE", "brief": "Basque winds. Narrow valley approach."},
    "DBV": {"icao": "LDDU", "lat": 42.561, "lon": 18.268, "rwy": 110, "fleet": "EFW", "brief": "Balkan seasonal focus."},
    "SKG": {"icao": "LGTS", "lat": 40.520, "lon": 22.970, "rwy": 340, "fleet": "EFW", "brief": "Thessaloniki Greek anchor."},
    "HER": {"icao": "LGIR", "lat": 35.339, "lon": 25.180, "rwy": 270, "fleet": "EFW", "brief": "Crete summer flow saturation."},
    "BDS": {"icao": "LIBR", "lat": 40.657, "lon": 17.946, "rwy": 310, "fleet": "EFW", "brief": "Brindisi Adriatic link."},
    "TFS": {"icao": "GCTS", "lat": 28.044, "lon": -16.572, "rwy": 70, "fleet": "EFW", "brief": "Trade wind gusts. Long haul regional."},
    "ACE": {"icao": "GCRR", "lat": 28.945, "lon": -13.605, "rwy": 30, "fleet": "EFW", "brief": "Lanzarote volcanic crosswinds."},
    "FUE": {"icao": "GCFV", "lat": 28.452, "lon": -13.863, "rwy": 10, "fleet": "EFW", "brief": "Canary flow hub."},
}

# 4. WEATHER & FORECAST ENGINES (NOAA DUAL-PULL)
@st.cache_data(ttl=1800) # Hard 30m Lock for Shift Stability
def fetch_strategic_wx(icao):
    try:
        m_url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        t_url = f"https://tgftp.nws.noaa.gov/data/forecasts/taf/stations/{icao}.TXT"
        metar = requests.get(m_url, timeout=3).text.split('\n')[1]
        taf = requests.get(t_url, timeout=3).text.split('\n')[1]
        
        # RAG Minima Logic
        color = "#008000"; status = "GREEN"
        if any(x in metar for x in ["FG", "TS", "SN", "VV"]): color = "#d6001a"; status = "RED (ALRT)"
        elif any(x in metar for x in ["RA", "BR", "HZ", "DZ"]): color = "#ffbf00"; status = "AMBER (CAUT)"
        
        return {"metar": metar, "taf": taf, "color": color, "status": status}
    except: return {"metar": "DATA OFFLINE", "taf": "TAF OFFLINE", "color": "gray", "status": "UNKNOWN"}

# 5. AIRCRAFT TRACKING ENGINE
@st.cache_data(ttl=20)
def fetch_ac_radar():
    fleet = []
    try:
        url = "https://opensky-network.org/api/states/all?lamin=28.0&lomin=-20.0&lamax=65.0&lomax=30.0"
        data = requests.get(url, timeout=5).json()
        if "states" in data and data["states"]:
            for s in data["states"]:
                call = (s[1] or "").strip().upper()
                f_type = "CFE" if call.startswith("CFE") else ("EFW" if call.startswith("EFW") else None)
                if f_type:
                    hdg = s[10] or 0
                    dist_to_lcy = math.sqrt((s[6] - 51.5)**2 + (s[5] - 0.1)**2)
                    is_inbound = True if (hdg > 200 and hdg < 360) and dist_to_lcy > 0.5 else False
                    fleet.append({
                        "call": call, "lat": s[6], "lon": s[5], "type": f_type,
                        "alt": round((s[7] or 0) * 3.28084), "hdg": hdg,
                        "dep": "OUTSTN" if is_inbound else ("LCY" if f_type=="CFE" else "LGW"),
                        "arr": ("LCY" if f_type=="CFE" else "LGW") if is_inbound else "OUTSTN"
                    })
    except: pass
    return fleet

# 6. EXECUTION & SIDEBAR (The v29.2 Strategic Dashboard)
radar = fetch_ac_radar()
st.markdown(f'<div class="ba-header"><div>BA OCC MASTER HUD | v35.51</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.title("🛡️ COMMAND HUD")
    if st.button("🔄 MANUAL DATA SYNC"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    # v29.2 SIDEBAR FILTERS
    st.markdown("📡 **TACTICAL VIEWPORTS**")
    f_cf = st.checkbox("Cityflyer Fleet (Blue)", value=True)
    f_ef = st.checkbox("Euroflyer Fleet (Red)", value=True)
    f_window = st.selectbox("Operational Window:", ["Current (Live)", "6hr Forecast", "12hr Tactical", "24hr Strategy"])
    
    st.markdown("---")
    # DROPDOWN: High-Vis Navy
    calls = [p['call'] for p in radar] if radar else ["Scanning..."]
    focus = st.selectbox("Primary Flight Focus:", calls)
    
    st.markdown("---")
    st.markdown("📟 **RAG ALERTS & FORECASTS**")
    tabs = st.tabs(["Actuals (CFE)", "Actuals (EFW)", "Strategy Briefs"])

# 7. MAP (RAG Status + HD Rotating Aircraft)
m = folium.Map(location=[50.0, 5.0], zoom_start=5, tiles="CartoDB dark_matter")

# STATION RAG LAYER (The "Dream" Tooltip)
for iata, info in stations.items():
    if not ((info['fleet'] == "CFE" and f_cf) or (info['fleet'] == "EFW" and f_ef)): continue
    wx = fetch_strategic_wx(info['icao'])
    
    # v29.2 Large High-Vis Popup
    popup_html = f"""<div style='color:black; width:500px; font-family:Arial;'>
                    <b style='font-size:1.5rem;'>{iata} ({info['icao']})</b><hr>
                    <b style='color:{wx['color']}; font-size:1.8rem;'>{wx['status']}</b><br><br>
                    <div style='background:#f0f0f0; padding:15px; border-radius:5px;'>
                    <b style='font-size:1.2rem;'>ACTUAL (METAR):</b><br><code style='font-size:1.1rem;'>{wx['metar']}</code><br><br>
                    <b style='font-size:1.2rem;'>FORECAST (TAF):</b><br><code style='font-size:1.1rem;'>{wx['taf']}</code>
                    </div><br>
                    <b style='font-size:1.2rem;'>STRATEGY BRIEF:</b><br><p style='font-size:1.1rem;'>{info['brief']}</p></div>"""
    
    folium.CircleMarker([info['lat'], info['lon']], radius=10, color=wx['color'], fill=True, popup=folium.Popup(popup_html, max_width=520)).add_to(m)
    
    # Sidebar Alerts
    if wx['status'] != "GREEN":
        with tabs[0 if info['fleet']=="CFE" else 1]:
            st.error(f"{iata}: {wx['status']}")
    
    # Briefing Tab Population
    with tabs[2]:
        if iata in ["LCY", "LGW", "EDI", "INN", "FLR"]:
            st.markdown(f'<div class="strategy-card"><b>{iata} Strategy:</b><br>{info["brief"]}</div>', unsafe_allow_html=True)

# AIRCRAFT HD LAYER
for p in radar:
    p_color = "white" if p['call'] == focus else ("#00bfff" if p['type']=="CFE" else "#ff4500")
    # Vector Track
    hub = [51.505, 0.055] if p['type'] == "CFE" else [51.148, -0.190]
    folium.PolyLine([hub, [p['lat'], p['lon']]], color=p_color, weight=1, opacity=0.3, dash_array='10, 20').add_to(m)
    
    # Clean HD Plane
    icon_html = f'<div style="transform: rotate({p["hdg"]}deg); font-size: 26px; color: {p_color}; text-shadow: 0 0 5px #000;"><i class="fa fa-plane"></i></div>'
    folium.Marker([p['lat'], p['lon']], icon=folium.DivIcon(html=icon_html), 
                  tooltip=f"<b>{p['call']}</b><br>DEP: {p['dep']} | ARR: {p['arr']}<br>ALT: {p['alt']}ft").add_to(m)

st_folium(m, width=1200, height=800, key="v35_51_final")
