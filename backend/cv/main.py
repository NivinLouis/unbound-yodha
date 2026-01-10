import cv2
import time
import base64
import requests
import mediapipe as mp

from config import SEND_INTERVAL, AGITATION_THRESHOLD, BED_MARGIN, SERVER_URL
from cv.pose import PoseDetector
from cv.movement import MovementAnalyzer
from cv.posture import get_posture
from cv.fall import check_fall
from utils.sender import send_to_server

# ---------------- CAMERA ----------------
# Try 0, 1, 2 until you see your phone feed
cap = cv2.VideoCapture(0)

# ---------------- MediaPipe ----------------
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

pose_detector = PoseDetector()
movement = MovementAnalyzer(AGITATION_THRESHOLD)

last_json_time = time.time()
last_frame_time = 0

print("📡 ICU LIVE CAMERA STARTED...")


# ---------------- Send RAW CCTV Frame ----------------
def send_frame(raw_frame):
    try:
        raw_frame = cv2.resize(raw_frame, (640, 360))
        _, buffer = cv2.imencode(".jpg", raw_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 25])
        jpg = base64.b64encode(buffer).decode("utf-8")

        requests.post(
            SERVER_URL.replace("/cv-data", "/video"),
            json={"frame": jpg},
            timeout=0.1
        )
    except:
        pass


# ---------------- Main Loop ----------------
while True:
    ret, frame = cap.read()
    if not ret:
        continue

    h, w, _ = frame.shape

    # Keep raw CCTV clean
    raw_frame = frame.copy()

    landmarks = pose_detector.get_landmarks(frame)

    if landmarks:
        is_agitated, (cx, cy) = movement.update(landmarks)
        posture = get_posture(landmarks)
        fall_risk = check_fall(cx, cy, w, h, BED_MARGIN)

        # Demo eyes logic
        eyes = "Open" if is_agitated else "Closed"

        # ---- Send JSON ----
        if time.time() - last_json_time > SEND_INTERVAL:
            payload = {
                "is_agitated": bool(is_agitated),
                "posture": str(posture),
                "eyes_status": str(eyes),
                "fall_risk": bool(fall_risk)
            }
            send_to_server(payload)
            last_json_time = time.time()

        # ---- Display frame (AI view) ----
        display_frame = frame.copy()

        # Bed box
        x1 = int(w * BED_MARGIN)
        y1 = int(h * BED_MARGIN)
        x2 = int(w * (1 - BED_MARGIN))
        y2 = int(h * (1 - BED_MARGIN))
        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0,255,0), 2)

        # Body center
        px = int(cx * w)
        py = int(cy * h)
        cv2.circle(display_frame, (px, py), 6, (0,0,255), -1)

        # Skeleton
        mp_drawing.draw_landmarks(
            display_frame,
            pose_detector.pose.process(
                cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ).pose_landmarks,
            mp_pose.POSE_CONNECTIONS
        )

        # Overlay text
        cv2.putText(display_frame, f"Agitated: {is_agitated}", (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
        cv2.putText(display_frame, f"Posture: {posture}", (10,60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,0,0), 2)
        cv2.putText(display_frame, f"Eyes: {eyes}", (10,90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        cv2.putText(display_frame, f"Fall Risk: {fall_risk}", (10,120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)

        cv2.imshow("ICU AI Vision (Local)", display_frame)

    # ---- Stream RAW CCTV to dashboard ----
    if time.time() - last_frame_time > 0.15:   # ~6 FPS
        send_frame(raw_frame)
        last_frame_time = time.time()

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
