"""Content gate for new scripts. python3 -m wots.textcheck content/scripts/<id>.json [...]
Fails (exit 1) on: wrong length, repeated hooks/titles/ideas, overlap with the archive, banned claims,
pressure language, invented quotes. Prints every problem so the writer can fix it."""
import json, os, re, sys, glob

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))
ARCHIVE = os.path.join(ROOT, 'content', 'archive.jsonl')

BANNED = [  # pressure, chain-letter, promises
    r'\bshare (this|it)\b', r'\btype ["“]?amen', r'\bclaim (your|this)\b', r'\bblessing will\b', r'\bif you ignore\b',
    r'\bdon\'?t scroll\b', r'\bwithin \d+ (hours|days)\b', r'\bguarantee', r'\bwill (heal|cure)\b', r'\bwill (come back|return to you)\b',
    r'\bwill reunite\b', r'\bmoney (is|will be) coming\b', r'\bwealth will\b', r'\bthis is your sign\b', r'\bthe universe will\b',
    r'\byou will meet\b', r'\bmeant to be together\b', r'\bscience (has )?(proves?|shows?)\b', r'\bscientifically proven\b',
    r'\bproven fact\b', r'\bit is a fact\b', r'\bundeniabl', r'\bwithout a doubt\b', r'\bcontact (your|the) (dead|deceased)\b',
    r'\bmessage from (your )?(loved ones|the dead)\b', r'\bdangerous\b.*\benerg', r'\bcurse', r'\bpunish',
]
RELATIONSHIP_RED_FLAGS = [  # twin flames / soulmates: never frame pain or crossing boundaries as proof
    r'\brunner\b', r'\bchaser\b', r'\bpain (means|proves|is proof)\b', r'\bif it hurts\b.*\b(real|meant)\b',
    r'\bnever give up on (him|her|them)\b', r'\bno matter how (they|he|she) treat', r'\bseparation (is|means) (a sign|proof)\b',
    r'\bthey will come back\b', r'\bwait for (him|her|them)\b',
]
QUOTE_ATTR = r'(["“][^"”]{8,}["”])\s*[—-]?\s*(said|wrote|says|taught|once)|(as|like) [A-Z][a-z]+ [A-Z][a-z]+ (said|wrote|taught)'
FACT_TOPICS = {'past-lives', 'angels', 'parallel-worlds', 'life-after-death', 'spirit-world', 'spirit-guides', 'source', 'twin-flames', 'soulmates', 'dreams'}
HEDGES = r'\b(may|might|perhaps|maybe|believe[ds]?|belief|traditions?|some (people|say)|many (people|say|believe)|could|if|whether|feel|sense|imagine|what if|possib|invitation|reflection|seen as|described|speak of|teach)\b'


def words(t):
    return re.findall(r"[a-z']+", t.lower())


def ngrams(t, n=5):
    w = words(t)
    return {' '.join(w[i:i + n]) for i in range(len(w) - n + 1)}


def archive():
    if not os.path.exists(ARCHIVE):
        return []
    return [json.loads(l) for l in open(ARCHIVE) if l.strip()]


def check(s, arch):
    errs = []
    v = CFG['video']
    n = len(words(s.get('text', '')))
    if not (v['minWords'] <= n <= v['maxWords']):
        errs.append(f'length {n} words (allowed {v["minWords"]}-{v["maxWords"]})')
    for k in ('id', 'topic', 'title', 'text', 'core_idea', 'description'):
        if not s.get(k):
            errs.append(f'missing field {k}')
    if s.get('topic') not in CFG['topics']:
        errs.append(f'unknown topic {s.get("topic")}')
    if len(s.get('title', '')) > 90:
        errs.append('title longer than 90 characters')
    low = s.get('text', '').lower() + ' ' + s.get('title', '').lower() + ' ' + s.get('description', '').lower()
    for p in BANNED:
        if re.search(p, low):
            errs.append(f'banned phrase /{p}/')
    if s.get('topic') in ('twin-flames', 'soulmates'):
        for p in RELATIONSHIP_RED_FLAGS:
            if re.search(p, low):
                errs.append(f'relationship red flag /{p}/')
    if re.search(QUOTE_ATTR, s.get('text', '') + ' ' + s.get('description', '')):
        errs.append('looks like a quote attributed to someone (not allowed)')
    if s.get('topic') in FACT_TOPICS and len(re.findall(HEDGES, low)) < 2:
        errs.append('presents a belief topic without framing it as belief/possibility (need hedging language)')
    sents = re.split(r'(?<=[.!?])\s+', s.get('text', '').strip())
    hook = ' '.join(words(sents[0])[:6]) if sents else ''
    ng = ngrams(s.get('text', ''))
    for a in arch:
        if a.get('id') == s.get('id'):
            continue
        if hook and ' '.join(words(a.get('text', '').split('.')[0])[:6]) == hook:
            errs.append(f'opening repeats {a["id"]}')
        if a.get('title', '').strip().lower() == s.get('title', '').strip().lower():
            errs.append(f'title repeats {a["id"]}')
        ag = ngrams(a.get('text', ''))
        if ng and ag:
            j = len(ng & ag) / len(ng | ag)
            if j > 0.06:
                errs.append(f'text overlaps {a["id"]} (5-gram Jaccard {j:.2f})')
        ci = set(words(a.get('core_idea', ''))) - STOP; cs = set(words(s.get('core_idea', ''))) - STOP
        if a.get('topic') == s.get('topic') and ci and cs and len(ci & cs) / len(ci | cs) > 0.5:
            errs.append(f'core idea too close to {a["id"]}')
    # repeated sentence structure inside the script
    starts = [' '.join(words(x)[:2]) for x in sents if words(x)]
    if starts and max(starts.count(x) for x in starts) > 3:
        errs.append('more than 3 sentences start the same way')
    return errs


STOP = set('the a an and or of to in on is are be your you it that this with for as can may might what when not but'.split())

if __name__ == '__main__':
    arch = archive(); bad = 0
    files = [f for a in sys.argv[1:] for f in glob.glob(a)]
    batch = []
    for f in files:
        s = json.load(open(f)); e = check(s, arch + batch); batch.append(s)
        print(('OK   ' if not e else 'FAIL ') + s.get('id', f) + ''.join('\n     - ' + x for x in e))
        bad += bool(e)
    sys.exit(1 if bad else 0)
