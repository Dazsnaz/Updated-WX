import streamlit as st
import folium
from streamlit_folium import st_folium
from fr24sdk.client import Client 
from datetime import datetime
import math

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. STABLE v29.2 CSS
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; border-radius: 8px; margin-bottom: 20px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; border-right: 3px solid #d6001a; min-width: 300px !important; }
    .stMetric { background-color: #001a33; border: 1px solid #d6001a; padding: 10px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# 3. LIVE PRODUCTION TOKEN
LIVE_TOKEN = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"

# 4. WIDE-NET DATA ENGINE
@st.cache_data(ttl=60)
def fetch_wide_fleet():
    fleet = []
    raw_total = 0
    try:
        with Client(api_token=LIVE_TOKEN) as client:
            # Re-formatted Bounds: North, South, West, East (covering all UK/EU/Med)
            bounds = "72.0,28.0,-25.0,45.0" 
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                raw_total = len(flights.data)
                for f in flights.data:
                    # Check multiple fields for the callsign string
                    call = (getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "").upper()
                    
                    f_type = None
                    if "CFE" in call: f_type = "CFE"
                    elif "EFW" in call: f_type = "EFW"
                    elif "SHT" in call: f_type = "SHT" # Adding Shuttle for visibility test
                    
                    if f_type:
                        fleet.append({
                            "callsign": call, 
                            "lat": getattr(f, 'lat', 0), 
                            "lon": getattr(f, 'lon', 0), 
                            "type": f_type
                        })
        return fleet, raw_total
    except Exception as e:
        return [], 0

# 5. RENDER HUD
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.23 | WIDE-NET OPS</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 REFRESH FLEET"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    active_fleet, total_api_count = fetch_wide_fleet()
    
    # Metrics
    st.metric("Cityflyer (CFE)", len([p for p in active_fleet if p['type'] == "CFE"]))
    st.metric("Euroflyer (EFW)", len([p for p in active_fleet if p['type'] == "EFW"]))
    st.metric("Shuttle (SHT)", len([p for p in active_fleet if p['type'] == "SHT"]))
    
    st.markdown("---")
    st.caption(f"API Zone Traffic: {total_api_count} flights")
    if active_fleet:
        st.write("Active Fleet List:")
        for p in active_fleet:
            st.code(f"{p['callsign']}")

# 6. MAP RENDER
# Auto-center on first aircraft found, otherwise default to London
center_lat, center_lon = 51.5, 0.0
if active_fleet:
    center_lat, center_lon = active_fleet[0]['lat'], active_fleet[0]['lon']

m = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles="CartoDB dark_matter")

for p in active_fleet:
    # Color coding
    icon_color = "blue" if p['type'] == "CFE" else ("red" if p['type'] == "EFW" else "cadetblue")
    folium.Marker(
        location=[p['lat'], p['lon']],
        icon=folium.Icon(color=icon_color, icon="plane", prefix="fa"),
        tooltip=p['callsign']
    ).add_to(m)

st_folium(m, width=1200, height=800, key="v35_23_widenet")
