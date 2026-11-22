"""Yellowstone Bear Report - 800x480 black & white image for an e-paper frame.

Left: pen-sketch map of Yellowstone with this season's bear sightings as dots.
Right: denning countdown / season stats / last bear seen.

  python bear_report.py                         # live iNaturalist data
  python bear_report.py --sample --date 2026-12-25
Writes out/frame.png
"""
import argparse, datetime as dt, json, math, os, random, urllib.request
from PIL import Image, ImageDraw, ImageFont
import sketch as sk

W, H, SPLIT = 800, 480, 470
HERE = os.path.dirname(os.path.abspath(__file__))
BOUNDARY = os.path.join(HERE, "data", "yell.geojson")   # NPS official boundary
SPRING, DEN_START = (3, 15), (11, 15)                    # approx. emergence / denning

# A few landmarks for orientation (lat, lon)
LANDMARKS = [("Mammoth", 44.976, -110.700), ("Lamar Valley", 44.880, -110.170),
             ("Hayden Valley", 44.650, -110.470), ("Old Faithful", 44.460, -110.828),
             ("Yellowstone Lake", 44.420, -110.360)]

def font(name, size):
    return ImageFont.truetype(os.path.join(HERE, "fonts", name), size)
NP_BOLD, NP_REG = "national-park-latin-800-normal.woff", "national-park-latin-400-normal.woff"


# ---------------- data ----------------
def load_boundary():
    g = json.load(open(BOUNDARY))
    feat = g["features"][0] if "features" in g else g
    return [(lon, lat) for lon, lat in feat["geometry"]["coordinates"][0]]


def inside(pt, poly):
    x, y = pt; c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


PLACES = [("Mammoth", 44.976, -110.700), ("Lamar Valley", 44.880, -110.170), ("Hayden Valley", 44.650, -110.470),
          ("Old Faithful", 44.460, -110.828), ("Canyon", 44.735, -110.489), ("Tower Junction", 44.917, -110.416),
          ("Norris", 44.727, -110.703), ("Madison", 44.645, -110.861), ("West Thumb", 44.416, -110.573),
          ("Fishing Bridge", 44.565, -110.373), ("Dunraven Pass", 44.787, -110.453), ("Slough Creek", 44.948, -110.307),
          ("Northeast Entrance", 45.005, -110.010), ("Grant Village", 44.392, -110.556)]


def nearest_place(lon, lat):
    k = math.cos(math.radians(lat))
    name, dist = min(((n, math.hypot((lon - lo) * k, lat - la) * 111) for n, la, lo in PLACES), key=lambda t: t[1])
    return f"near {name}" if dist < 10 else "Yellowstone backcountry"


def to_sighting(date, taxon, lon, lat, poly):
    kind = "Grizzly" if taxon.startswith("Ursus arctos") else "Black bear" if taxon.startswith("Ursus americanus") else None
    if kind and date and lon is not None and inside((lon, lat), poly):
        return {"date": date, "kind": kind, "lon": lon, "lat": lat, "where": nearest_place(lon, lat)}


def fetch_sightings(year, poly):
    base = ("https://api.inaturalist.org/v1/observations?taxon_name=Ursus"
            "&swlat=44.13&swlng=-111.16&nelat=45.11&nelng=-109.82"
            f"&year={year}&per_page=200&order_by=observed_on&order=desc&geo=true")
    out, page = [], 1
    while page <= 10:
        req = urllib.request.Request(f"{base}&page={page}", headers={"User-Agent": "bear-report-frame"})
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.load(r)
        for o in j["results"]:
            c = (o.get("geojson") or {}).get("coordinates") or [None, None]
            s = to_sighting(o.get("observed_on"), (o.get("taxon") or {}).get("name", ""), c[0], c[1], poly)
            if s:
                out.append(s)
        if page * 200 >= j["total_results"]:
            break
        page += 1
    return out


def load_file(path, poly):
    rows = json.load(open(path))
    return [s for r in rows if (s := to_sighting(r["observed_on"], r["taxon"] or "", r["lon"], r["lat"], poly))]


def sample_sightings(poly):
    """Fake data clustered in the real bear hotspots, for layout testing."""
    rng = random.Random(4)
    hot = [(44.88, -110.17, 0.06), (44.65, -110.47, 0.05), (44.95, -110.35, 0.06),
           (44.75, -110.10, 0.07), (44.45, -110.55, 0.08), (44.60, -110.90, 0.08)]
    out = []
    while len(out) < 140:
        lat, lon, s = rng.choice(hot)
        p = (lon + rng.gauss(0, s * 1.3), lat + rng.gauss(0, s))
        if inside(p, poly):
            kind = "Grizzly" if rng.random() < 0.55 else "Black bear"
            out.append({"date": f"2026-{rng.randint(4,10):02d}-{rng.randint(1,28):02d}", "kind": kind,
                        "lon": p[0], "lat": p[1], "where": "x"})
    out.append({"date": "2026-10-31", "kind": "Grizzly", "lon": -110.47, "lat": 44.66, "where": "Hayden Valley"})
    return out


