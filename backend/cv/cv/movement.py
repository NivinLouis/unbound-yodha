import numpy as np

class MovementAnalyzer:
    def __init__(self, threshold):
        self.prev_points = None
        self.motion_buffer = []
        self.threshold = threshold
        self.buffer_size = 12   # ~0.5 seconds of history

    def update(self, landmarks):
        # MediaPipe pose landmark indices
        LW, RW, LE, RE, LS, RS = 15, 16, 13, 14, 11, 12

        points = [
            landmarks[LW], landmarks[RW],
            landmarks[LE], landmarks[RE],
            landmarks[LS], landmarks[RS]
        ]

        coords = [(p.x, p.y) for p in points]

        motion = 0.0
        if self.prev_points is not None:
            for (x1, y1), (x2, y2) in zip(coords, self.prev_points):
                d = ((x1 - x2)**2 + (y1 - y2)**2) ** 0.5
                motion += d

        self.prev_points = coords

        # Smooth motion (moving average)
        self.motion_buffer.append(motion)
        if len(self.motion_buffer) > self.buffer_size:
            self.motion_buffer.pop(0)

        avg_motion = np.mean(self.motion_buffer)

        # Stronger weight to hands
        hand_motion = 0
        if self.prev_points:
            for i in [0,1]:  # wrists
                x1,y1 = coords[i]
                x2,y2 = self.prev_points[i]
                hand_motion += ((x1-x2)**2 + (y1-y2)**2) ** 0.5

        agitation_score = avg_motion * 0.6 + hand_motion * 0.4

        is_agitated = agitation_score > self.threshold

        # Body centroid
        xs = [p.x for p in landmarks]
        ys = [p.y for p in landmarks]
        cx = float(np.mean(xs))
        cy = float(np.mean(ys))

        return is_agitated, (cx, cy)
