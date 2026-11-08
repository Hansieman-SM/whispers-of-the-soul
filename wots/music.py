"""Original generative ambient music (own code, no samples). Every seed gives a different key,
progression, tempo of change, chime melody and texture."""
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR = 44100
KEYS = {'C': 48, 'D': 50, 'Eb': 51, 'E': 52, 'F': 53, 'G': 55, 'Ab': 56, 'A': 57, 'Bb': 58}
# degrees (semitones from root) of calm chords; each progression is a list of chords
PROGS = [
    [[0, 7, 12, 16], [9, 16, 21, 24], [5, 12, 17, 21], [7, 14, 19, 23]],      # I vi IV V(add)
    [[0, 7, 14, 16], [5, 12, 16, 21], [9, 16, 19, 24], [5, 12, 17, 19]],      # Iadd9 IV vi IVsus
    [[0, 7, 12, 19], [4, 11, 16, 19], [9, 16, 21, 24], [5, 12, 17, 24]],      # I iii vi IV
    [[9, 16, 21, 24], [5, 12, 17, 21], [0, 7, 12, 16], [7, 14, 17, 23]],      # vi IV I V
    [[0, 7, 12, 17], [0, 7, 12, 16], [5, 12, 17, 21], [5, 12, 14, 21]],       # Isus I IV IV9
    [[2, 9, 14, 17], [7, 14, 17, 23], [0, 7, 12, 16], [9, 16, 19, 24]],       # ii V I vi
]
PENTA = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _lp(x, fc, order=2):
    return sosfilt(butter(order, fc, 'low', fs=SR, output='sos'), x)


def _reverb(x, rng, secs=3.2, mix=0.45):
    n = int(secs * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((2, n)) * np.exp(-t * 6.5 / secs)
    ir[:, :int(0.012 * SR)] = 0
    ir = np.stack([_lp(ir[0], 5500), _lp(ir[1], 5000)])
    wet = np.stack([fftconvolve(x, ir[0])[:len(x)], fftconvolve(x, ir[1])[:len(x)]])
    wet /= np.max(np.abs(wet)) + 1e-9
    dry = np.stack([x, x]) / (np.max(np.abs(x)) + 1e-9)
    return dry * (1 - mix) + wet * mix


def compose(seconds, seed):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR); t = np.arange(n) / SR
    root = KEYS[rng.choice(list(KEYS))]
    prog = PROGS[rng.integers(len(PROGS))]
    chord_len = float(rng.choice([6.0, 7.0, 8.0, 9.0]))
    bright = rng.uniform(900, 1800)
    pad = np.zeros(n)
    nch = int(np.ceil(seconds / chord_len)) + 1
    for c in range(nch):
        notes = prog[c % len(prog)]
        s0 = c * chord_len - 1.5; s1 = s0 + chord_len + 3.0
        a = max(0, int(s0 * SR)); b = min(n, int(s1 * SR))
        if a >= b:
            continue
        tt = t[a:b] - s0
        env = np.clip(tt / 2.5, 0, 1) * np.clip((s1 - s0 - tt) / 2.5, 0, 1)
        env = np.sin(env * np.pi / 2) ** 2
        seg = np.zeros(b - a)
        for d in notes:
            f = hz(root + d)
            for det in (-0.12, 0.0, 0.11):
                ph = rng.uniform(0, 2 * np.pi)
                ff = f * 2 ** (det / 12)
                seg += np.sin(2 * np.pi * ff * tt + ph) + 0.28 * np.sin(4 * np.pi * ff * tt + ph) + 0.1 * np.sin(6 * np.pi * ff * tt)
        pad[a:b] += seg * env / len(notes)
    pad = _lp(pad, bright)
    lfo = 0.82 + 0.18 * np.sin(2 * np.pi * t / rng.uniform(9, 15))
    pad *= lfo
    drone = np.sin(2 * np.pi * hz(root - 12) * t) * 0.35 + np.sin(2 * np.pi * hz(root - 5) * t) * 0.12
    drone *= np.clip(t / 3, 0, 1)
    # soft chimes on a pentatonic scale
    chimes = np.zeros(n)
    tt0 = rng.uniform(1.0, 3.0)
    while tt0 < seconds - 2:
        m = root + 24 + PENTA[rng.integers(len(PENTA))]
        L = int(3.5 * SR); a = int(tt0 * SR); b = min(n, a + L)
        x = np.arange(b - a) / SR
        f = hz(m)
        chimes[a:b] += (np.sin(2 * np.pi * f * x) + 0.25 * np.sin(2 * np.pi * f * 2.76 * x) * np.exp(-x * 3)) * np.exp(-x * 1.4) * (1 - np.exp(-x * 200)) * rng.uniform(0.5, 1.0)
        tt0 += rng.uniform(1.6, 4.2)
    chimes = _lp(chimes, 6000)
    air = _lp(rng.standard_normal(n), 700) * 0.06 * (0.6 + 0.4 * np.sin(2 * np.pi * t / 11))
    mono = pad * 0.55 + drone * 0.5 + chimes * rng.uniform(0.10, 0.18) + air
    st = _reverb(mono, rng)
    fade = np.clip(t / 1.2, 0, 1) * np.clip((seconds - t) / 2.0, 0, 1)
    st *= fade
    return (st / (np.max(np.abs(st)) + 1e-9) * 0.8).astype(np.float32), {
        'key': [k for k, v in KEYS.items() if v == root][0], 'chordSeconds': chord_len}


def mix(voice, music, voice_end, total):
    """voice: mono @SR; music: stereo (2, n). Music sits ~-20 dB under the voice and rises slightly after."""
    n = int(total * SR)
    v = np.zeros(n, np.float32); v[:min(n, len(voice))] = voice[:n]
    m = music[:, :n]
    if m.shape[1] < n:
        m = np.pad(m, ((0, 0), (0, n - m.shape[1])))
    t = np.arange(n) / SR
    gain = np.where(t < voice_end + 0.3, 0.13, 0.13 + np.clip((t - voice_end - 0.3) / 0.8, 0, 1) * 0.12)
    out = m * gain + np.stack([v, v]) * 0.92
    return out / max(1.0, np.max(np.abs(out)) / 0.97)
