"""Weekly long videos for Whispers of the Soul (16:9, 1920x1080). Approved by Hans 2026-11-08, built 2026-11-15.
python3 -m wots.long content/long/<id>.json out/<id>   -> <id>.mp4, <id>_thumb.jpg (1280x720), <id>.meta.json

kind "music"       (Friday)    30-60 min calm generative music over a slowly moving scene. Title card at start, subscribe card at the end.
kind "reflection"  (Wednesday) 9-14 min narrated reflection/meditation in 3-6 sections (af_heart), phrase captions, section cards.
kind "compilation" (Sunday)    the week's Shorts back to back in 16:9 (blurred backdrop), with chapters."""
import json, os, sys, glob, hashlib, subprocess, urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from . import tts, music, longkit
from .longkit import W, H
from .scenes import SCENES

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))
FONTS = os.path.join(ROOT, 'fonts', 'ass')
CTA = CFG.get('outroCta', 'Subscribe for daily whispers')


def styles(A):
    A.style('Brand', 'WOTS Cinzel', 30, 'FFF7E8', align=7, mv=48, ml=60, mr=0, spacing=2, outline=1)
    A.style('Title', 'WOTS Cormorant SemiBold', 100, 'FFF7E8', align=5, ml=180, mr=180, outline=3)
    A.style('Slogan', 'WOTS Cormorant Italic', 62, 'FFF7E8', align=8, mv=600, ml=180, mr=180, outline=2)
    A.style('Gold', 'WOTS Cinzel', 54, 'E8C480', align=5, ml=180, mr=180, spacing=5, outline=3)
    A.style('Cap', 'WOTS Cormorant', 72, 'FFF7E8', align=2, mv=250, ml=300, mr=300, outline=3)
    A.style('Cta', 'Lato', 42, 'E8C480', align=8, mv=690, outline=2)


def music_long(seconds, seed, chunk=240):
    """Several different 4-minute pieces in the same key, crossfaded, so an hour does not loop audibly."""
    base, info = music.compose(chunk, seed); pieces = [base]
    for k in range(1, 4 if seconds > 2 * chunk else 1):
        pieces.append(music.compose(chunk, seed + k, key=info['key'])[0])
    sr = music.SR; x = int(6 * sr); ramp = np.sin(np.linspace(0, np.pi / 2, x)) ** 2
    n = int(seconds * sr); out = np.zeros((2, n), np.float32); pos = 0; k = 0
    while pos < n:
        c = pieces[k % len(pieces)].copy(); k += 1
        if pos: c[:, :x] *= ramp
        c[:, -x:] *= ramp[::-1]
        e = min(n, pos + c.shape[1]); out[:, pos:e] += c[:, :e - pos]; pos += c.shape[1] - x
    t = np.arange(n) / sr
    return out * np.clip(t / 3, 0, 1) * np.clip((seconds - t) / 8, 0, 1), {**info, 'pieces': len(pieces)}


def thumbnail(frame, title, sub, tag, path):
    im = Image.fromarray(frame).resize((1280, 720), Image.LANCZOS)
    im = Image.blend(im, Image.new('RGB', im.size, (10, 8, 30)), 0.22)
    rows = [(title, ImageFont.truetype(os.path.join(FONTS, 'WOTSCormorantSemiBold.ttf'), 112), (255, 247, 232), 0),
            (sub, ImageFont.truetype(os.path.join(FONTS, 'WOTSCormorantItalic.ttf'), 54), (255, 247, 232), 0),
            (tag, ImageFont.truetype(os.path.join(FONTS, 'WOTSCinzel.ttf'), 32), (232, 196, 128), 4)]
    mask = Image.new('L', im.size, 0); txt = Image.new('RGB', im.size); md, td = ImageDraw.Draw(mask), ImageDraw.Draw(txt)
    lines = []
    for s, f, col, tr in rows:
        if not s:
            continue
        words, cur = s.split(), ''
        for w_ in words:                                   # wrap to 1100 px
            if f.getlength((cur + ' ' + w_).strip()) > 1100 and cur:
                lines.append((cur, f, col, tr)); cur = w_
            else:
                cur = (cur + ' ' + w_).strip()
        lines.append((cur, f, col, tr))
    total_h = sum(int(sum(f.getmetrics()) * 1.05) for _, f, _, _ in lines)
    y = (720 - total_h) / 2
    for s, f, col, tr in lines:
        wd = sum(f.getlength(c) + tr for c in s) - tr; x = (1280 - wd) / 2
        for c in s:
            md.text((x, y), c, font=f, fill=255); td.text((x, y), c, font=f, fill=col); x += f.getlength(c) + tr
        y += int(sum(f.getmetrics()) * 1.05)
    sh = mask.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(min(255, v * 1.7) * 0.75))
    im.paste((0, 0, 0), (0, 0), sh); im.paste(txt, (0, 0), mask)
    im.save(path, quality=92)


