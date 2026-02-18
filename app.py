import streamlit as st
import folium
from streamlit_folium import st_folium
from fr24sdk.client import Client 
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Command HUD", page_icon="✈️")

# 2. STABLE v29.2 CSS
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; border-radius: 8px;}
    [data-testid="stSidebar"] { background-color: #002366 !important; border-right: 3px solid #d6001a; min-width: 350px !important; }
    .debug-box { background-color: #000; color: #0f0 !important; padding: 10px; font-family: monospace; font-size: 0.8rem; border: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# 3. LIVE PRODUCTION TOKEN
LIVE_TOKEN = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"

# 4. DATA ENGINE WITH RAW OUTPUT
@st.cache_data(ttl=60)
def fetch_raw_api_data():
    fleet = []
    raw_sample = "No data received"
    try:
        with Client(api_token=LIVE_TOKEN) as client:
            # Most Sandbox/Live API tiers prefer this N, S, W, E format
            bounds = "60.0,48.0,-10.0,5.0" # Tighter box over UK/France to force a hit
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                raw_sample = f"Total flights in packet: {len(flights.data)}\n"
                for i, f in enumerate(flights.data):
                    call = (getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "UNKNOWN").upper()
                    if i < 3: # Log first 3 raw flights for debugging
                        raw_sample += f" - Found: {call} at {f.lat}, {f.lon}\n"
                    
                    f_type = None
                    if "CFE" in call: f_type = "CFE"
                    elif "EFW" in call: f_type = "EFW"
                    elif "BAW" in call or "SHT" in call: f_type = "BA_GROUP"
                    
                    if f_type:
                        fleet.append({"callsign": call, "lat": f.lat, "lon": f.lon, "type": f_type})
        return fleet, raw_sample
    except Exception as e:
        return [], f"API Error: {str(e)}"

# 5. RENDER HUD
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.24 | DATA DEBUG</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

active_fleet, debug_info = fetch_raw_api_data()

with st.sidebar:
    st.title("🛠️ COMMAND HUD")
    if st.button("🔄 RE-PROBE API"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    st.markdown("📟 **RAW DATA STREAM**")
    st.markdown(f'<div class="debug-box">{debug_info}</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    st.metric("Cityflyer (CFE)", len([p for p in active_fleet if p['type'] == "CFE"]))
    st.metric("Euroflyer (EFW)", len([p for p in active_fleet if p['type'] == "EFW"]))
    st.metric("BA Group (BAW/SHT)", len([p for p in active_fleet if p['type'] == "BA_GROUP"]))

# 6. MAP
m = folium.Map(location=[52.0, -1.0], zoom_start=5, tiles="CartoDB dark_matter")
for p in active_fleet:
    color = "blue" if p['type'] == "CFE" else ("red" if p['type'] == "EFW" else "cadetblue")
    folium.Marker([p['lat'], p['lon']], icon=folium.Icon(color=color), tooltip=p['callsign']).add_to(m)

st_folium(m, width=1200, height=800, key="v35_24_debug")
