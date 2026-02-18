import streamlit as st
import folium
from streamlit_folium import st_folium
from fr24sdk.client import Client 
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. STABLE v29.2 CSS (NAVY & RED)
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; border-radius: 8px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; border-right: 3px solid #d6001a; min-width: 350px !important; }
    .stMetric { background-color: #001a33; border-left: 5px solid #d6001a; padding: 10px; }
    .debug-box { background-color: #000; color: #0f0 !important; padding: 10px; font-family: monospace; font-size: 0.8rem; border: 1px solid #333; margin-bottom: 20px;}
    </style>
    """, unsafe_allow_html=True)

# 3. LIVE PRODUCTION TOKEN
LIVE_TOKEN = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"

# 4. DATA ENGINE (v35.25 - Multi-Fleet Logic)
@st.cache_data(ttl=60)
def fetch_ops_data():
    fleet = []
    raw_log = ""
    try:
        with Client(api_token=LIVE_TOKEN) as client:
            # Expanded European Operations Box
            bounds = "71.0,30.0,-20.0,35.0" 
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                raw_log = f"Total Detected: {len(flights.data)}"
                for f in flights.data:
                    call = (getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "UKNOWN").upper()
                    
                    # Tagging Logic
                    f_tag = "OTHER"
                    if "CFE" in call: f_tag = "CFE"
                    elif "EFW" in call: f_tag = "EFW"
                    elif "BAW" in call or "SHT" in call: f_tag = "BA_GROUP"
                    
                    fleet.append({
                        "callsign": call, 
                        "lat": f.lat, 
                        "lon": f.lon, 
                        "type": f_tag
                    })
        return fleet, raw_log
    except Exception as e:
        return [], f"Error: {str(e)}"

# 5. RENDER HUD
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.25 | OPERATIONS BASELINE</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

all_flights, status = fetch_ops_data()

with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH LIVE FEED"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    # Live Totals
    cfe_count = len([p for p in all_flights if p['type'] == "CFE"])
    efw_count = len([p for p in all_flights if p['type'] == "EFW"])
    ba_count = len([p for p in all_flights if p['type'] == "BA_GROUP"])
    
    st.metric("Cityflyer (CFE)", cfe_count)
    st.metric("Euroflyer (EFW)", efw_count)
    st.metric("BA Mainline/SHT", ba_count)
    
    st.markdown("---")
    st.markdown("🎯 **MAP FILTERS**")
    show_all = st.checkbox("Show All Traffic (Gray)", value=True)
    show_ba_only = st.checkbox("Show BA Group Only", value=False)
    
    st.markdown("---")
    st.caption(status)

# 6. MAP RENDER
# Center on London City / Gatwick area
m = folium.Map(location=[51.5, 0.0], zoom_start=6, tiles="CartoDB dark_matter")

if all_flights:
    for p in all_flights:
        # Filtering logic
        if show_ba_only and p['type'] == "OTHER": continue
        if not show_all and p['type'] == "OTHER": continue
            
        # Color Coding
        icon_color = "gray"
        if p['type'] == "CFE": icon_color = "blue"
        elif p['type'] == "EFW": icon_color = "red"
        elif p['type'] == "BA_GROUP": icon_color = "cadetblue"
        
        folium.Marker(
            location=[p['lat'], p['lon']],
            icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
            tooltip=f"{p['callsign']}"
        ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_25_ops")