def scene_bg(name, seed, outdir, leg=40.0):
    sc = SCENES[name](np.random.default_rng(seed + 1), W, H, leg * 2)
    yy = np.arange(H, dtype=np.float32)[:, None]
    shade = (1 - 0.30 * np.exp(-((yy - 700) / 300) ** 2)).astype(np.float32)[..., None]
    bg = os.path.join(outdir, 'bg.mp4'); longkit.bg_loop(sc, bg, leg=leg, shade=shade)
    return bg, (np.clip(sc.frame(leg * 0.6) * shade, 0, 1) * 255).astype(np.uint8)


def render_music(s, outdir, seed):
    total = s['minutes'] * 60.0
    mus, minfo = music_long(total, seed)
    wav = os.path.join(outdir, s['id'] + '.wav'); longkit.write_wav(wav, mus * 0.9, music.SR)
    bg, tf = scene_bg(s['scene'], seed, outdir)
    A = longkit.ASS(); styles(A)
    A.add(0, total, 'Brand', 'Whispers of the Soul', fade=(1500, 1500), extra='\\alpha&H40&')
    A.add(1.0, 14, 'Title', s['title'].split(' | ')[0], fade=(1500, 1500), extra='\\pos(960,450)')
    A.add(2.0, 14, 'Slogan', CFG['slogan'], fade=(1500, 1500))
    A.add(total - 16, total - 1, 'Title', CFG['slogan'], fade=(1500, 1500), extra='\\pos(960,460)')
    A.add(total - 15, total - 1, 'Cta', CTA, fade=(1500, 1500))
    return wav, bg, tf, A, total, ['00:00 ' + s['title'].split(' | ')[0]], minfo


def render_reflection(s, outdir, seed):
    v = CFG['voice']; sr = tts.SR
    parts, t, cues, cards = [], 10.0, [], []
    for sec in s['sections']:
        cards.append((t, sec['heading'])); t += 4.5
        a, c, vend = tts.narrate(sec['text'], v['voice'], v['lang'], v['speed'], v['sentencePause'], lead=0.1)
        parts.append((t, a)); cues += [(t + s0, t + s1, p) for s0, s1, p in c]; t += vend + 3.0
    total = t + 14.0
    n = int(total * sr); vt = np.zeros(n, np.float32)
    for t0, a in parts:
        i = int(t0 * sr); vt[i:i + len(a)] += a[:max(0, n - i)]
    mus, minfo = music_long(total, seed)
    tt = np.arange(n) / sr
    talking = np.zeros(n, np.float32)
    for t0, a in parts:
        talking[int(t0 * sr):int(t0 * sr) + len(a)] = 1
    env = np.convolve(talking, np.ones(int(sr * 1.5)) / int(sr * 1.5), 'same')
    gain = 0.13 + 0.15 * (1 - np.clip(env, 0, 1))
    mix = mus[:, :n] * gain + np.stack([vt, vt]) * 0.92
    mix /= max(1.0, np.max(np.abs(mix)) / 0.97)
    wav = os.path.join(outdir, s['id'] + '.wav'); longkit.write_wav(wav, mix, sr)
    bg, tf = scene_bg(s['scene'], seed, outdir)
    A = longkit.ASS(); styles(A)
    A.add(0, total, 'Brand', 'Whispers of the Soul', fade=(1200, 1200), extra='\\alpha&H40&')
    A.add(0.8, 9.6, 'Title', s['title'].split(' | ')[0], fade=(1200, 900), extra='\\pos(960,450)')
    A.add(1.4, 9.6, 'Slogan', CFG['slogan'], fade=(1200, 900))
    for i, (t0, t1, p) in enumerate(cues):
        nxt = cues[i + 1][0] if i + 1 < len(cues) else t1 + 0.3
        A.add(t0 - 0.05, min(t1 + 0.15, nxt - 0.03), 'Cap', p, fade=(150, 120))
    chapters = ['00:00 Introduction']
    for t0, h in cards:
        A.add(t0, t0 + 4.3, 'Gold', h.upper(), fade=(600, 600), extra='\\pos(960,470)')
        chapters.append(f'{int(t0 // 60):02d}:{int(t0 % 60):02d} {h}')
    A.add(total - 13, total - 0.5, 'Title', CFG['slogan'], fade=(1200, 1200), extra='\\pos(960,460)')
    A.add(total - 12, total - 0.5, 'Cta', CTA, fade=(1200, 1200))
    return wav, bg, tf, A, total, chapters, minfo


