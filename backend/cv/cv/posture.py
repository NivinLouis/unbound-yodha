import mediapipe as mp

mp_pose = mp.solutions.pose

def get_posture(landmarks):
    nose = landmarks[mp_pose.PoseLandmark.NOSE]
    left = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    right = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]

    shoulder_y = (left.y + right.y) / 2

    if abs(nose.y - shoulder_y) < 0.05:
        return "Sitting"
    return "Supine"


def get_eyes_status(landmarks):
    nose = landmarks[0]
    left_shoulder = landmarks[11]
    right_shoulder = landmarks[12]

    shoulder_y = (left_shoulder.y + right_shoulder.y) / 2

    # If head is lifted relative to shoulders → eyes open
    if nose.y < shoulder_y - 0.05:
        return "Open"
    else:
        return "Closed"


