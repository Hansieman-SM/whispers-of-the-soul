"""Render one Whispers of the Soul Short from a script JSON.
python3 -m wots.render content/scripts/<id>.json out/<id>/      -> <id>.mp4, <id>_thumb.jpg, <id>.meta.json"""
import json, os, subprocess, sys, wave, hashlib
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from . import tts, music
from .scenes import SCENES, feather_sprite, radial

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))
W, H, FPS = CFG['video']['width'], CFG['video']['height'], CFG['video']['fps']
F = lambda n: os.path.join(ROOT, 'fonts', n)
CAP_Y, CAP_X, CAP_W = 900, W // 2 - 30, 800        # captions: centre slightly left of the Shorts buttons
TOPIC_Y = 745
WARM_WHITE = (255, 247, 232); GOLD = (232, 196, 128)


def font(name, size, var=None):
    f = ImageFont.truetype(F(name), size)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
    return f


def wrap(text, fnt, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        if fnt.getlength(test) <= maxw or not cur:
            cur = test
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    if len(lines) == 2 and len(lines[1].split()) == 1 and len(lines[0].split()) > 2:   # balance
        a = lines[0].split(); lines = [' '.join(a[:-1]), a[-1] + ' ' + lines[1]]
    return lines


def text_block(lines, fnt, fill, spacing=1.18, shadow=0.8, track=0):
    asc, desc = fnt.getmetrics(); lh = int((asc + desc) * spacing)
    widths = [fnt.getlength(l) + track * len(l) for l in lines]
    bw, bh = int(max(widths)) + 80, lh * len(lines) + 60
    txt = Image.new('L', (bw, bh), 0); d = ImageDraw.Draw(txt)
    for i, l in enumerate(lines):
        x = (bw - widths[i]) / 2; y = 30 + i * lh
        if track:
            for ch in l:
                d.text((x, y), ch, font=fnt, fill=255); x += fnt.getlength(ch) + track
        else:
            d.text((x, y), l, font=fnt, fill=255)
    a = np.asarray(txt, np.float32) / 255
    sh = np.asarray(txt.filter(ImageFilter.GaussianBlur(9)), np.float32) / 255
    sh = np.clip(sh * 1.8, 0, 1) * shadow
    alpha = np.maximum(a, sh)
    rgb = (np.array(fill, np.float32) / 255 * a[..., None]) / np.maximum(alpha[..., None], 1e-4)
    return np.dstack([rgb, alpha])        # straight alpha RGBA float


def blend(img, block, cx, cy, k=1.0):
    bh, bw = block.shape[:2]; x0, y0 = int(cx - bw / 2), int(cy - bh / 2)
    a0, b0 = max(0, -y0), max(0, -x0); a1, b1 = min(bh, H - y0), min(bw, W - x0)
    reg = img[y0 + a0:y0 + a1, x0 + b0:x0 + b1].astype(np.float32) / 255
    blk = block[a0:a1, b0:b1]; al = blk[..., 3:4] * k
    img[y0 + a0:y0 + a1, x0 + b0:x0 + b1] = ((reg * (1 - al) + blk[..., :3] * al) * 255).astype(np.uint8)


def emblem():
    """Brand mark: Hans's watermark file if present, else a small drawn feather around a soul light."""
    p = os.path.join(ROOT, 'brand', 'watermark.png')
    if os.path.exists(p):
        im = Image.open(p).convert('RGBA'); im.thumbnail((84, 84))
        a = np.asarray(im, np.float32) / 255
        return a
    S = 84
    out = np.zeros((S, S, 4), np.float32)
    g = radial(S, S, S / 2, S / 2, 12)
    out[..., :3] = np.array([1.0, 0.86, 0.6]); out[..., 3] = np.clip(g * 1.4, 0, 1)
    fe = feather_sprite(np.random.default_rng(7), 70)
    fe = cv2.warpAffine(np.pad(fe, ((7, 7), (int((84 - fe.shape[1]) / 2),) * 2, (0, 0)))[:84, :84], cv2.getRotationMatrix2D((42, 42), -35, 1.0), (84, 84))
    al = fe[..., 3:4]
    out[..., :3] = out[..., :3] * (1 - al) + fe[..., :3] * al
    out[..., 3] = np.maximum(out[..., 3], fe[..., 3])
    return out


def header_block():
    em = emblem()
    name = text_block(['Whispers of the Soul'], font('Cinzel[wght].ttf', 34, 'Regular'), WARM_WHITE, shadow=0.7, track=1)
    return em, name


def build_audio(script, out_wav):
    v = CFG['voice']
    voice, cues, vend = tts.narrate(script['text'], v['voice'], v['lang'], v['speed'], v['sentencePause'])
    total = vend + CFG['video']['outroSeconds']
    mus, info = music.compose(total + 0.5, script['seed'])
    mixd = music.mix(voice, mus, vend, total)
    o = wave.open(out_wav, 'wb'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(music.SR)
    o.writeframes((mixd.T * 32767).astype('<i2').tobytes()); o.close()
    return cues, vend, total, info


def render(script_path, outdir):
    script = json.load(open(script_path))
    sid = script['id']; os.makedirs(outdir, exist_ok=True)
    seed = script.setdefault('seed', int(hashlib.sha1(sid.encode()).hexdigest()[:8], 16))
    rng = np.random.default_rng(seed)
    topic = CFG['topics'][script['topic']]
    scene_name = script.get('scene') or rng.choice(topic['scenes'])
    wav = os.path.join(outdir, sid + '.wav')
    cues, vend, total, minfo = build_audio(script, wav)
    scene = SCENES[scene_name](np.random.default_rng(seed + 1), W, H, total)

    capf = font('CormorantGaramond[wght].ttf', 76, 'SemiBold')
    blocks = []
    for i, (s, e, p) in enumerate(cues):            # no overlap: each phrase is gone before the next appears
        nxt = cues[i + 1][0] if i + 1 < len(cues) else vend + 0.3
        blocks.append((s, min(e + 0.12, nxt - 0.03), text_block(wrap(p, capf, CAP_W), capf, WARM_WHITE)))
    topic_blk = text_block([topic['name'].upper()], font('Cinzel[wght].ttf', 32, 'Regular'), GOLD, shadow=0.75, track=3)
    slogan = text_block([CFG['slogan']], font('CormorantGaramond-Italic[wght].ttf', 68, 'Medium Italic'), WARM_WHITE)
    cta = text_block([CFG.get('outroCta', 'Subscribe for daily whispers')], font('Lato-Regular.ttf', 44), GOLD, shadow=0.7)  # on every video since 2026-11-13 (Hans)
    em, name = header_block()

    yy = np.arange(H, dtype=np.float32)[:, None]
    scrim = 1 - 0.38 * np.exp(-((yy - CAP_Y) / 300) ** 2)
    xx = np.arange(W, dtype=np.float32)[None, :]
    vig = 1 - 0.35 * (((xx - W / 2) / (W / 2)) ** 2 * 0.5 + ((yy - H / 2) / (H / 2)) ** 2 * 0.5)
    shade = (scrim * vig).astype(np.float32)[..., None]

    mp4 = os.path.join(outdir, sid + '.mp4')
    nfr = int(round(total * FPS))
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-i', wav, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '48000',
                           '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
                           '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '192k', '-shortest', mp4], stdin=subprocess.PIPE)
    thumb_t = min(total * 0.4, total - 1)
    for i in range(nfr):
        t = i / FPS
        f = scene.frame(t) * shade
        lvl = min(1.0, 0.8 + 0.2 * t / 0.4) * (1 - 0.35 * max(0, (t - (total - 0.8)) / 0.8))
        img = (np.clip(f * lvl, 0, 1) * 255).astype(np.uint8)
        if hasattr(scene, 'overlay'):
            scene.overlay(img, t)
        if i == int(thumb_t * FPS):
            bg_thumb = img.copy()
        blend(img, em, W / 2, 250, 0.95)
        blend(img, name, W / 2, 318, 0.92)
        if t < vend + 0.2:
            blend(img, topic_blk, CAP_X, TOPIC_Y, min(1, t / 0.3) * 0.95)
        for s, e, b in blocks:
            if s - 0.04 <= t < e:
                k = min(1, (t - s + 0.04) / 0.14, (e - t) / 0.1)
                blend(img, b, CAP_X, CAP_Y, max(0, k))
        if t > vend + 0.35:
            k = min(1, (t - vend - 0.35) / 0.6)
            blend(img, slogan, CAP_X, CAP_Y, k)
            if cta is not None:
                blend(img, cta, CAP_X, CAP_Y + 95, k * 0.95)
        ff.stdin.write(img.tobytes())
    ff.stdin.close(); ff.wait()
    if ff.returncode:
        raise SystemExit('ffmpeg failed')
    os.remove(wav)

    # thumbnail 1080x1920
    th = bg_thumb.copy()
    tf = font('CormorantGaramond[wght].ttf', 104, 'SemiBold')
    tb = text_block(wrap(script['title'].split(' | ')[0], tf, 820), tf, WARM_WHITE, spacing=1.08, shadow=0.9)
    blend(th, em, W / 2, 250); blend(th, name, W / 2, 318)
    blend(th, topic_blk, CAP_X, 690)
    blend(th, tb, CAP_X, CAP_Y + 40)
    Image.fromarray(th).save(os.path.join(outdir, sid + '_thumb.jpg'), quality=92)

    meta = {k: script[k] for k in ('id', 'date', 'slot', 'topic', 'title', 'description') if k in script}
    meta.update({'scene': scene_name, 'seed': seed, 'seconds': round(total, 2), 'voiceSeconds': round(vend, 2),
                 'music': minfo, 'voice': CFG['voice']['voice'], 'cues': [[round(s, 2), round(e, 2), p] for s, e, p in cues],
                 'provenance': {'visuals': 'procedural, generated by wots/scenes.py (own code)',
                                'music': 'generative, wots/music.py (own code, no samples)',
                                'voice': 'Kokoro-82M via kokoro-onnx (Apache-2.0 / MIT)',
                                'fonts': 'Cormorant Garamond, Cinzel, Lato (SIL Open Font License)'}})
    json.dump(meta, open(os.path.join(outdir, sid + '.meta.json'), 'w'), indent=1)
    return meta


if __name__ == '__main__':
    m = render(sys.argv[1], sys.argv[2])
    print(json.dumps({k: m[k] for k in ('id', 'scene', 'seconds', 'voiceSeconds')}))
