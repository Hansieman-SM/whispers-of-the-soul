# Whispers of the Soul – instructions for Claude

Owner: Hans (speaks Dutch – always write to him in Dutch). Everything published is in **English**.
Channel: https://www.youtube.com/@WhispersoftheSoulChannel (channel ID UCQm6OQ778XEs7kJ-SoCx_ug), adults, international.
Slogan: **Pause. Breathe. Listen within.** Config: `config/channel.json` (single source of truth).

This project is completely separate from Still Waters Daily and Toet Toet and Friends. Never touch their repos,
Metricool brands (7823324, 7587077) or posts.

## Hard rules
- **Pause switch:** if `config/channel.json` has `"paused": true`, do nothing except send Hans one line that production is paused.
- Publish only to the Metricool brand in `metricool.brandId` and only if that brand's `networksData.youtubeData` equals
  `youtubeChannelId` (check with getBrandSettings every run). If brandId is null or the channel does not match: schedule nothing, tell Hans.
- Never publish immediately; always schedule ahead (rolling buffer `schedule.bufferDays` = 7 days = 21 videos).
- Never schedule a video that failed textcheck, render, QC or the visual contact-sheet check. A gap in the schedule is better than a bad video.
- No duplicates: before scheduling check `state/posts.json` AND Metricool getScheduledPosts for that date/slot. Record every Metricool
  post id in `state/posts.json` immediately after it is created; on a retry, look the post up first instead of creating it again.
- Keys/tokens never go into this repo.

## Content rules (from Hans's brief – apply to every script)
- Original English, warm, meaningful, accessible, natural. Viewer should feel recognition, calm, comfort, wonder or a new insight.
- Structure: a strong first sentence that meets a feeling or question; ONE clear thought with real depth; a calm, meaningful close.
  Vary structure, rhythm and openings – no filler, no forced rhymes, not the same template every time.
- No invented quotes and no attributions to known spiritual teachers.
- Treat spiritual ideas as beliefs, traditions, possibilities or personal reflection ("many traditions describe…", "some people sense…",
  "perhaps…"). Past lives, angels, parallel worlds, the afterlife, spirit world, guides are never presented as established fact.
- No predictions or guarantees about money, healing, reunion or contact with the deceased. No fear, no emotional pressure,
  no "share this to receive your blessing".
- Twin flames / soulmates: mutual respect, freedom and healthy boundaries are central. Pain, rejection or crossed boundaries are never
  proof of a destined bond. Regression imagery is never presented as reliable memory or historical evidence.
- 88–128 words (≈ 36–52 s incl. outro). Title ≤ 90 chars, no clickbait, no ALL CAPS. `description`: 1–2 calm sentences.
- About every 3rd video `"cta": true` (adds a small "Follow for daily whispers" under the slogan at the end).

## Script file
`content/scripts/<date>-<slot>-<topic>.json`:
`{"id","date","slot","category","topic","title","core_idea","text","description","cta"}` (optional `"scene"` from the topic's scene list).
After it is scheduled, append one line with the same fields to `content/archive.jsonl` (the memory against repetition).

## Pipeline
- `python3 -m wots.plan` → which date/slot/topic is missing in the buffer + recent hooks/ideas per topic (avoid them).
- `python3 -m wots.textcheck content/scripts/<id>.json` → must print OK (length, banned claims, pressure language, invented quotes,
  belief framing, overlap with the archive, repeated openings/titles/core ideas). Rewrite until OK – never weaken the checker.
- Push to main → GitHub Actions `.github/workflows/render.yml` renders each new script (Kokoro voice af_heart, generative music,
  procedural visuals, captions, thumbnail), runs `wots.qc`, makes the contact sheet and publishes a release with tag = script id:
  `https://github.com/Hansieman-SM/whispers-of-the-soul/releases/download/<id>/<id>.mp4` (+ `_thumb.jpg`, `.meta.json`, `.qc.json`, `_sheet.jpg`).
  Failed items go to the prerelease `render-logs`.
- Local render is also possible (`bash tools/get_models.sh; python3 -m wots.render content/scripts/<id>.json out/<id>`).
- Visual check: download `<id>_sheet.jpg` and LOOK at it: captions readable, inside the frame, nothing covering them, no artefacts,
  no black/empty frames. Reject and fix otherwise.
- `python3 -m wots.postdata <id> <id>` → exact Metricool payload (blogId, date, info). Then call Metricool createScheduledPost with it.
  Also try `videoThumbnailUrl` = the thumbnail URL; if Metricool rejects it (VIDEO_THUMBNAIL_NOT_APPLICABLE), schedule without it.
  YouTube: type "short", madeForKids false, isAiGeneratedContent true (synthetic narration), category PEOPLE_BLOGS.
- Times: `schedule.slots` in America/New_York (06:30 Inner Wisdom, 12:00 Soul Connections, 18:00 Beyond the Visible). Metricool gets the
  IANA zone per post, so daylight-saving changes are handled automatically.

## Daily run (scheduled task)
1. `git pull`. Pause switch. getBrandSettings: brand + channel check.
2. Failures: getScheduledPosts for the past 2 days and the next 8 (extendedRange). Any provider in ERROR, or PENDING > 30 min after its
   time: fix if possible (updateScheduledPost to a time ≥ 15 min ahead, same content) – max 2 attempts per post, tracked in state.
   If it needs Hans (disconnected account, permissions, limits), tell him exactly what to do.
3. Reconcile `state/posts.json` with Metricool (published / scheduled / failed).
4. `wots.plan` → write the missing scripts (normally 3: day +7), textcheck until OK, commit + push, wait for the Actions run
   (`gh` is not authenticated in scheduled sessions; poll `https://api.github.com/repos/Hansieman-SM/whispers-of-the-soul/releases/tags/<id>`
   with curl, max ~25 min). Retry a failed render once via a small fix + push. Still failing → do not schedule, tell Hans.
5. QC json pass + sheet looked at → schedule → save post ids in state → append to archive → commit + push.
6. Stock check: count scheduled future posts. Fewer than 15 → catch up (up to 9 scripts in one run).
7. Report: if everything is fine, end with one Dutch line `Whispers: N video's ingepland t/m <datum>, geen problemen.` (no push).
   If anything failed or needs Hans: SendUserMessage + PushNotification in Dutch: what failed, what was fixed, what he must do.

## State
`state/posts.json`: `{"posts": {"<id>": {"date","slot","status": "scripted|rendered|scheduled|published|failed","release","metricoolId","plannerUrl","attempts"}}}`
