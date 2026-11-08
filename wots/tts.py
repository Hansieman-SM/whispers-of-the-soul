"""Narration with Kokoro (kokoro-onnx, Apache-2.0 model). Returns 44.1 kHz mono audio plus
caption cues timed to the spoken text (sentence-level synthesis, phrase timing snapped to pauses)."""
import os, re
import numpy as np
from scipy.signal import resample_poly

SR = 44100
MODEL_DIR = os.environ.get('WOTS_MODELS', os.path.join(os.path.dirname(__file__), '..', 'models'))
_k = None


def kokoro():
    global _k
    if _k is None:
        from kokoro_onnx import Kokoro
        _k = Kokoro(os.path.join(MODEL_DIR, 'kokoro-v1.0.onnx'), os.path.join(MODEL_DIR, 'voices-v1.0.bin'))
    return _k


def sentences(text):
    text = re.sub(r'\s+', ' ', text.strip())
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z"“])', text)
    return [p.strip() for p in parts if p.strip()]


WEAK_END = set("a an the to of and or but your my our their his her its this that these those is are was were be been am "
               "with for in on at by from as if so than into onto who whom whose which what where when your you're it's i'm "
               "can could would should may might will not no every each some any more most very just".split())
GOOD_START = set("but and or when where while because so that which who like as if until before after though although "
                 "with without into from for in on at to than yet or".split())


def phrases(sentence, target=5, max_words=7, max_chars=36):
    """Split a sentence into caption phrases. Hard breaks after , ; : and dashes; inside a clause a
    small dynamic programme picks breaks that keep phrases 3-7 words and avoid ending on a weak word."""
    out = []
    for clause in re.split(r'(?<=[,;:\u2014])\s+|\s+(?=\u2014)', sentence):
        w = clause.split(); n = len(w)
        if n <= max_words and len(clause) <= max_chars:
            out.append(clause); continue
        best = [0.0] + [1e9] * n; prev = [0] * (n + 1)
        for j in range(1, n + 1):
            for i in range(max(0, j - max_words), j):
                seg = w[i:j]; L = len(' '.join(seg))
                if L > max_chars and j - i > 1:
                    continue
                c = (len(seg) - target) ** 2 * 0.6
                if len(seg) < 3: c += 6
                if j < n and re.sub(r'\W', '', seg[-1].lower()) in WEAK_END: c += 8
                if j < n and re.sub(r'\W', '', w[j].lower()) in GOOD_START: c -= 2
                if best[i] + c < best[j]:
                    best[j] = best[i] + c; prev[j] = i
        cuts, j = [], n
        while j > 0:
            cuts.append((prev[j], j)); j = prev[j]
        out += [' '.join(w[a:b]) for a, b in reversed(cuts)]
    merged = []
    for p in out:                                # glue 1-2 word fragments to the previous phrase if it fits
        if merged and len(p.split()) <= 2 and len(merged[-1]) + len(p) < max_chars + 4:
            merged[-1] += ' ' + p
        else:
            merged.append(p)
    if len(merged) > 1 and len(merged[0].split()) <= 2 and len(merged[0]) + len(merged[1]) < max_chars + 4:
        merged[1] = merged[0] + ' ' + merged[1]; merged.pop(0)
    return merged


def _pauses(a, sr):
    """Centres of internal silences (>110 ms) in a sentence clip, in seconds."""
    hop = int(0.01 * sr)
    e = np.sqrt(np.convolve(a ** 2, np.ones(hop) / hop, 'same')[::hop])
    thr = max(e.max() * 0.04, 1e-4)
    quiet = e < thr
    res, i = [], 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if j - i >= 11 and i > 5 and j < len(quiet) - 5:
                res.append((i + j) / 2 * 0.01)
            i = j
        else:
            i += 1
    return res


def _trim(a, sr):
    e = np.abs(a) > 0.004
    idx = np.where(e)[0]
    if not len(idx):
        return a
    s = max(0, idx[0] - int(0.02 * sr)); t = min(len(a), idx[-1] + int(0.08 * sr))
    return a[s:t]


def narrate(text, voice='af_heart', lang='en-us', speed=0.88, pause=0.55, lead=0.12):
    """-> (audio float32 @44.1k, cues [(start, end, phrase)], voice_end_seconds)"""
    k = kokoro()
    audio = [np.zeros(int(lead * SR), np.float32)]
    t = lead; cues = []
    for s in sentences(text):
        a, sr = k.create(s.replace('—', ', '), voice=voice, speed=speed, lang=lang)
        a = _trim(np.asarray(a, np.float32), sr)
        pz = _pauses(a, sr)
        a = resample_poly(a, 147, 80).astype(np.float32)          # 24 kHz -> 44.1 kHz
        L = len(a) / SR
        ph = phrases(s)
        weights = np.array([len(p) + 4 for p in ph], float)
        bounds = np.concatenate([[0], np.cumsum(weights) / weights.sum() * L])
        for b in range(1, len(bounds) - 1):                        # snap to the nearest real pause
            near = [p for p in pz if abs(p - bounds[b]) < 0.45]
            if near:
                bounds[b] = min(near, key=lambda p: abs(p - bounds[b]))
        for i, p in enumerate(ph):
            cues.append([t + bounds[i], t + bounds[i + 1], p])
        audio.append(a); t += L
        audio.append(np.zeros(int(pause * SR), np.float32)); t += pause
    voice_end = t - pause
    for i in range(len(cues) - 1):                                 # hold text through short gaps
        cues[i][1] = max(cues[i][1], min(cues[i + 1][0], cues[i][1] + pause))
    a = np.concatenate(audio)
    peak = np.max(np.abs(a)) + 1e-9
    return a / peak * 0.89, [tuple(c) for c in cues], voice_end
