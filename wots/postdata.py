"""Build the exact Metricool post for a rendered Short. python3 -m wots.postdata <id> <releaseTag>
Prints JSON with blogId, date and info (string) ready for Metricool createScheduledPost. Refuses when brandId is not set."""
import json, os, sys, datetime as dt
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = json.load(open(os.path.join(ROOT, 'config', 'channel.json')))


def build(sid, tag, at=None, nets=None):
    nets = nets or CFG['metricool'].get('networks', ['youtube'])
    if 'youtube' not in nets:
        raise SystemExit('REFUSED: youtube must always be included')
    s = json.load(open(os.path.join(ROOT, 'content', 'scripts', sid + '.json')))
    brand = CFG['metricool']['brandId']
    if not brand:
        raise SystemExit('REFUSED: config metricool.brandId is empty - the Whispers of the Soul brand is not linked yet')
    if at:
        date, time = at.split('T')
    else:
        slot = next(x for x in CFG['schedule']['slots'] if x['slot'] == s['slot'])
        date, time = s['date'], slot['time']
    tags = CFG['hashtags']['base'] + CFG['hashtags'][s['topic']]
    url = lambda f: CFG['hosting']['releaseUrl'].format(tag=tag, file=f)
    text = (f"{s['description']}\n\n{CFG['slogan']}\n\n"
            f"Spiritual ideas here are shared as reflections and beliefs, not as facts or promises.\n"
            f"{CFG['aiDisclosure']['descriptionLine']}\n\n" + ' '.join(tags))
    yt_tags = ['spirituality', 'spiritual reflection', 'inner peace', 'soul', CFG['topics'][s['topic']]['name'].lower(), 'whispers of the soul']
    info = {
        'autoPublish': True, 'draft': False, 'text': text, 'firstCommentText': '', 'descendants': [], 'hasNotReadNotes': False,
        'shortener': False, 'smartLinkData': {'ids': []}, 'mediaAltText': [],
        'media': [url(sid + '.mp4')],
        'providers': [{'network': n} for n in nets],
        'publicationDate': {'dateTime': f"{date}T{time}:00", 'timezone': CFG['schedule']['timezone']},
        'youtubeData': {'title': s['title'][:95], 'type': 'short', 'privacy': 'public', 'tags': yt_tags, 'category': 'PEOPLE_BLOGS',
                        'madeForKids': False, 'isAiGeneratedContent': CFG['aiDisclosure']['youtube_isAiGeneratedContent']},
    }
    if 'instagram' in nets:
        info['instagramData'] = {'type': 'REEL', 'showReelOnFeed': True, 'isAiGenerated': True}
    if 'tiktok' in nets:
        info['tiktokData'] = {'privacyOption': 'PUBLIC_TO_EVERYONE', 'disableComment': False, 'disableDuet': False, 'disableStitch': False,
                              'commercialContentThirdParty': False, 'commercialContentOwnBrand': False, 'autoAddMusic': False, 'isAigc': True, 'title': s['title'][:90]}
    off = dt.datetime.fromisoformat(f"{date}T{time}").replace(tzinfo=ZoneInfo(CFG['schedule']['timezone'])).strftime('%z')
    return {'blogId': str(brand), 'date': f"{date}T{time}:00{off[:3]}:{off[3:]}", 'videoThumbnailUrl': url(sid + '_thumb.jpg'), 'timezone': CFG['schedule']['timezone'],
            'thumbnail': url(sid + '_thumb.jpg'), 'info': json.dumps(info)}


if __name__ == '__main__':
    a = sys.argv  # optional: --at YYYY-MM-DDTHH:MM (in schedule.timezone) for one-off posts such as the test publication
    # optional: --networks youtube,instagram (drop a network whose Metricool account is not the expected one)
    nets = a[a.index('--networks') + 1].split(',') if '--networks' in a else None
    print(json.dumps(build(a[1], a[2], a[a.index('--at') + 1] if '--at' in a else None, nets), indent=1))
