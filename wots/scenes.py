"""Procedural animated backgrounds (all original code): night blue, purple and warm gold.
Each scene: Scene(rng, W, H, T).frame(t) -> float32 HxWx3 (0..1); optional .overlay(uint8 img, t)."""
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter

TAU = 2 * np.pi


# ---------- helpers ----------
def vnoise(h, w, cells, rng, octaves=5, persist=0.55):
    out = np.zeros((h, w), np.float32); amp = 1.0; tot = 0
    for o in range(octaves):
        ch = max(2, int(cells * 2 ** o * h / max(h, w))); cw = max(2, int(cells * 2 ** o * w / max(h, w)))
        g = rng.random((ch + 1, cw + 1)).astype(np.float32)
        out += cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC) * amp
        tot += amp; amp *= persist
    out /= tot
    out -= out.min(); out /= out.max() + 1e-9
    return out


def vgrad(h, w, stops):
    """stops: [(pos 0..1, (r,g,b) 0..255)]"""
    y = np.linspace(0, 1, h)
    cols = np.zeros((h, 3), np.float32)
    ps = [s[0] for s in stops]
    for c in range(3):
        cols[:, c] = np.interp(y, ps, [s[1][c] / 255 for s in stops])
    return np.repeat(cols[:, None, :], w, 1)


def radial(h, w, cx, cy, r):
    yy, xx = np.ogrid[:h, :w]
    return np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r))).astype(np.float32)


def sprite(r):
    s = int(r * 6) | 1
    yy, xx = np.mgrid[:s, :s] - s // 2
    return np.exp(-(xx ** 2 + yy ** 2) / (2 * r * r)).astype(np.float32)


def add_sprite(img, spr, x, y, col, k=1.0):
    s = spr.shape[0]; h = s // 2
    x0, y0 = int(x) - h, int(y) - h
    H, W = img.shape[:2]
    if x0 >= W or y0 >= H or x0 + s <= 0 or y0 + s <= 0:
        return
    a0, b0 = max(0, -y0), max(0, -x0)
    a1, b1 = s - max(0, y0 + s - H), s - max(0, x0 + s - W)
    img[y0 + a0:y0 + a1, x0 + b0:x0 + b1] += spr[a0:a1, b0:b1, None] * (np.array(col, np.float32) * k)


def jitter(rgb, rng, amt=14):
    return tuple(int(np.clip(c + rng.uniform(-amt, amt), 0, 255)) for c in rgb)


