"""Gate for long-video scripts. python3 -m wots.longcheck content/long/<id>.json
Uses the same banned-claims / pressure / quote rules as the Shorts (wots.textcheck)."""
import json, os, re, sys
from .textcheck import BANNED, RELATIONSHIP_RED_FLAGS, QUOTE_ATTR, HEDGES, FACT_TOPICS

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))
KINDS = {'music': ('minutes',), 'reflection': ('sections', 'topic'), 'compilation': ('from', 'to')}


def check(path):
    e = []; s = json.load(open(path))
    for k in ('id', 'date', 'kind', 'title', 'description', 'scene') + KINDS.get(s.get('kind'), ()):
        if not s.get(k) and not (k == 'scene' and s.get('kind') == 'compilation'): e.append(f'missing "{k}"')
    if s.get('kind') not in KINDS: e.append('kind must be music | reflection | compilation')
    if e: return e
    if os.path.basename(path) != s['id'] + '.json' or not s['id'].startswith(f"{s['date']}-{s['kind']}-"): e.append('id must be <date>-<kind>-<slug> = file name')
    if s.get('scene') and s['scene'] not in {x for t in CFG['topics'].values() for x in t['scenes']}: e.append('unknown scene')
    if len(s['title']) > 100: e.append('title longer than 100')
    texts = [s['title'], s['description']]
    if s['kind'] == 'music' and not 30 <= s['minutes'] <= 90: e.append('music: 30-90 minutes')
    if s['kind'] == 'reflection':
        if s['topic'] not in CFG['topics']: e.append('unknown topic')
        if not 3 <= len(s['sections']) <= 6: e.append('reflection: 3-6 sections')
        body = ' '.join(x['text'] for x in s['sections']); n = len(body.split())
        if not 1100 <= n <= 2200: e.append(f'reflection is {n} words; needs 1100-2200 (about 9-14 minutes)')
        texts += [body] + [x['heading'] for x in s['sections']]
        if s['topic'] in FACT_TOPICS and len(re.findall(HEDGES, body, re.I)) < n / 120:
            e.append('belief framing too thin for this topic: present ideas as beliefs/possibilities, not facts')
    allt = ' '.join(texts)
    for b in BANNED + RELATIONSHIP_RED_FLAGS:
        m = re.search(b, allt, re.I)
        if m: e.append(f'banned wording: "{m.group(0)}"')
    if re.search(QUOTE_ATTR, allt): e.append('no quotes attributed to people')
    return e


if __name__ == '__main__':
    bad = 0
    for p in sys.argv[1:]:
        e = check(p); print(('FAIL ' if e else 'OK   ') + os.path.basename(p)); [print('  -', x) for x in e]; bad += bool(e)
    sys.exit(1 if bad else 0)
