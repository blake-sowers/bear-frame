"""Pen-and-ink sketch helpers: wobbly strokes and hatching clipped to shapes."""
import math, random
from PIL import Image, ImageDraw, ImageChops

INK = 0
PAPER = 255


def wobble(points, amp=1.2, step=6):
    """Resample a polyline and jitter it so it looks hand-drawn."""
    out = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
        for i in range(n):
            t = i / n
            out.append((x0 + (x1 - x0) * t + random.uniform(-amp, amp),
                        y0 + (y1 - y0) * t + random.uniform(-amp, amp)))
    out.append(points[-1])
    return out


def stroke(d, points, width=2, passes=2, amp=1.2):
    for _ in range(passes):
        d.line(wobble(points, amp), fill=INK, width=width, joint="curve")


def hatch(img, mask, angle=45, spacing=6, width=1, jitter=1.0, gaps=0.15):
    """Draw parallel sketchy lines over the whole canvas, keep only inside mask."""
    w, h = img.size
    layer = Image.new("L", (w, h), PAPER)
    ld = ImageDraw.Draw(layer)
    a = math.radians(angle)
    dx, dy = math.cos(a), math.sin(a)
    nx, ny = -dy, dx
    diag = math.hypot(w, h)
    k = -diag
    while k < diag:
        cx, cy = w / 2 + nx * k, h / 2 + ny * k
        p0 = (cx - dx * diag, cy - dy * diag)
        p1 = (cx + dx * diag, cy + dy * diag)
        # break the line into dashes with random gaps, like real pen strokes
        segs = int(diag / 25)
        for s in range(segs * 2):
            t0, t1 = s / (segs * 2), (s + 1) / (segs * 2)
            if random.random() < gaps:
                continue
            q0 = (p0[0] + (p1[0] - p0[0]) * t0, p0[1] + (p1[1] - p0[1]) * t0)
            q1 = (p0[0] + (p1[0] - p0[0]) * t1, p0[1] + (p1[1] - p0[1]) * t1)
            ld.line(wobble([q0, q1], jitter, 8), fill=INK, width=width)
        k += spacing + random.uniform(-spacing * 0.25, spacing * 0.25)
    inv_mask = ImageChops.invert(mask)
    layer = ImageChops.lighter(layer, inv_mask)      # white outside mask
    img.paste(ImageChops.darker(img, layer))


def poly_mask(size, pts):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m


def grass(d, x, y, n=5, h=10):
    for _ in range(n):
        gx = x + random.uniform(-6, 6)
        d.line([(gx, y), (gx + random.uniform(-4, 4), y - random.uniform(h * 0.5, h))], fill=INK, width=1)


def pine(d, x, base, h):
    """Sketchy pine: a trunk and zig-zag branches."""
    d.line([(x, base), (x, base - h)], fill=INK, width=1)
    rows = int(h / 4)
    for i in range(rows):
        y = base - h + i * 4 + 2
        span = (i + 1) / rows * h * 0.28
        d.line([(x - span, y + 3), (x, y), (x + span, y + 3)], fill=INK, width=1)
