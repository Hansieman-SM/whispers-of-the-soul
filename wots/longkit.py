"""Building blocks for long 16:9 videos (10-90 min) that render fast on GitHub Actions:
- a seamless background loop (scene rendered forward then backward = ping-pong, so it can loop for hours),
- all text as an ASS subtitle file rendered by libass (soft fades, wrapping, custom fonts),
- one ffmpeg pass that loops the background, burns in the text, adds the audio and encodes."""
import os, subprocess, wave
import numpy as np

W, H, FPS = 1920, 1080, 24


def bg_loop(scene, out_mp4, leg=40.0, shade=None, fps=FPS):
    """Render `leg` seconds forward and the same frames backward -> loop of 2*leg seconds without a seam."""
    n = int(leg * fps)
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', '-g', str(fps * 2), out_mp4],
                          stdin=subprocess.PIPE)
    order = list(range(n)) + list(range(n - 1, 0, -1))
    for i in order:
        f = scene.frame(i / fps)
        if shade is not None:
            f = f * shade
        ff.stdin.write((np.clip(f, 0, 1) * 255).astype(np.uint8).tobytes())
    ff.stdin.close(); ff.wait()
    if ff.returncode:
        raise SystemExit('ffmpeg bg loop failed')
    return len(order) / fps


def ass_time(t):
    t = max(0.0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f'{h}:{m:02d}:{s:05.2f}'


def ass_escape(s):
    return s.replace('\\', '').replace('{', '(').replace('}', ')').replace('\n', '\\N')


class ASS:
    def __init__(self):
        self.styles, self.events = [], []

    def style(self, name, font, size, colour='F6F0E4', bold=0, italic=0, align=8, mv=0, ml=260, mr=260, spacing=0, outline=2, shadow=0,
              back='000000', back_alpha=0x90):
        # colours are RRGGBB; ASS wants &HAABBGGRR
        c = lambda rgb, a=0: f'&H{a:02X}{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}'
        self.styles.append(f'Style: {name},{font},{size},{c(colour)},{c(colour)},{c(back, back_alpha)},{c(back, 0xB0)},{bold},{italic},0,0,100,100,'
                           f'{spacing},0,1,{outline},{shadow},{align},{ml},{mr},{mv},1')

    def add(self, t0, t1, style, text, fade=(700, 700), extra=''):
        self.events.append(f'Dialogue: 0,{ass_time(t0)},{ass_time(t1)},{style},,0,0,0,,{{\\fad({fade[0]},{fade[1]})\\blur4{extra}}}{ass_escape(text)}')

    def write(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n'
                    '[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, '
                    'Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n')
            f.write('\n'.join(self.styles) + '\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n')
            f.write('\n'.join(self.events) + '\n')


def write_wav(path, stereo, sr):
    o = wave.open(path, 'wb'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(sr)
    o.writeframes((np.clip(stereo, -1, 1).T * 32767).astype('<i2').tobytes()); o.close()


def tile_music(chunk, seconds, sr, xfade=6.0):
    """Repeat a stereo music chunk (2, n) to `seconds` with equal-power crossfades."""
    n = int(seconds * sr); x = int(xfade * sr); L = chunk.shape[1]
    out = np.zeros((2, n), np.float32); pos = 0
    ramp = np.sin(np.linspace(0, np.pi / 2, x)) ** 2
    while pos < n:
        c = chunk.copy()
        c[:, :x] *= ramp if pos else 1
        c[:, -x:] *= ramp[::-1]
        e = min(n, pos + L); out[:, pos:e] += c[:, :e - pos]
        pos += L - x
    f = np.clip(np.arange(n) / sr / 3, 0, 1) * np.clip((seconds - np.arange(n) / sr) / 6, 0, 1)
    return out * f


def assemble(bg_mp4, wav, ass_path, total, out_mp4, fontsdir, overlay_png=None, overlay_xy=(48, 40), crf=23):
    fdir = fontsdir.replace(':', '\\:')
    inputs = ['-stream_loop', '-1', '-i', bg_mp4]
    if overlay_png:
        inputs += ['-i', overlay_png]
    inputs += ['-i', wav]
    ai = 2 if overlay_png else 1
    vf = (f'[0:v][1:v]overlay={overlay_xy[0]}:{overlay_xy[1]}[b];[b]' if overlay_png else '[0:v]') + \
         f"subtitles='{ass_path}':fontsdir='{fdir}'[v]"
    cmd = ['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', vf, '-map', '[v]', '-map', f'{ai}:a',
           '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '48000', '-t', f'{total:.2f}', '-r', str(FPS),
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', str(crf), '-pix_fmt', 'yuv420p', '-g', str(FPS * 4),
           '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '160k', out_mp4]
    r = subprocess.run(cmd)
    if r.returncode:
        raise SystemExit('ffmpeg assemble failed')
