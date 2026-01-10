def check_fall(cx, cy, frame_w, frame_h, margin):
    x1 = frame_w * margin
    x2 = frame_w * (1 - margin)
    y1 = frame_h * margin
    y2 = frame_h * (1 - margin)

    px = cx * frame_w
    py = cy * frame_h

    inside = x1 < px < x2 and y1 < py < y2
    return not inside
