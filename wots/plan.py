"""What needs to be written next. python3 -m wots.plan [--days 7] [--from YYYY-MM-DD]
Prints JSON: missing (date, slot, time, timezone, category, topic) for the rolling buffer, choosing per
category the topic used longest ago, plus the recent hooks/ideas per topic so the writer avoids them."""
import json, os, sys, datetime as dt
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))
STATE = os.path.join(ROOT, 'state', 'posts.json')
ARCHIVE = os.path.join(ROOT, 'content', 'archive.jsonl')


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {'posts': {}}


def archive():
    return [json.loads(l) for l in open(ARCHIVE)] if os.path.exists(ARCHIVE) else []


def plan(days=7, start=None):
    tz = ZoneInfo(CFG['schedule']['timezone'])
    now = dt.datetime.now(tz)
    start = start or (now + dt.timedelta(days=1)).date()
    st = load_state()['posts']; arch = archive()
    taken = {(p['date'], p['slot']) for p in st.values() if p.get('status') not in ('failed', 'cancelled')}
    taken |= {(a['date'], a['slot']) for a in arch if a.get('date')}
    last = {}
    for a in sorted(arch, key=lambda a: (a.get('date') or '', a.get('slot', ''))):
        last[a['topic']] = a.get('date') or '0000'
    missing = []
    for d in range(days):
        day = start + dt.timedelta(days=d)
        for s in CFG['schedule']['slots']:
            if (day.isoformat(), s['slot']) in taken:
                continue
            topics = CFG['categories'][s['category']]
            topic = min(topics, key=lambda t: (last.get(t, '0000'), topics.index(t)))
            last[topic] = day.isoformat()
            missing.append({'date': day.isoformat(), 'slot': s['slot'], 'time': s['time'], 'timezone': CFG['schedule']['timezone'],
                            'category': s['category'], 'topic': topic, 'topicName': CFG['topics'][topic]['name'],
                            'id': f"{day.isoformat()}-{s['slot']}-{topic}"})
    recent = {}
    for a in arch[-400:]:
        recent.setdefault(a['topic'], []).append({'title': a['title'], 'hook': a['text'].split('.')[0][:120], 'core_idea': a.get('core_idea', '')})
    n_cta = sum(1 for a in arch if a.get('cta'))
    return {'now': now.isoformat(timespec='minutes'), 'missing': missing,
            'recentByTopic': {t: recent.get(t, [])[-12:] for t in {m['topic'] for m in missing}},
            'ctaHint': 'every video now ends with the subscribe line automatically; set "cta": true in new scripts'}


if __name__ == '__main__':
    a = sys.argv
    days = int(a[a.index('--days') + 1]) if '--days' in a else CFG['schedule']['bufferDays']
    start = dt.date.fromisoformat(a[a.index('--from') + 1]) if '--from' in a else None
    print(json.dumps(plan(days, start), indent=1))
