import asyncio
import websockets
import json
import random

# Gwalior Phoolbagh Coordinates
BASE_LAT = 26.2124
BASE_LNG = 78.1772

async def simulate_stationary_vendor(vendor_id, name, icon):
    uri = f"ws://localhost:8000/ws/vendor/{vendor_id}"
    
    # Fixed location
    lat = BASE_LAT + random.uniform(-0.002, 0.002)
    lng = BASE_LNG + random.uniform(-0.002, 0.002)

    print(f"🏪 {name} ({vendor_id}) set up shop at {lat}, {lng}")

    async with websockets.connect(uri) as websocket:
        while True:
            # 2. Jitter (GPS usually fluctuates slightly even when standing still)
            jitter_lat = lat + random.uniform(-0.00001, 0.00001)
            jitter_lng = lng + random.uniform(-0.00001, 0.00001)
            
            payload = {
                "type": "location_update",
                "vendor_id": vendor_id,
                "icon": icon, 
                "location": {"lat": jitter_lat, "lng": jitter_lng}
            }
            
            await websocket.send(json.dumps(payload))
            # print(f"📍 {name} pinged location")
            
            # Update every 5 seconds (Slower than moving vendors)
            await asyncio.sleep(5)

async def main():
    # Run 2 stationary vendors
    await asyncio.gather(
        simulate_stationary_vendor("v_bot_4", "SS Kachori", "food"),
        simulate_stationary_vendor("v_bot_5", "Bahadur Poha", "food")
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Stopped Stationary Vendors")
