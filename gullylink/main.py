from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import List, Dict
import json
import asyncio

app = FastAPI()

# --- CONFIGURATION ---
# 1. Database Setup (MongoDB)
# Replace with your actual MongoDB URI if hosting remotely. 
# For local, ensure MongoDB is running or use a cloud string.
MONGO_URI = "mongodb://localhost:27017" 
client = AsyncIOMotorClient(MONGO_URI)
db = client.gullylink
vendors_collection = db.vendors
orders_collection = db.orders

# 2. CORS (Allow Frontend to talk to Backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REALTIME WEBSOCKET MANAGER ---
class ConnectionManager:
    def __init__(self):
        # Store active connections: 'user' or 'vendor'
        self.active_connections: Dict[str, List[WebSocket]] = {"user": [], "vendor": []}

    async def connect(self, websocket: WebSocket, role: str):
        await websocket.accept()
        self.active_connections[role].append(websocket)

    def disconnect(self, websocket: WebSocket, role: str):
        if websocket in self.active_connections[role]:
            self.active_connections[role].remove(websocket)

    # Send message to all Users (e.g., Vendor moved)
    async def broadcast_to_users(self, message: dict):
        for connection in self.active_connections["user"]:
            await connection.send_json(message)

    # Send message to a specific Vendor (e.g., New Order)
    # For MVP simplicity, we broadcast to all vendors, client side filters by ID
    async def broadcast_to_vendors(self, message: dict):
        for connection in self.active_connections["vendor"]:
            await connection.send_json(message)

manager = ConnectionManager()

# --- DATA MODELS ---
class VendorProfile(BaseModel):
    id: str
    name: str
    icon_type: str  # e.g., "burger", "coffee", "veg"
    location: dict  # {lat: float, lng: float}
    menu: List[dict] # [{name: "Poha", price: 20}]

class Order(BaseModel):
    vendor_id: str
    user_location: dict
    items: List[dict]
    total: float
    status: str = "pending" # pending, accepted, rejected

# --- API ROUTES ---

@app.get("/")
async def root():
    return {"message": "GullyLINK API is Running"}

# 1. Vendor Updates Location (Realtime)
@app.websocket("/ws/vendor/{vendor_id}")
async def vendor_websocket(websocket: WebSocket, vendor_id: str):
    await manager.connect(websocket, "vendor")
    try:
        while True:
            data = await websocket.receive_json()
            # Expecting: {lat: x, lng: y, type: "location_update"}
            if data.get("type") == "location_update":
                # Broadcast new location to ALL users immediately
                await manager.broadcast_to_users({
                    "type": "vendor_moved",
                    "vendor_id": vendor_id,
                    "location": data["location"],
                    "icon": data.get("icon", "default")
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, "vendor")

# 2. User Listens for Vendors
@app.websocket("/ws/user")
async def user_websocket(websocket: WebSocket):
    await manager.connect(websocket, "user")
    try:
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket, "user")

# 3. Create Order (User -> Vendor)
@app.post("/api/order")
async def create_order(order: Order):
    new_order = order.dict()
    # Save to DB
    result = await orders_collection.insert_one(new_order)
    new_order["_id"] = str(result.inserted_id)
    
    # Alert the Vendor Realtime
    await manager.broadcast_to_vendors({
        "type": "new_order",
        "order": new_order
    })
    return {"status": "Order Placed", "order_id": str(result.inserted_id)}

# 4. Vendor Respond to Order (Accept/Reject)
@app.post("/api/order/{order_id}/status")
async def update_order_status(order_id: str, status: str):
    # Update DB
    await orders_collection.update_one({"_id": order_id}, {"$set": {"status": status}})
    return {"status": "updated"}

# 5. Initialize Vendor (Mock Data for MVP)
@app.post("/api/vendor/init")
async def init_vendor(vendor: VendorProfile):
    # Upsert vendor in DB
    await vendors_collection.update_one(
        {"id": vendor.id}, 
        {"$set": vendor.dict()}, 
        upsert=True
    )
    return {"msg": "Vendor Online"}

# Run with: uvicorn main:app --reload
