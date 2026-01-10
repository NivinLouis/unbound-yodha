import socketio
import time
from config import SERVER_URL  # Make sure this is just 'http://localhost:5000', not '/cv-data'

# Initialize the Socket.IO Client
sio = socketio.Client()

# ==========================================
# 1. ESTABLISH CONNECTION (Run this once at start)
# ==========================================
try:
    print(f"🔌 Connecting to server at {SERVER_URL}...")
    sio.connect(SERVER_URL, transports=['websocket', 'polling'])
    print("✅ Connected to Central ICU Server!")
except Exception as e:
    print(f"❌ Connection Failed: {e}")
    # Optional: Logic to exit or retry could go here

# ==========================================
# 2. THE SENDING FUNCTION
# ==========================================
def send_to_server(payload):
    """
    Emits the CV data to the 'seedy_update' event listener on the server.
    """
    if sio.connected:
        try:
            # We match the event name '@sio.event async def seedy_update' from your server code
            sio.emit('seedy_update', payload)
            print(f"Sent: {payload['is_agitated']} | {payload['posture']}")
        except Exception as e:
            print(f"⚠️ Failed to emit data: {e}")
    else:
        print("⚠️ Not connected to server. Attempting to reconnect...")
        try:
            sio.connect(SERVER_URL)
        except:
            pass