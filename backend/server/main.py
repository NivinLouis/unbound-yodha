import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from collections import deque

# ==========================================
# 1. SERVER SETUP
# ==========================================
# Create the WebSocket Server (The Hub)
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()

# Add CORS for HTTP endpoints (crucial for the video POST requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Socket.IO to the FastAPI app
sio_app = socketio.ASGIApp(sio, app)

# ==========================================
# 2. DATA MODELS (For HTTP POST)
# ==========================================
class VideoPayload(BaseModel):
    frame: str

class CVDataPayload(BaseModel):
    posture: str
    is_agitated: bool
    fall_risk: bool

# ==========================================
# 3. THE GLOBAL STATE (The "Memory")
# ==========================================
current_state = {
    "patient": {"id": "ICU-04", "name": "Alex Doe"},
    "vitals": {
        "heart_rate": 72,
        "spo2": 98,
        "bed_pressure_index": 0
    },
    "environment": {
        "noise_level_db": 40,
        "light_lux": 300
    },
    "behavior": {
        "posture": "Supine",
        "is_agitated": False,
        "fall_risk": False,
        "privacy_mode": False
    },
    "analysis": {
        "risk_score": 0,
        "risk_level": "Stable",
        "current_sleep_stage": "Awake",
        "intervention_active": False
    },
    "event_log": deque(maxlen=5) 
}

# Helper to add a log message
def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    current_state['event_log'].appendleft(entry)
    return list(current_state['event_log'])

# ==========================================
# 4. THE BRAIN (Risk Calculation Logic)
# ==========================================
def calculate_risk_score():
    score = 0
    
    # --- Factor A: Vitals ---
    hr = current_state['vitals']['heart_rate']
    if hr > 100 or hr < 50: score += 20
    
    bed_movement = current_state['vitals']['bed_pressure_index']
    if bed_movement > 50: score += 15
    if bed_movement > 80: score += 20 

    # --- Factor B: Environment ---
    noise = current_state['environment']['noise_level_db']
    if noise > 70: score += 15
    
    # --- Factor C: Behavior ---
    if current_state['behavior']['is_agitated']: score += 30
    if current_state['behavior']['fall_risk']: score += 50 

    # Cap score at 100
    final_score = min(score, 100)
    
    # Update Analysis block
    current_state['analysis']['risk_score'] = final_score
    
    if final_score < 40:
        current_state['analysis']['risk_level'] = "Stable"
    elif final_score < 75:
        current_state['analysis']['risk_level'] = "Warning"
    else:
        current_state['analysis']['risk_level'] = "CRITICAL"
        current_state['analysis']['intervention_active'] = True 
        
    return final_score

# ==========================================
# 5. HTTP ENDPOINTS (For Seedy's CV Script)
# ==========================================

@app.post("/video")
async def receive_video(data: VideoPayload):
    """
    Receives base64 video frame from CV script via HTTP POST
    and emits it to the Dashboard via WebSockets.
    """
    # Directly broadcast frame to Meera (Dashboard)
    # We use a separate event 'video_frame' so it doesn't lag the data stream
    await sio.emit('video_frame', data.frame)
    return {"status": "ok"}

@app.post("/cv-data")
async def receive_cv_data(data: CVDataPayload):
    """
    Receives Analysis Data from CV script via HTTP POST
    Updates Global State and broadcasts to Dashboard.
    """
    print(f"📷 CV Update via HTTP: Posture={data.posture}, Agitated={data.is_agitated}")

    # 1. Update Global State
    current_state['behavior']['posture'] = data.posture
    current_state['behavior']['is_agitated'] = data.is_agitated
    current_state['behavior']['fall_risk'] = data.fall_risk

    # 2. Log specific scary events
    if data.fall_risk:
        add_log("CRITICAL: FALL RISK DETECTED!")
    if data.is_agitated:
        add_log("WARN: Agitation/Thrashing detected")

    # 3. Recalculate Risk
    calculate_risk_score()

    # 4. Broadcast FULL State to Everyone
    state_to_send = current_state.copy()
    state_to_send['event_log'] = list(current_state['event_log'])
    
    await sio.emit('update_data', state_to_send)
    return {"status": "ok"}

# ==========================================
# 6. SOCKET EVENTS (Connection & Vitals)
# ==========================================
@sio.event
async def connect(sid, environ, auth=None):
    print(f"✅ Client Connected: {sid}")
    state_to_send = current_state.copy()
    state_to_send['event_log'] = list(current_state['event_log'])
    await sio.emit('update_data', state_to_send, to=sid)

@sio.event
async def disconnect(sid):
    print(f"❌ Client Disconnected: {sid}")

# LISTEN TO NIVIN (Hardware/Simulator)
@sio.event
async def nivin_update(sid, data):
    # Update Vitals & Environment
    current_state['vitals']['heart_rate'] = data.get('heart_rate', 72)
    current_state['vitals']['spo2'] = data.get('spo2', 98)
    current_state['vitals']['bed_pressure_index'] = data.get('bed_movement_intensity', 0)
    current_state['environment']['noise_level_db'] = data.get('room_noise_db', 40)
    current_state['environment']['light_lux'] = data.get('room_light_lux', 300)

    calculate_risk_score()
    
    state_to_send = current_state.copy()
    state_to_send['event_log'] = list(current_state['event_log'])
    
    await sio.emit('update_data', state_to_send)

# LISTEN TO SEEDY (Via Socket - Backup option)
@sio.event
async def seedy_update(sid, data):
    print(f"Received Seedy Data (Socket): {data}")
    current_state['behavior']['is_agitated'] = data.get('is_agitated', False)
    current_state['behavior']['posture'] = data.get('posture', "Supine")
    current_state['behavior']['fall_risk'] = data.get('fall_risk', False)
    
    if data.get('fall_risk'): add_log("CRITICAL: FALL RISK DETECTED!")
    if data.get('is_agitated'): add_log("WARN: Agitation/Thrashing detected")

    calculate_risk_score()
    
    state_to_send = current_state.copy()
    state_to_send['event_log'] = list(current_state['event_log'])
    await sio.emit('update_data', state_to_send)

# ==========================================
# 7. RUN
# ==========================================
if __name__ == '__main__':
    # Run on 0.0.0.0 to let other laptops connect
    uvicorn.run(sio_app, host='0.0.0.0', port=5000)