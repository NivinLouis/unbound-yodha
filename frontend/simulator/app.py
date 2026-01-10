import streamlit as st
import streamlit.components.v1 as components
import socketio
import time

# ============================================
# 1. SETUP & PAGE CONFIG
# ============================================
st.set_page_config(layout="wide", page_title="ICU Simulation Hub")

# Custom CSS
st.markdown("""
<style>
    .monitor-box {
        background-color: #000000;
        padding: 20px;
        border-radius: 10px;
        border: 2px solid #333;
    }
    .metric-value {
        font-size: 3em;
        font-weight: bold;
        font-family: 'Courier New', monospace;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if 'sio' not in st.session_state:
    st.session_state.sio = socketio.Client()
    st.session_state.connected = False

defaults = {'hr': 72, 'spo2': 98, 'noise': 40, 'light': 300, 'bed': 0}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ============================================
# 2. HELPER FUNCTIONS
# ============================================
def send_update():
    """Send data to Manav's server"""
    if st.session_state.connected:
        try:
            payload = {
                "heart_rate": st.session_state.hr,
                "spo2": st.session_state.spo2,
                "room_noise_db": st.session_state.noise,
                "room_light_lux": st.session_state.light,
                "bed_movement_intensity": st.session_state.bed
            }
            st.session_state.sio.emit('nivin_update', payload)
        except Exception as e:
            st.error(f"Transmission Error: {e}")

def set_scenario(hr, noise, light, bed, spo2=98):
    st.session_state.hr = hr
    st.session_state.noise = noise
    st.session_state.light = light
    st.session_state.bed = bed
    st.session_state.spo2 = spo2
    send_update()

def render_ecg_animation(hr, noise_level, sound_on):
    """
    Injects a Client-Side JavaScript Canvas to draw a live moving ECG.
    Includes rhythmic beeps for HR > 0 and CONTINUOUS TONE for HR == 0.
    """
    
    js_sound = "true" if sound_on else "false"

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ margin: 0; background: #0e1117; overflow: hidden; }}
        canvas {{ 
            width: 100%; height: 250px; 
            background-color: #000000; 
            border: 1px solid #333; 
            border-radius: 4px; 
            cursor: pointer; 
        }}
        #click-hint {{
            position: absolute; top: 10px; left: 10px; 
            color: #00ff00; font-family: monospace; font-size: 10px;
            background: rgba(0,0,0,0.7); padding: 2px 5px;
            display: none;
        }}
    </style>
    </head>
    <body>
    <div id="click-hint">CLICK GRAPH TO UNMUTE</div>
    <canvas id="ecgCanvas"></canvas>
    
    <script>
    (function() {{
        const canvas = document.getElementById('ecgCanvas');
        const ctx = canvas.getContext('2d');
        const hint = document.getElementById('click-hint');
        
        // --- AUDIO STATE ---
        let audioCtx = null;
        let soundEnabled = {js_sound};
        let lastBeepTime = 0;
        let flatlineOsc = null; // Tracks the continuous tone

        function initAudio() {{
            if (!audioCtx && soundEnabled) {{
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                audioCtx = new AudioContext();
            }}
            
            if (audioCtx && audioCtx.state === 'suspended') {{
                hint.style.display = "block";
                audioCtx.resume().then(() => {{
                    hint.style.display = "none";
                }});
            }}
        }}

        document.body.addEventListener('click', function() {{
            if (audioCtx && audioCtx.state === 'suspended') {{
                audioCtx.resume();
                hint.style.display = "none";
            }}
        }});

        // 1. Short Beep (Normal Heartbeat)
        function playBeep() {{
            if (!audioCtx || !soundEnabled) return;
            
            const osc = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();
            
            osc.connect(gainNode);
            gainNode.connect(audioCtx.destination);
            
            osc.type = 'square'; 
            osc.frequency.value = 800; 
            
            gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.15);
            
            osc.start();
            osc.stop(audioCtx.currentTime + 0.15);
        }}

        // 2. Start Continuous Tone (Flatline)
        function startFlatline() {{
            if (!audioCtx || !soundEnabled || flatlineOsc) return;

            flatlineOsc = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();
            
            flatlineOsc.connect(gainNode);
            gainNode.connect(audioCtx.destination);
            
            flatlineOsc.type = 'square';
            flatlineOsc.frequency.value = 800; // Constant pitch
            gainNode.gain.value = 0.1; // Constant volume
            
            flatlineOsc.start();
        }}

        // 3. Stop Continuous Tone
        function stopFlatline() {{
            if (flatlineOsc) {{
                try {{
                    flatlineOsc.stop();
                    flatlineOsc.disconnect();
                }} catch(e) {{}}
                flatlineOsc = null;
            }}
        }}

        // --- GRAPH & LOGIC LOOP ---
        function resize() {{
            canvas.width = window.innerWidth;
            canvas.height = 250;
        }}
        window.addEventListener('resize', resize);
        resize();

        let hr = {hr};
        let noiseLevel = {noise_level};
        
        let x = 0;
        let lastTime = Date.now();
        let data = []; 
        
        function getECGValue(t) {{
            let duration = 60 / (hr || 60); 
            let phase = t % duration;
            let pos = phase / duration; 
            
            let amp = 0;
            if (hr === 0) return 0; // Flatline math

            // PQRST Logic
            if(pos > 0.1 && pos < 0.2) amp += 5 * Math.sin((pos-0.15)*20*Math.PI);
            if(pos > 0.35 && pos < 0.38) amp -= 10; 
            if(pos >= 0.38 && pos < 0.44) amp += 80 * Math.sin((pos-0.41)*10*Math.PI); 
            if(pos >= 0.44 && pos < 0.48) amp -= 10; 
            if(pos > 0.6 && pos < 0.8) amp += 8 * Math.sin((pos-0.7)*5*Math.PI);
            
            let noise = (Math.random() - 0.5) * (noiseLevel * 0.5);
            return amp + noise;
        }}

        function draw() {{
            requestAnimationFrame(draw);
            
            let now = Date.now();
            let dt = (now - lastTime) / 1000;
            lastTime = now;
            
            // --- AUDIO MANAGER ---
            if (!soundEnabled) {{
                // If sound disabled mid-stream, kill flatline
                stopFlatline();
            }} else if (hr === 0) {{
                // ASYSTOLE: Start continuous tone
                startFlatline();
            }} else {{
                // NORMAL RHYTHM: Stop flatline, pulse beats
                stopFlatline();
                
                let beatInterval = 60000 / hr;
                if (now - lastBeepTime > beatInterval) {{
                    playBeep();
                    lastBeepTime = now;
                }}
            }}

            // --- DRAWING MANAGER ---
            let speed = canvas.width / 4; 
            x += speed * dt;
            if (x > canvas.width) {{
                x = 0;
                data = []; 
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }}

            let yVal = getECGValue(now / 1000);
            let centerY = canvas.height / 2;
            let y = centerY - yVal;
            
            data.push({{x: x, y: y}});

            ctx.beginPath();
            ctx.strokeStyle = '#00FF00'; 
            ctx.lineWidth = 2;
            ctx.lineJoin = 'round';
            
            if (data.length > 1) {{
                let lastPt = data[data.length - 2];
                let currPt = data[data.length - 1];
                ctx.beginPath();
                ctx.moveTo(lastPt.x, lastPt.y);
                ctx.lineTo(currPt.x, currPt.y);
                ctx.stroke();
            }}
            
            ctx.fillStyle = '#000000';
            ctx.fillRect(x + 1, 0, 20, canvas.height);
        }}
        
        initAudio(); 
        draw();
    }})();
    </script>
    </body>
    </html>
    """
    
    components.html(html_code, height=260, scrolling=False)

# ============================================
# 3. LAYOUT: SPLIT SCREEN
# ============================================
col_monitor, col_controls = st.columns([2,3])

# --------------------------------------------
# LEFT COLUMN: THE PATIENT MONITOR
# --------------------------------------------
with col_monitor:
    st.markdown("### Monitor")
    
    # 1. Status Banner
    if st.session_state.hr == 0:
        st.error(" ASYSTOLE (FLATLINE)")
    elif st.session_state.hr > 120 or st.session_state.hr < 50:
        st.error(" CRITICAL ALERT")
    else:
        st.success(" STABLE CONDITION")

    # 2. Big Metrics Row
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("HR (BPM)", st.session_state.hr, delta_color="inverse")
    with m2:
        st.metric("SPO2 (%)", st.session_state.spo2)
    with m3:
        rr = int(st.session_state.hr / 4)
        st.metric("RESP (RR)", rr)

    # 3. LIVE ECG ANIMATION (Audio Enabled)
    st.markdown("#### ECG Rhythm Strip")
    
    # Toggle for Sound
    use_sound = st.checkbox("🔊 Enable Heartbeat Audio", value=False)
    
    render_ecg_animation(st.session_state.hr, st.session_state.bed, use_sound)

    # 4. Environment Status
    st.divider()
    e1, e2, e3 = st.columns(3)
    e1.metric(" Noise (dB)", st.session_state.noise)
    e2.metric(" Light (Lux)", st.session_state.light)
    e3.metric(" Bed Activity", f"{st.session_state.bed}%")

# --------------------------------------------
# RIGHT COLUMN: THE JUDGE'S CONTROLS
# --------------------------------------------
with col_controls:
    st.subheader("Simulation Controls")
    
    st.write(" **Heart Rate**")
    st.slider("HR", 0, 200, key="hr", on_change=send_update, label_visibility="collapsed")

    st.write(" **SPO2**")
    st.slider("SPO2", 70, 100, key="spo2", on_change=send_update, label_visibility="collapsed")

    st.write(" **Noise Level**")
    st.slider("Noise", 30, 120, key="noise", on_change=send_update, label_visibility="collapsed")

    st.write(" **Room Light**")
    st.slider("Light", 0, 1000, key="light", on_change=send_update, label_visibility="collapsed")

    st.write(" **Bed Movement**")
    st.slider("Bed", 0, 100, key="bed", on_change=send_update, label_visibility="collapsed")

    st.subheader(" Quick Scenarios")
    
    st.button(" Normal Night", on_click=set_scenario, args=(72, 40, 300, 0), use_container_width=True)
    st.button(" Delirium / Agitated", on_click=set_scenario, args=(115, 85, 800, 65), use_container_width=True)
    st.button(" CODE BLUE", type="primary", on_click=set_scenario, kwargs={"hr": 160, "noise": 95, "light": 1000, "bed": 100, "spo2": 80}, use_container_width=True)
    
    st.markdown("---")

    with st.expander("🔌 Server Connection", expanded=True):
        server_ip = st.text_input("Server URL", value="http://172.16.17.193:5000")
        
        status_container = st.empty()

        col_con1, col_con2 = st.columns(2)
        
        with col_con1:
            if st.button("Connect", use_container_width=True):
                try:
                    if st.session_state.sio.connected:
                        st.session_state.sio.disconnect()
                    st.session_state.sio.connect(server_ip)
                    st.session_state.connected = True
                    st.success("Connected!")
                except Exception as e:
                    st.session_state.connected = False
                    st.error(f"Failed: {e}")

        with col_con2:
            if st.button("Disconnect", use_container_width=True):
                if st.session_state.sio.connected:
                    st.session_state.sio.disconnect()
                st.session_state.connected = False
                st.info("Disconnected.")

        if st.session_state.connected:
            status_container.success(f"✅ Status: ONLINE ({server_ip})")
        else:
            status_container.error("❌ Status: OFFLINE")
    
    st.markdown("---")