# ---------------- left: sketch map ----------------
def make_projection(poly, box):
    x0, y0, x1, y1 = box
    lons = [p[0] for p in poly]; lats = [p[1] for p in poly]
    k = math.cos(math.radians(sum(lats) / len(lats)))
    sx = (x1 - x0) / ((max(lons) - min(lons)) * k)
    sy = (y1 - y0) / (max(lats) - min(lats))
    s = min(sx, sy)
    ox = x0 + ((x1 - x0) - (max(lons) - min(lons)) * k * s) / 2
    oy = y0 + ((y1 - y0) - (max(lats) - min(lats)) * s) / 2
    return lambda lon, lat: (ox + (lon - min(lons)) * k * s, oy + (max(lats) - lat) * s)


def draw_map(img, poly, sightings, last):
    global PROJ
    random.seed(11)
    d = ImageDraw.Draw(img)
    proj = make_projection(poly, (30, 62, SPLIT - 30, H - 46))
    PROJ = proj
    pts = [proj(*p) for p in poly[::12]] + [proj(*poly[0])]

    # title cartouche
    t = "YELLOWSTONE"

    # engraved look: light hatching outside the park, boundary drawn twice
    outside = sk.poly_mask(img.size, [(0, 0), (SPLIT, 0), (SPLIT, H), (0, H)])
    park = sk.poly_mask(img.size, pts)
    from PIL import ImageChops
    sk.hatch(img, ImageChops.subtract(outside, park), angle=45, spacing=9, gaps=0.5)
    d.polygon(pts, fill=255)
    sk.stroke(d, pts, width=2, passes=2, amp=0.8)
    d.rectangle([110, 12, SPLIT - 110, 48], fill=255)
    d.rectangle([24, H - 40, 280, H - 12], fill=255)
    d.text((SPLIT / 2, 30), t, font=font(NP_BOLD, 30), fill=0, anchor="mm")

    # sightings: grizzly = filled dot, black bear = open dot; older ones shrink and fade
    ref = dt.date.fromisoformat(last["date"]) if last else None
    for s in sorted(sightings, key=lambda s: s["date"]):
        if s is last:
            continue  # drawn in red later
        x, y = proj(s["lon"], s["lat"])
        age = (ref - dt.date.fromisoformat(s["date"])).days
        r = 4 if age <= 30 else 3 if age <= 90 else 2.2
        box = [x - r, y - r, x + r, y + r]
        if s["kind"] == "Grizzly":
            if age <= 90:
                d.ellipse(box, fill=0)
            else:  # faded: 50% stipple
                for px in range(int(x - r), int(x + r) + 1):
                    for py in range(int(y - r), int(y + r) + 1):
                        if (px + py) % 2 == 0 and (px - x) ** 2 + (py - y) ** 2 <= r * r:
                            d.point((px, py), fill=0)
        else:
            d.ellipse(box, fill=255, outline=0, width=1 if age > 30 else 2)

    # landmarks
    for name, lat, lon in LANDMARKS:
        x, y = proj(lon, lat)
        if name == "Yellowstone Lake":
            for i in range(3):   # little wave marks
                yy = y - 8 + i * 7
                d.line(sk.wobble([(x - 14, yy), (x - 5, yy - 3), (x + 4, yy), (x + 13, yy - 3)], 0.4, 4), fill=0, width=1)
            d.text((x, y + 16), name, font=font("DejaVuSerif-Italic.ttf", 12), fill=0, anchor="mm", stroke_width=3, stroke_fill=255)
            continue
        d.polygon([(x, y - 5), (x - 5, y + 4), (x + 5, y + 4)], fill=255, outline=0, width=2)
        d.text((x + 7, y - 1), name, font=font("DejaVuSerif-Italic.ttf", 12), fill=0, anchor="lm", stroke_width=3, stroke_fill=255)

    # legend + compass
    ly = H - 26
    d.ellipse([34, ly - 3, 40, ly + 3], fill=0)
    d.text((46, ly), "Grizzly", font=font("DejaVuSerif.ttf", 13), fill=0, anchor="lm")
    d.ellipse([112, ly - 3, 118, ly + 3], outline=0)
    d.text((124, ly), "Black bear", font=font("DejaVuSerif.ttf", 13), fill=0, anchor="lm")
    d.text((231, ly), "Latest", font=font("DejaVuSerif.ttf", 13), fill=0, anchor="lm")
    cx, cy = SPLIT - 40, H - 34
    d.polygon([(cx, cy - 16), (cx - 6, cy + 4), (cx, cy), (cx + 6, cy + 4)], fill=0)
    d.text((cx, cy - 24), "N", font=font(NP_BOLD, 14), fill=0, anchor="mm")


