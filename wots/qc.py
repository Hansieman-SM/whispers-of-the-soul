"""Automatic technical QC of a rendered Short. python3 -m wots.qc out/<id>/<id>.mp4  -> writes <id>.qc.json, exit 1 on failure.
A human-style visual check of the contact sheet (tools/sheet.sh) is still required before scheduling."""
import json, os, re, subprocess, sys

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stderr + subprocess.run(cmd, capture_output=True, text=True).stdout


def qc(mp4):
    errs, info = [], {}
    pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,width,height,r_frame_rate:format=duration,size',
                                    '-of', 'json', mp4], capture_output=True, text=True).stdout)
    v = [s for s in pr['streams'] if s['codec_type'] == 'video'][0]; a = [s for s in pr['streams'] if s['codec_type'] == 'audio']
    dur = float(pr['format']['duration']); info.update(duration=round(dur, 2), width=v['width'], height=v['height'], fps=v['r_frame_rate'],
                                                       sizeMB=round(int(pr['format']['size']) / 1e6, 1))
    vc = CFG['video']
    if (v['width'], v['height']) != (vc['width'], vc['height']): errs.append('wrong resolution')
    if v['r_frame_rate'] != f"{vc['fps']}/1": errs.append('wrong frame rate')
    if not a: errs.append('no audio')
    if not (vc['minSeconds'] <= dur <= vc['maxSeconds']): errs.append(f'duration {dur:.1f}s outside {vc["minSeconds"]}-{vc["maxSeconds"]}')
    out = subprocess.run(['ffmpeg', '-nostats', '-i', mp4, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    I = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', out)[-1]); P = float(re.findall(r'Peak:\s+(-?[\d.]+) dBFS', out)[-1])
    info.update(lufs=I, peakDb=P)
    if not (-16 <= I <= -12): errs.append(f'loudness {I} LUFS')
    if P > -0.9: errs.append(f'true peak {P} dBFS')
    sil = subprocess.run(['ffmpeg', '-i', mp4, '-af', 'silencedetect=n=-45dB:d=0.6', '-f', 'null', '-'], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r'silence_start: (-?[\d.]+)', sil)]
    if any(s < 0.3 for s in starts): errs.append('silent start')
    if starts: errs.append(f'silence of >0.6 s at {starts[:3]}')
    blk = subprocess.run(['ffmpeg', '-i', mp4, '-vf', 'blackdetect=d=0.1:pix_th=0.04', '-an', '-f', 'null', '-'], capture_output=True, text=True).stderr
    if 'black_start' in blk: errs.append('black frames detected')
    meta_p = mp4.replace('.mp4', '.meta.json')
    if os.path.exists(meta_p):
        m = json.load(open(meta_p))
        for s, e, p in m['cues']:
            if e - s < 0.45: errs.append(f'caption too short on screen: "{p}" ({e - s:.2f}s)')
            if len(p) / max(e - s, 0.1) > 24: errs.append(f'caption too fast to read: "{p}"')
            if len(p) > 44: errs.append(f'caption too long: "{p}"')
        if dur - m['voiceSeconds'] > 3.5: errs.append('tail after voice longer than 3.5 s')
    thumb = mp4.replace('.mp4', '_thumb.jpg')
    if not os.path.exists(thumb): errs.append('thumbnail missing')
    res = {'file': os.path.basename(mp4), 'pass': not errs, 'errors': errs, **info}
    json.dump(res, open(mp4.replace('.mp4', '.qc.json'), 'w'), indent=1)
    return res


if __name__ == '__main__':
    bad = 0
    for f in sys.argv[1:]:
        r = qc(f); print(json.dumps(r)); bad += not r['pass']
    sys.exit(1 if bad else 0)