class Camera:
    """Slow zoom/drift over an oversized still layer."""
    def __init__(self, rng, W, H, T, zoom=(1.0, 1.07), rot=0.0):
        self.W, self.H, self.T = W, H, T
        self.z0, self.z1 = (zoom if rng.random() < 0.7 else zoom[::-1])
        self.dx = rng.uniform(-0.02, 0.02) * W; self.dy = rng.uniform(-0.015, 0.015) * H
        self.rot = rot * rng.choice([-1, 1])

    def view(self, layer, t):
        H, W = self.H, self.W
        u = t / self.T; z = self.z0 + (self.z1 - self.z0) * (3 * u * u - 2 * u ** 3)
        lh, lw = layer.shape[:2]
        M = cv2.getRotationMatrix2D((lw / 2 + self.dx * u, lh / 2 + self.dy * u), self.rot * u, z)
        M[0, 2] += W / 2 - lw / 2; M[1, 2] += H / 2 - lh / 2
        return cv2.warpAffine(layer, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


class Stars:
    def __init__(self, rng, W, H, n=160, ymax=1.0, col=(255, 245, 225)):
        self.p = np.stack([rng.uniform(0, W, n), rng.uniform(0, H * ymax, n) ** 1.0], 1)
        self.p[:, 1] = H * ymax * rng.random(n) ** 1.35
        self.b = rng.uniform(0.25, 1.0, n); self.ph = rng.uniform(0, TAU, n); self.w = rng.uniform(0.6, 2.2, n)
        self.big = rng.random(n) < 0.12
        self.s1, self.s2 = sprite(1.3), sprite(2.6); self.col = col

    def static(self, img, rng, n=900, ymax=1.0):
        H, W = img.shape[:2]
        xs = rng.integers(0, W, n); ys = (H * ymax * rng.random(n) ** 1.2).astype(int).clip(0, H - 1)
        v = rng.uniform(0.08, 0.45, n)
        img[ys, xs] += v[:, None]

    def draw(self, img, t):
        k = 0.55 + 0.45 * np.sin(self.w * t + self.ph)
        for (x, y), b, kk, big in zip(self.p, self.b, k, self.big):
            add_sprite(img, self.s2 if big else self.s1, x, y, self.col, b * kk / 255 * (0.9 if big else 1.2))


class Dust:
    """Slow drifting warm particles (gold dust, fireflies, plankton)."""
    def __init__(self, rng, W, H, n=45, col=(255, 205, 120), r=(2.0, 4.5), vy=-12, blink=True, region=(0, 1)):
        self.W, self.H = W, H
        self.x = rng.uniform(0, W, n); self.y = rng.uniform(H * region[0], H * region[1], n)
        self.ax = rng.uniform(15, 60, n); self.fx = rng.uniform(0.05, 0.2, n); self.ph = rng.uniform(0, TAU, n)
        self.vy = rng.uniform(0.5, 1.5, n) * vy; self.blink = blink; self.col = col
        self.sp = [sprite(v) for v in rng.uniform(r[0], r[1], n)]
        self.a = rng.uniform(0.35, 1.0, n); self.region = region

    def draw(self, img, t):
        H = self.H
        lo, hi = H * self.region[0], H * self.region[1]
        for i in range(len(self.x)):
            x = self.x[i] + self.ax[i] * np.sin(self.fx[i] * TAU * t + self.ph[i])
            y = lo + (self.y[i] - lo + self.vy[i] * t) % (hi - lo)
            k = self.a[i] * ((0.5 + 0.5 * np.sin(1.3 * t + self.ph[i] * 3)) if self.blink else 1.0)
            add_sprite(img, self.sp[i], x, y, self.col, k / 255)


def ridge(rng, W, base, amp, rough=0.55, n=9):
    x = np.zeros(W)
    for o in range(n):
        cells = 2 ** o + 1
        g = rng.uniform(-1, 1, cells + 1)
        x += np.interp(np.linspace(0, cells, W), np.arange(cells + 1), g) * amp * rough ** o
    return base + x


def fill_below(h, w, ys):
    yy = np.arange(h)[:, None]
    return (yy >= ys[None, :]).astype(np.float32)


def soften(mask, k=3):
    return cv2.GaussianBlur(mask, (0, 0), k)


# ---------- scenes ----------
class Nebula:
    name = 'nebula'

    def __init__(self, rng, W, H, T):
        self.W, self.H, self.T = W, H, T
        LW, LH = int(W * 1.12), int(H * 1.12)
        top, mid, bot = jitter((6, 9, 34), rng, 6), jitter((24, 14, 58), rng, 8), jitter((44, 20, 78), rng, 10)
        bg = vgrad(LH, LW, [(0, top), (0.55, mid), (1, bot)])
        n1 = vnoise(LH, LW, 3, rng); n2 = vnoise(LH, LW, 4, rng); n3 = vnoise(LH, LW, 6, rng)
        cloud = np.clip((n1 * 0.7 + n3 * 0.3 - 0.42) * 2.3, 0, 1) ** 1.6
        purple = np.array(jitter((120, 60, 190), rng, 20), np.float32) / 255
        gold = np.array(jitter((235, 170, 95), rng, 15), np.float32) / 255
        mixk = np.clip((n2 - 0.35) * 2, 0, 1)[..., None]
        bg += cloud[..., None] * (purple * (1 - mixk) + gold * mixk) * 0.55
        self.st = Stars(rng, W, H, n=150)
        self.st.static(bg, rng, n=2600)
        cx, cy = rng.uniform(0.35, 0.65) * LW, rng.uniform(0.30, 0.48) * LH
        self.has_light = rng.random() < 0.6
        if self.has_light:
            bg += radial(LH, LW, cx, cy, LW * 0.22)[..., None] * gold * 0.35
        self.layer = bg
        self.cam = Camera(rng, W, H, T, zoom=(1.0, 1.09), rot=2.5)
        self.light = (cx, cy)
        self.dust = Dust(rng, W, H, n=35, col=(255, 210, 140), vy=-8)
        self.gold = gold
        self.pulse = radial(H, W, cx - (LW - W) / 2, cy - (LH - H) / 2, W * 0.12)[..., None] * gold if self.has_light else None

    def frame(self, t):
        f = self.cam.view(self.layer, t)
        if self.has_light:
            f += self.pulse * (0.10 + 0.06 * np.sin(TAU * t / 7))
        self.st.draw(f, t); self.dust.draw(f, t)
        return f


class MoonSea:
    name = 'moonsea'

    def __init__(self, rng, W, H, T):
        self.W, self.H, self.T = W, H, T
        hz_y = int(H * rng.uniform(0.56, 0.62)); self.hz = hz_y
        sky = vgrad(hz_y, W, [(0, jitter((5, 8, 30), rng, 5)), (0.6, jitter((22, 18, 60), rng, 8)), (1, jitter((70, 45, 95), rng, 12))])
        sea = vgrad(H - hz_y, W, [(0, jitter((30, 30, 70), rng, 8)), (0.25, (12, 20, 52)), (1, (4, 8, 24))])
        bg = np.concatenate([sky, sea], 0)
        self.mx = rng.uniform(0.3, 0.7) * W; self.my = rng.uniform(0.2, 0.32) * H
        moon_col = np.array(jitter((255, 236, 200), rng, 8), np.float32) / 255
        bg[:hz_y] += radial(hz_y, W, self.mx, self.my, 260)[..., None] * moon_col * 0.28
        disc = np.clip(60 - np.sqrt((np.arange(W)[None, :] - self.mx) ** 2 + (np.arange(hz_y)[:, None] - self.my) ** 2), 0, 1.5) / 1.5
        tex = vnoise(hz_y, W, 40, rng, 3) * 0.12
        bg[:hz_y] = bg[:hz_y] * (1 - disc[..., None]) + (moon_col * (0.92 - tex[..., None])) * disc[..., None]
        clouds = vnoise(hz_y, W, 3, rng); cl = np.clip((clouds - 0.6) * 2.5, 0, 1)[..., None] * 0.18
        bg[:hz_y] = bg[:hz_y] * (1 - cl) + np.array([0.25, 0.2, 0.35]) * cl
        self.st = Stars(rng, W, hz_y, n=110, ymax=0.85)
        self.st.static(bg[:hz_y], rng, n=1400, ymax=0.9)
        # moon path glow on the water
        yy = np.arange(H - hz_y)[:, None]; xx = np.arange(W)[None, :]
        spread = 40 + yy * 0.9
        path = np.exp(-((xx - self.mx) ** 2) / (2 * spread ** 2)) * np.exp(-yy / (H * 0.5))
        bg[hz_y:] += path[..., None] * moon_col * 0.22
        self.layer = bg
        n = 1700
        d = rng.random(n) ** 1.6
        self.gy = hz_y + 4 + d * (H - hz_y - 4)
        sp = 30 + (self.gy - hz_y) * 0.95
        self.gx = self.mx + rng.standard_normal(n) * sp * 0.9
        self.gl = (3 + (self.gy - hz_y) * 0.06 * rng.uniform(0.5, 1.5, n)).astype(int)
        self.gw = rng.uniform(0.8, 2.5, n); self.gp = rng.uniform(0, TAU, n)
        self.gk = np.exp(-np.abs(self.gx - self.mx) / (sp * 1.4)) * rng.uniform(0.4, 1, n)
        self.moon_col = moon_col
        self.cam = Camera(rng, W, H, T, zoom=(1.0, 1.035))

    def frame(self, t):
        f = self.layer.copy()
        self.st.draw(f[:self.hz], t)
        k = np.clip(np.sin(self.gw * t + self.gp), 0, 1) ** 3 * self.gk * 0.55
        H, W = self.H, self.W
        for x, y, l, kk in zip(self.gx.astype(int), self.gy.astype(int), self.gl, k):
            if kk < 0.02 or y >= H - 1 or x < 0 or x + l >= W:
                continue
            f[y:y + 2, x:x + l] += self.moon_col * kk
        return self.cam.view(f, t)


def _tree_layer(rng, W, H, base, height, dens, kind):
    img = Image.new('L', (W, H), 0); d = ImageDraw.Draw(img)
    x = -40
    while x < W + 40:
        h = height * rng.uniform(0.6, 1.25); y0 = base + rng.uniform(-15, 15)
        if kind == 'pine' or (kind == 'mix' and rng.random() < 0.6):
            w = h * rng.uniform(0.28, 0.4); tiers = rng.integers(5, 9)
            for i in range(tiers):
                ty = y0 - h * i / tiers; tw = w * (1 - i / tiers) * 1.1
                d.polygon([(x - tw / 2, ty), (x + tw / 2, ty), (x, ty - h / tiers * 1.9)], fill=255)
            d.rectangle([x - 3, y0 - 6, x + 3, H], fill=255)
        else:
            r = h * 0.28
            for _ in range(7):
                d.ellipse([x - r + rng.uniform(-r, r) * 0.7, y0 - h + rng.uniform(0, h * 0.5), x + r + rng.uniform(-r, r) * 0.7, y0 - h * 0.35 + rng.uniform(0, h * 0.3)], fill=255)
            d.rectangle([x - 5, y0 - h * 0.45, x + 5, H], fill=255)
        x += height * dens * rng.uniform(0.3, 0.9)
    d.rectangle([0, base, W, H], fill=255)
    return np.asarray(img, np.float32) / 255


class Forest:
    name = 'forest'

    def __init__(self, rng, W, H, T):
        self.W, self.H, self.T = W, H, T
        LW, LH = int(W * 1.1), int(H * 1.1)
        warm = jitter((215, 140, 90), rng, 20)
        bg = vgrad(LH, LW, [(0, jitter((8, 10, 36), rng, 5)), (0.35, jitter((32, 24, 70), rng, 8)), (0.62, jitter((110, 70, 110), rng, 12)), (0.72, warm), (1, (30, 20, 40))])
        Stars(rng, W, H).static(bg, rng, n=900, ymax=0.3)
        gx = rng.uniform(0.3, 0.7) * LW
        bg += radial(LH, LW, gx, LH * 0.68, LW * 0.3)[..., None] * np.array(warm, np.float32) / 255 * 0.3
        kind = rng.choice(['pine', 'mix'])
        layers = [(0.60, 300, (95, 70, 115)), (0.66, 380, (58, 42, 82)), (0.74, 470, (30, 22, 50)), (0.84, 620, (10, 8, 20))]
        fog = vnoise(LH, LW, 4, rng)
        for i, (b, h, c) in enumerate(layers):
            m = soften(_tree_layer(rng, LW, LH, LH * b, h * LH / 2112, 0.55, kind), 1.2 if i else 2.0)
            col = np.array(jitter(c, rng, 6), np.float32) / 255
            bg = bg * (1 - m[..., None]) + col * m[..., None]
            if i < 3:
                band = np.exp(-((np.arange(LH)[:, None] - LH * (b + 0.03)) ** 2) / (2 * (LH * 0.035) ** 2))
                fm = (band * (0.4 + 0.6 * fog))[..., None] * 0.22
                bg = bg * (1 - fm) + np.array([0.55, 0.45, 0.65]) * fm
        self.layer = bg
        self.cam = Camera(rng, W, H, T, zoom=(1.0, 1.06))
        self.ff = Dust(rng, W, H, n=38, col=(255, 200, 100), r=(2.2, 5.0), vy=-4, region=(0.5, 0.95))

    def frame(self, t):
        f = self.cam.view(self.layer, t)
        self.ff.draw(f, t)
        return f


class Aurora:
    name = 'aurora'

    def __init__(self, rng, W, H, T):
        self.W, self.H, self.T = W, H, T
        bg = vgrad(H, W, [(0, jitter((4, 6, 26), rng, 4)), (0.6, jitter((16, 14, 50), rng, 6)), (1, (20, 14, 40))])
        self.st = Stars(rng, W, H, n=130, ymax=0.7)
        self.st.static(bg, rng, n=2000, ymax=0.75)
        self.bg = bg
        r1 = ridge(rng, W, H * rng.uniform(0.62, 0.68), H * 0.06)
        r2 = ridge(rng, W, H * rng.uniform(0.72, 0.78), H * 0.05)
        m1 = soften(fill_below(H, W, r1), 1.0); m2 = soften(fill_below(H, W, r2), 1.0)
        self.m1, self.m2 = m1[..., None], m2[..., None]
        self.c1 = np.array(jitter((24, 18, 46), rng, 5), np.float32) / 255
        self.c2 = np.array((10, 8, 22), np.float32) / 255
        self.lw, self.lh = W // 4, H // 4
        self.n = rng.integers(2, 4)
        self.par = [(rng.uniform(0.40, 0.55), rng.uniform(0.02, 0.05), rng.uniform(1.5, 4), rng.uniform(0.05, 0.15), rng.uniform(0, TAU)) for _ in range(self.n)]
        cols = [(110, 80, 220), (70, 200, 190), (210, 120, 220), (240, 190, 120)]
        idx = rng.permutation(len(cols))[:self.n]
        self.cols = [np.array(cols[i], np.float32) / 255 for i in idx]
        self.tex = vnoise(self.lh, self.lw * 3, 12, rng, 3)

    def frame(self, t):
        lh, lw = self.lh, self.lw
        yy = np.arange(lh)[:, None] / lh; xx = np.arange(lw)[None, :] / lw
        acc = np.zeros((lh, lw, 3), np.float32)
        for (base, amp, k, w, ph), col in zip(self.par, self.cols):
            curve = base + amp * np.sin(TAU * k * xx + w * TAU * t + ph) + amp * 0.5 * np.sin(TAU * 2.3 * k * xx - 0.7 * w * TAU * t)
            dy = curve - yy                       # >0 above the lower edge
            prof = np.where(dy > 0, np.exp(-dy / 0.16), np.exp(dy / 0.01))
            sh = int(t * 6) % (lw * 2)
            rays = 0.6 + 0.4 * self.tex[:, sh:sh + lw]
            acc += (prof * rays)[..., None] * col * (0.75 + 0.25 * np.sin(TAU * t / 9 + ph))
        au = cv2.resize(acc, (self.W, self.H), interpolation=cv2.INTER_CUBIC)
        f = self.bg + au * 0.55
        self.st.draw(f, t)
        f = f * (1 - self.m1) + (self.c1 + au * 0.05) * self.m1
        f = f * (1 - self.m2) + self.c2 * self.m2
        return f


def feather_sprite(rng, h=900, gold=(240, 200, 130)):
    S = 2; W, H = int(h * 0.42) * S, h * S
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    bend = rng.uniform(0.05, 0.12) * W
    def rach(u):
        return W / 2 + bend * np.sin(np.pi * u) - bend * 0.5, H * 0.04 + u * H * 0.92
    gold = np.array(gold); white = np.array([255, 250, 240])
    for side in (-1, 1):
        for i in range(int(420 * S)):
            u = 0.06 + 0.8 * i / (420 * S)
            x, y = rach(u)
            wid = W * 0.46 * np.sin(np.pi * min(1, (u - 0.04) / 0.86)) ** 0.7 * (0.85 + 0.15 * rng.random())
            ang = np.radians(rng.uniform(52, 62))
            ex, ey = x + side * wid * np.sin(ang), y - wid * np.cos(ang) * 0.6
            c = (gold * (1 - u) + white * u).clip(0, 255)
            if rng.random() < 0.025:      # little natural gaps in the vane
                continue
            d.line([(x, y), (ex, ey)], fill=tuple(int(v) for v in c) + (int(185 + 70 * rng.random()),), width=2 * S)
    pts = [rach(u) for u in np.linspace(0, 1, 60)]
    d.line(pts, fill=(255, 245, 225, 255), width=3 * S)
    img = img.filter(ImageFilter.GaussianBlur(0.6 * S)).resize((W // S, H // S), Image.LANCZOS)
    a = np.asarray(img, np.float32) / 255
    return a


class Feather:
    name = 'feather'

    def __init__(self, rng, W, H, T):
        self.W, self.H, self.T = W, H, T
        LW, LH = int(W * 1.08), int(H * 1.08)
        bg = vgrad(LH, LW, [(0, jitter((8, 8, 32), rng, 5)), (0.5, jitter((30, 16, 62), rng, 8)), (1, jitter((14, 10, 38), rng, 6))])
        for _ in range(26):                                     # soft bokeh
            r = rng.uniform(20, 75); x, y = rng.uniform(0, LW), rng.uniform(0, LH)
            c = np.array(jitter((200, 150, 220) if rng.random() < 0.5 else (240, 190, 120), rng, 20), np.float32) / 255
            bg += radial(LH, LW, x, y, r)[..., None] * c * rng.uniform(0.05, 0.14)
        self.cx, self.cy = W * rng.uniform(0.42, 0.56), H * rng.uniform(0.69, 0.72)   # below the caption zone
        self.layer = bg
        self.cam = Camera(rng, W, H, T, zoom=(1.0, 1.05))
        self.halo = radial(H, W, self.cx, self.cy, 230)[..., None]
        self.core = radial(H, W, self.cx, self.cy, 55)[..., None]
        self.warm = np.array(jitter((255, 205, 130), rng, 10), np.float32) / 255
        fh = int(H * rng.uniform(0.22, 0.26))
        self.fe = feather_sprite(rng, fh)
        self.orbit = rng.uniform(130, 170); self.a0 = rng.uniform(0, TAU); self.av = rng.choice([-1, 1]) * rng.uniform(0.05, 0.09)
        self.dust = Dust(rng, W, H, n=40, col=(255, 215, 150), vy=-10)

    def frame(self, t):
        f = self.cam.view(self.layer, t)
        p = 1 + 0.12 * np.sin(TAU * t / 6.5)
        f += self.halo * self.warm * 0.42 * p + self.core * np.array([1, 0.95, 0.85], np.float32) * 0.75 * p
        a = self.a0 + self.av * TAU * t
        fx = self.cx + self.orbit * np.cos(a) * 0.9; fy = self.cy + self.orbit * np.sin(a) * 0.55 + 15 * np.sin(TAU * t / 8)
        ang = np.degrees(a) + 90 + 12 * np.sin(TAU * t / 5)
        fh, fw = self.fe.shape[:2]
        S = int(max(fh, fw) * 1.1)
        canvas = np.zeros((S, S, 4), np.float32)
        oy, ox = (S - fh) // 2, (S - fw) // 2
        canvas[oy:oy + fh, ox:ox + fw] = self.fe
        M = cv2.getRotationMatrix2D((S / 2, S / 2), -ang * 0.35, 1.0)
        rot = cv2.warpAffine(canvas, M, (S, S), flags=cv2.INTER_LINEAR)
        x0, y0 = int(fx - S / 2), int(fy - S / 2)
        H, W = self.H, self.W
        a0, b0 = max(0, -y0), max(0, -x0); a1, b1 = min(S, H - y0), min(S, W - x0)
        if a1 > a0 and b1 > b0:
            sub = rot[a0:a1, b0:b1]; al = sub[..., 3:4]
            glow = cv2.GaussianBlur(al, (0, 0), 9)[..., None] if al.ndim == 3 else None
            reg = f[y0 + a0:y0 + a1, x0 + b0:x0 + b1]
            f[y0 + a0:y0 + a1, x0 + b0:x0 + b1] = reg * (1 - al) + sub[..., :3] * al + glow * self.warm * 0.35
        self.dust.draw(f, t)
        return f


class DawnClouds:
    name = 'dawnclouds'

    def __init__(self, rng, W, H, T):
        self.W, self.H, self.T = W, H, T
        warm = jitter((245, 180, 110), rng, 12)
        self.bg = vgrad(H, W, [(0, jitter((14, 12, 46), rng, 6)), (0.35, jitter((60, 36, 96), rng, 10)), (0.62, jitter((140, 84, 120), rng, 15)), (0.8, warm), (1, jitter((90, 50, 90), rng, 10))])
        self.sx, self.sy = W * rng.uniform(0.3, 0.7), H * rng.uniform(0.62, 0.72)
        self.warm = np.array(warm, np.float32) / 255
        self.bg += radial(H, W, self.sx, self.sy, 260)[..., None] * self.warm * 0.32
        self.lw, self.lh = W // 3, H // 3
        self.c1 = vnoise(self.lh, self.lw * 2, 5, rng); self.c2 = vnoise(self.lh, self.lw * 2, 7, rng)
        yy, xx = np.mgrid[:self.lh, :self.lw]
        self.ang = np.arctan2(yy - self.sy / 3, xx - self.sx / 3); self.dist = np.hypot(yy - self.sy / 3, xx - self.sx / 3)
        self.rayn = rng.uniform(0, 1, 64); self.rot = rng.choice([-1, 1]) * 0.012
        self.cloudcol = np.array(jitter((235, 175, 190), rng, 15), np.float32) / 255
        self.shade = np.array(jitter((60, 40, 90), rng, 10), np.float32) / 255

    def frame(self, t):
        lw = self.lw
        a = (self.ang + self.rot * t) % TAU
        i = (a / TAU * 64)
        r = np.interp(i, np.arange(65), np.append(self.rayn, self.rayn[0]))
        rays = (r ** 4) * np.exp(-self.dist / (self.lh * 0.35)) * 0.16
        s1 = int(t * 3) % lw; s2 = int(t * 6) % lw
        c1 = np.clip((self.c1[:, s1:s1 + lw] - 0.45) * 3, 0, 1); c2 = np.clip((self.c2[:, s2:s2 + lw] - 0.5) * 3, 0, 1)
        yy = np.arange(self.lh)[:, None] / self.lh
        band = np.clip(1 - np.abs(yy - 0.45) / 0.4, 0, 1)
        cl = np.clip((c1 * 0.7 + c2 * 0.5) * band, 0, 1)
        low = np.dstack([rays, cl])
        up = cv2.resize(low, (self.W, self.H), interpolation=cv2.INTER_CUBIC)
        f = self.bg + up[..., :1] * self.warm
        lit = (self.cloudcol * (0.55 + 0.45 * np.exp(-np.abs(np.arange(self.H)[:, None, None] - self.sy) / 500)))
        m = up[..., 1:2] * 0.85
        f = f * (1 - m) + (lit * 0.8 + self.shade * 0.2) * m
        return f


class Birds:
    name = 'birds'

    def __init__(self, rng, W, H, T):
        self.W, self.H, self.T = W, H, T
        warm = jitter((240, 165, 95), rng, 12)
        bg = vgrad(H, W, [(0, jitter((12, 12, 44), rng, 6)), (0.4, jitter((70, 42, 100), rng, 10)), (0.66, warm), (1, (40, 25, 50))])
        sx = W * rng.uniform(0.3, 0.7)
        bg += radial(H, W, sx, H * 0.68, 220)[..., None] * np.array(warm, np.float32) / 255 * 0.45
        bg += radial(H, W, sx, H * 0.68, 40)[..., None] * 0.9
        for i, (b, a, c) in enumerate([(0.68, 0.05, (80, 50, 90)), (0.75, 0.05, (40, 26, 56)), (0.84, 0.04, (14, 10, 24))]):
            m = soften(fill_below(H, W, ridge(rng, W, H * b, H * a)), 1.0)[..., None]
            bg = bg * (1 - m) + np.array(jitter(c, rng, 6), np.float32) / 255 * m
        Stars(rng, W, H).static(bg, rng, n=500, ymax=0.25)
        self.layer = bg
        self.cam = Camera(rng, W, H, T, zoom=(1.0, 1.04))
        n = int(rng.integers(6, 12))
        self.dir = rng.choice([-1, 1])
        self.speed = rng.uniform(22, 36)
        lead_y = H * rng.uniform(0.30, 0.45)
        self.birds = []
        for i in range(n):
            row = i // 2 + 1; side = 1 if i % 2 else -1
            self.birds.append((-self.dir * row * rng.uniform(80, 110), lead_y + side * row * rng.uniform(40, 60) + rng.uniform(-10, 10),
                               rng.uniform(22, 32), rng.uniform(1.6, 2.4), rng.uniform(0, TAU)))
        self.x0 = W * 0.5 - self.dir * self.speed * T * 0.5

    def frame(self, t):
        return self.cam.view(self.layer, t)

    def overlay(self, img, t):
        lx = self.x0 + self.dir * self.speed * t
        for dx, y, s, w, ph in self.birds:
            x = lx + dx; yb = y + 6 * np.sin(0.6 * t + ph)
            flap = np.sin(TAU * w * t / 2 + ph)
            wy = -s * 0.55 * flap; tip = s * 0.25 * flap
            pts = np.array([[x - s, yb + wy + tip], [x - s * 0.45, yb + wy * 0.55], [x, yb + 2], [x + s * 0.45, yb + wy * 0.55], [x + s, yb + wy + tip]], np.int32)
            cv2.polylines(img, [pts], False, (18, 12, 26), 4, cv2.LINE_AA)


class Whale:
    name = 'whale'

    def __init__(self, rng, W, H, T):
        self.W, self.H, self.T = W, H, T
        self.bg = vgrad(H, W, [(0, jitter((40, 70, 120), rng, 10)), (0.25, jitter((18, 36, 84), rng, 8)), (0.7, (8, 14, 44)), (1, (4, 6, 22))])
        self.bg += radial(H, W, W * rng.uniform(0.3, 0.7), -100, 600)[..., None] * np.array([0.9, 0.8, 0.55], np.float32) * 0.35
        self.lw, self.lh = W // 4, H // 4
        self.r1 = np.interp(np.arange(self.lw * 4), np.linspace(0, self.lw * 4, 60), rng.random(60)) ** 3
        self.dust = Dust(rng, W, H, n=70, col=(200, 220, 255), r=(1.2, 2.6), vy=-6, blink=False)
        self.dir = rng.choice([-1, 1]); self.y = H * rng.uniform(0.52, 0.62)
        self.L = W * rng.uniform(0.85, 1.05); self.v = rng.uniform(0.55, 0.75) * (W + self.L) / T
        self.x0 = W / 2 - self.dir * self.v * T / 2
        u = np.linspace(0, 1, 80)
        top = 0.19 * np.sin(np.pi * u ** 0.7) * (1 - 0.3 * u)
        bot = -0.15 * np.sin(np.pi * u ** 0.6) * (1 - 0.2 * u)
        self.body = (u, top, bot)
        self.col = (46, 66, 104)   # lighter than the deep water so the whale reads clearly (fix 2026-11-08)

    def frame(self, t):
        lw = self.lw
        yy = np.arange(self.lh)[:, None]; xx = np.arange(lw)[None, :]
        idx = (xx + yy * 0.35 + t * 2.5 + lw).astype(int) % (lw * 4)
        rays = self.r1[idx] * np.exp(-yy / (self.lh * 0.5))
        up = cv2.resize(rays, (self.W, self.H), interpolation=cv2.INTER_CUBIC)[..., None]
        f = self.bg + up * np.array([0.55, 0.65, 0.75], np.float32) * 0.3
        self.dust.draw(f, t)
        return f

    def overlay(self, img, t):
        x = self.x0 + self.dir * self.v * t; L = self.L
        u, top, bot = self.body
        und = 0.04 * np.sin(TAU * (u * 0.8 - t / 4)) * u ** 2
        xs = x + self.dir * (0.5 - u) * L
        ys_t = self.y - (top + und) * L * 0.6; ys_b = self.y - (bot + und) * L * 0.6
        pts = np.concatenate([np.stack([xs, ys_t], 1), np.stack([xs, ys_b], 1)[::-1]]).astype(np.int32)
        ov = img.copy()
        cv2.fillPoly(ov, [pts], self.col, cv2.LINE_AA)
        ut = u[-1]; tx = xs[-1]; ty = self.y - und[-1] * L * 0.6
        fl = 0.12 * L * np.sin(TAU * t / 4)
        tail = np.array([[tx, ty], [tx - self.dir * 0.12 * L, ty - 0.09 * L + fl], [tx - self.dir * 0.05 * L, ty + fl * 0.3], [tx - self.dir * 0.12 * L, ty + 0.09 * L + fl]], np.int32)
        cv2.fillPoly(ov, [tail], self.col, cv2.LINE_AA)
        fx = x + self.dir * 0.12 * L; fy = self.y + 0.06 * L * 0.6
        fin = np.array([[fx, fy], [fx - self.dir * 0.16 * L, fy + 0.1 * L], [fx - self.dir * 0.05 * L, fy + 0.02 * L]], np.int32)
        cv2.fillPoly(ov, [fin], self.col, cv2.LINE_AA)
        cv2.addWeighted(ov, 0.9, img, 0.1, 0, img)


SCENES = {c.name: c for c in [Nebula, MoonSea, Forest, Aurora, Feather, DawnClouds, Birds, Whale]}