def render_compilation(s, outdir, seed):
    """Shorts of the week (from state/posts.json) side by side with a blurred copy as 16:9 backdrop."""
    st = json.load(open(os.path.join(ROOT, 'state', 'posts.json')))['posts']
    ids = sorted(k for k, p in st.items() if s['from'] <= p.get('date', '') <= s['to'] and p.get('slot') in ('A', 'B', 'C')
                 and p.get('status') in ('published', 'scheduled'))
    if len(ids) < 7:
        raise SystemExit(f'only {len(ids)} Shorts between {s["from"]} and {s["to"]}')
    segs, chapters, t = [], [], 0.0
    intro = os.path.join(outdir, 'intro.mp4')
    bg, tf = scene_bg(s.get('scene', 'nebula'), seed, outdir, leg=6.0)
    A = longkit.ASS(); styles(A)
    A.add(0.3, 6.6, 'Title', s['title'].split(' | ')[0], fade=(900, 700), extra='\\pos(960,450)')
    A.add(0.8, 6.6, 'Slogan', CFG['slogan'], fade=(900, 700))
    ia = os.path.join(outdir, 'intro.ass'); A.write(ia)
    sil = os.path.join(outdir, 'intro.wav')
    m, _ = music.compose(7.0, seed); longkit.write_wav(sil, m * 0.3, music.SR)
    longkit.assemble(bg, sil, ia, 7.0, intro, FONTS, crf=20)
    segs.append(intro); t = 7.0; chapters.append('00:00 Introduction')
    for i, sid in enumerate(ids):
        src = os.path.join(outdir, sid + '.mp4')
        url = CFG['hosting']['releaseUrl'].format(tag=sid, file=sid + '.mp4')
        if not os.path.exists(src):
            r = subprocess.run(['gh', 'release', 'download', sid, '-p', sid + '.mp4', '-D', outdir, '-R', CFG['hosting']['repo']])
            if r.returncode:
                urllib.request.urlretrieve(url, src)
        dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src], capture_output=True, text=True).stdout)
        out = os.path.join(outdir, f'seg{i:02d}.mp4')
        fc = ('[0:v]split[a][b];[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=30:3,eq=brightness=-0.12[bg];'
              '[b]scale=-2:1080[fg];[bg][fg]overlay=(W-w)/2:0,fps=24,format=yuv420p,'
              f'fade=t=in:st=0:d=0.4,fade=t=out:st={dur - 0.4:.2f}:d=0.4[v];[0:a]aresample=48000,afade=t=in:d=0.3,afade=t=out:st={dur - 0.4:.2f}:d=0.4[a2]')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-filter_complex', fc, '-map', '[v]', '-map', '[a2]', '-c:v', 'libx264',
                        '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2', out], check=True)
        title = st[sid].get('title') or json.load(open(os.path.join(ROOT, 'content', 'scripts', sid + '.json')))['title']
        chapters.append(f'{int(t // 60):02d}:{int(t % 60):02d} {title}'); t += dur; segs.append(out)
    lst = os.path.join(outdir, 'list.txt')
    open(lst, 'w').write(''.join(f"file '{os.path.abspath(p)}'\n" for p in segs))
    mp4 = os.path.join(outdir, s['id'] + '.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c:v', 'copy', '-af', 'loudnorm=I=-14:TP=-2:LRA=11,alimiter=limit=0.79:attack=1:release=50:level=false',
                    '-ar', '48000', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', mp4], check=True)
    return mp4, tf, t, chapters, ids


def render(path, outdir):
    s = json.load(open(path)); sid = s['id']; os.makedirs(outdir, exist_ok=True)
    seed = int(hashlib.sha1(sid.encode()).hexdigest()[:8], 16)
    tag = {'music': f"{s.get('minutes', 60)} MIN · CALM MUSIC", 'reflection': 'GUIDED REFLECTION', 'compilation': 'THIS WEEK\'S WHISPERS'}[s['kind']]
    extra = {}
    if s['kind'] == 'compilation':
        mp4, tf, total, chapters, ids = render_compilation(s, outdir, seed); minfo = None; extra['shorts'] = ids
    else:
        fn = render_music if s['kind'] == 'music' else render_reflection
        wav, bg, tf, A, total, chapters, minfo = fn(s, outdir, seed)
        ass = os.path.join(outdir, sid + '.ass'); A.write(ass)
        mp4 = os.path.join(outdir, sid + '.mp4')
        longkit.assemble(bg, wav, ass, total, mp4, FONTS, crf=23)
        os.remove(wav); os.remove(bg)
    for f in glob.glob(os.path.join(outdir, 'seg*.mp4')) + glob.glob(os.path.join(outdir, '20*-[ABC]-*.mp4')) + [os.path.join(outdir, 'intro.mp4')]:
        if os.path.exists(f) and f != mp4:
            os.remove(f)
    thumbnail(tf, s.get('thumbTitle') or s['title'].split(' | ')[0], CFG['slogan'], tag, os.path.join(outdir, sid + '_thumb.jpg'))
    meta = {k: s[k] for k in ('id', 'date', 'kind', 'title', 'topic', 'scene') if k in s}
    meta.update({'seconds': round(total, 1), 'minutes': round(total / 60, 1), 'chapters': chapters, 'music': minfo, 'long': True, **extra,
                 'provenance': {'visuals': 'procedural, wots/scenes.py (own code)', 'music': 'generative, wots/music.py (own code, no samples)',
                                'voice': 'Kokoro-82M via kokoro-onnx (Apache-2.0 / MIT)' if s['kind'] != 'music' else None}})
    json.dump(meta, open(os.path.join(outdir, sid + '.meta.json'), 'w'), indent=1, ensure_ascii=False)
    return meta


if __name__ == '__main__':
    m = render(sys.argv[1], sys.argv[2])
    print(json.dumps({k: m[k] for k in ('id', 'kind', 'minutes', 'chapters')})[:600])
