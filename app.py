import streamlit as st
import folium
from streamlit_folium import st_folium
from fr24sdk.client import Client 
from datetime import datetime

# 1. PAGE CONFIG
st.set_page_config(layout="wide", page_title="BA OCC Final Probe")

# 2. CSS STYLING
st.markdown("""
    <style>
    .main { background-color: #001a33 !important; }
    html, body, [class*="st-"], div, p, h1, h2, h4, label { color: white !important; }
    .ba-header { background-color: #002366; padding: 20px; border: 2px solid #d6001a; display: flex; justify-content: space-between; }
    [data-testid="stSidebar"] { background-color: #002366 !important; border-right: 3px solid #d6001a; min-width: 400px !important; }
    .status-card { background-color: #111; padding: 15px; border-radius: 5px; border: 1px solid #444; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# 3. YOUR TOKEN
LIVE_TOKEN = "019c7003-96dc-7061-aacf-54bfde6a7847|wb9k84G45pNBUFJJppAywj8kjMzVcOqmAst0D0o9f98666e1"

# 4. DATA ENGINE
@st.cache_data(ttl=60)
def final_data_probe():
    fleet = []
    api_log = "Initializing..."
    try:
        # We specify the client with no extra sandbox flags to ensure we are hitting the production gate
        with Client(api_token=LIVE_TOKEN) as client:
            # Huge box covering all UK/Europe flight paths
            bounds = "62.0,35.0,-15.0,15.0"
            flights = client.live.flight_positions.get_light(bounds=bounds)
            
            if flights and flights.data:
                api_log = f"SUCCESS: Received {len(flights.data)} flights."
                for f in flights.data:
                    call = (getattr(f, 'callsign', "") or getattr(f, 'flight', "") or "???").upper()
                    
                    # Filtering for BA Group
                    f_tag = "OTHER"
                    if any(x in call for x in ["CFE", "EFW", "BAW", "SHT"]):
                        f_tag = "BA_GROUP"
                    
                    fleet.append({"call": call, "lat": f.lat, "lon": f.lon, "type": f_tag})
            else:
                api_log = "EMPTY: No flights returned in this region."
    except Exception as e:
        api_log = f"DENIED: {str(e)}"
    
    return fleet, api_log

# 5. EXECUTION
traffic, log_msg = final_data_probe()
st.markdown(f'<div class="ba-header"><div>OCC HUD v35.30</div><div>{datetime.now().strftime("%H:%M")}Z</div></div>', unsafe_allow_html=True)

# 6. SIDEBAR
with st.sidebar:
    st.title("🛡️ SUBSCRIPTION VERIFIER")
    if st.button("🔄 REFRESH"): st.cache_data.clear(); st.rerun()
    st.markdown("---")
    
    st.markdown(f'<div class="status-card"><b>API Log:</b><br>{log_msg}</div>', unsafe_allow_html=True)
    
    ba_count = len([p for p in traffic if p['type'] == "BA_GROUP"])
    st.metric("BA Group Detected", ba_count)
    
    if ba_count == 0 and "SUCCESS" in log_msg:
        st.error("Explorer Plan Restriction: You are seeing 'Traffic', but FR24 is filtering out all Scheduled Airlines (CFE/EFW).")
    elif "DENIED" in log_msg:
        st.warning("Auth Failure: The token is not valid for this SDK version.")

# 7. MAP
m = folium.Map(location=[51.5, 0.0], zoom_start=6, tiles="CartoDB dark_matter")
for p in traffic:
    color = "blue" if p['type'] == "BA_GROUP" else "gray"
    folium.Marker([p['lat'], p['lon']], tooltip=p['call'], icon=folium.Icon(color=color)).add_to(m)
st_folium(m, width=1200, height=800, key="v35_30")
