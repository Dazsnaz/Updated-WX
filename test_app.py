import requests
import json

# Your Aviationstack Free Tier API Key
API_KEY = "3b58d69a6306718aaaffab704540eb21"

# The API endpoint (⚠️ Free tier MUST use http://, not https://)
URL = "http://api.aviationstack.com/v1/flights"

# We will search for a specific flight to see its live data.
# You can change 'BA8721' to any active flight number on your shift today.
params = {
    'access_key': API_KEY,
    'flight_iata': 'BA8721'
}

print(f"📡 Pinging Aviationstack for flight {params['flight_iata']}...")

try:
    response = requests.get(URL, params=params)
    data = response.json()
    
    # 1. Print the raw JSON data nicely formatted so you can see everything they give you
    print("\n" + "="*50)
    print(" RAW API RESPONSE (First 500 chars to prevent spam)")
    print("="*50)
    print(json.dumps(data, indent=4)[:500] + "\n... [truncated] ...\n")
    
    # 2. Extract the specific OCC metrics you are looking for
    if data.get('data'):
        flight = data['data'][0] # Get the first matching flight
        
        print("="*50)
        print(" 🎯 EXTRACTED OCC DATA")
        print("="*50)
        
        # Flight Info
        print(f"✈️ FLIGHT: {flight.get('flight', {}).get('iata')} / {flight.get('flight', {}).get('icao')}")
        print(f"📡 STATUS: {str(flight.get('flight_status')).upper()}")
        
        # Departure Info
        dep = flight.get('departure', {})
        print(f"\n🛫 DEPARTURE (DEP): {dep.get('iata')} (Gate: {dep.get('gate')})")
        print(f"   STD: {dep.get('scheduled')}")
        print(f"   ATD: {dep.get('actual') or 'Not Departed'}")
        
        # Arrival Info
        arr = flight.get('arrival', {})
        print(f"\n🛬 ARRIVAL (ARR): {arr.get('iata')} (Terminal: {arr.get('terminal')})")
        print(f"   STA: {arr.get('scheduled')}")
        print(f"   ETA: {arr.get('estimated') or 'No ETA provided yet'}")
        print("="*50)
        
    else:
        print("\n❌ No active flight found for that callsign right now. (It might not be flying today).")

except Exception as e:
    print(f"Error connecting to API: {e}")