# ---------------- right: stats panel ----------------
def draw_panel(img, today, sightings, last):
    d = ImageDraw.Draw(img)
    x = SPLIT + 24
    sign = [(x - 6, 18), (W - 18, 18), (W - 18, 102), (x - 6, 102)]
    sk.hatch(img, sk.poly_mask(img.size, sign), angle=10, spacing=2.2, gaps=0.02)
    d.rectangle([x + 2, 26, W - 26, 94], fill=0)
    d.text((x + 14, 30), "BEAR", font=font(NP_BOLD, 34), fill=255)
    d.text((x + 14, 64), "REPORT", font=font(NP_BOLD, 24), fill=255)
    sk.stroke(d, sign + [sign[0]], width=2, passes=1)

    d.text((x, 116), today.strftime("%A, %B %-d"), font=font("DejaVuSerif.ttf", 17), fill=0)
    sk.stroke(d, [(x, 144), (W - 24, 144)], width=1)

    denning = (today.month, today.day) >= DEN_START or (today.month, today.day) < SPRING
    big = font(NP_BOLD, 64)
    if denning:
        spring = dt.date(today.year + (today.month >= DEN_START[0]), *SPRING)
        num, label, head = (spring - today).days, "days until\nbears wake", "DENNING SEASON"
    else:
        num, label, head = len(sightings), "sightings\nthis year", "BEARS ARE OUT"
    d.text((x, 156), head, font=font("DejaVuSans-Bold.ttf", 14), fill=0)
    d.text((x, 170), str(num), font=big, fill=0)
    d.text((x + 14 + d.textlength(str(num), font=big), 190), label, font=font("DejaVuSerif.ttf", 17), fill=0)

    grizz = sum(s["kind"] == "Grizzly" for s in sightings)
    black = len(sightings) - grizz
    d.text((x, 262), "This season", font=font("DejaVuSans-Bold.ttf", 14), fill=0)
    top = max(grizz, black, 1)
    for i, (lab, n, dense) in enumerate([("Grizzly", grizz, True), ("Black bear", black, False)]):
        yy = 286 + i * 30
        d.text((x, yy), lab, font=font("DejaVuSerif.ttf", 16), fill=0)
        bw = int(110 * n / top)
        bar = [(x + 100, yy + 3), (x + 100 + bw, yy + 3), (x + 100 + bw, yy + 17), (x + 100, yy + 17)]
        if dense:
            d.polygon(bar, fill=0)
        else:
            sk.hatch(img, sk.poly_mask(img.size, bar), angle=45, spacing=3.5, gaps=0.02)
            sk.stroke(d, bar + [bar[0]], width=1, passes=1, amp=0.5)
        d.text((x + 108 + bw, yy), str(n), font=font("DejaVuSans-Bold.ttf", 15), fill=0)

    sk.stroke(d, [(x, 356), (W - 24, 356)], width=1)
    if last:
        ld = dt.date.fromisoformat(last["date"])
        d.text((x, 368), "LAST SEEN", font=font("DejaVuSans-Bold.ttf", 14), fill=0)
        d.text((x, 388), f"{last['kind']} · {ld.strftime('%b %-d')}", font=font("DejaVuSerif-Bold.ttf", 21), fill=0)
        d.text((x, 416), last["where"][:28], font=font("DejaVuSerif-Italic.ttf", 17), fill=0)
    d.text((x, 454), "sightings via iNaturalist", font=font("DejaVuSans.ttf", 11), fill=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--date")
    ap.add_argument("--file", help="saved sightings JSON instead of live fetch")
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    year = today.year if today.month > 3 else today.year - 1
    poly = load_boundary()
    if a.file:
        sightings = load_file(a.file, poly)
    else:
        sightings = sample_sightings(poly) if a.sample else fetch_sightings(year, poly)
    last = max(sightings, key=lambda s: s["date"]) if sightings else None

    img = Image.new("L", (W, H), 255)
    draw_map(img, poly, sightings, last)
    sk.stroke(ImageDraw.Draw(img), [(SPLIT, 14), (SPLIT, H - 14)], width=1)
    draw_panel(img, today, sightings, last)

    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    out = img.point(lambda v: 0 if v < 128 else 255).convert("RGB")
    d = ImageDraw.Draw(out)
    RED = (255, 0, 0)
    ly = H - 26
    d.ellipse([212, ly - 5, 222, ly + 5], fill=RED)
    d.ellipse([207, ly - 9, 227, ly + 9], outline=RED, width=2)
    if last:
        x, y = PROJ(last["lon"], last["lat"])
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=RED)
        d.ellipse([x - 11, y - 11, x + 11, y + 11], outline=RED, width=2)
        d.text((SPLIT + 24, 368), "LAST SEEN", font=font("DejaVuSans-Bold.ttf", 14), fill=RED)
    out.save(os.path.join(HERE, "out", "frame.png"))
    print(f"{today}: {len(sightings)} sightings -> out/frame.png")


if __name__ == "__main__":
    main()
