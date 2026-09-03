# API Limitations — what cannot be automated, and why

This file exists because the brief asked for no fake automation. Everything below is a
real constraint imposed by the platforms or by physics, not a gap in this codebase. Where
the system cannot do something, it says `NOT SUPPORTED BY CURRENT API` in the UI and
routes the work to a human instead of pretending.

## Blocking limitations

### 1. TikTok posts are private until your app passes audit
Unaudited API clients have **all** their posts forced to `SELF_ONLY` visibility. No
parameter changes this. Audit takes ~2–4 weeks with multiple review rounds.
**Consequence:** TikTok automation works end-to-end from day one, but nobody but you can
see the results until audit passes. The account card in the dashboard shows
`AUDIT PENDING — POSTS WILL BE PRIVATE` so this is never a surprise.

### 2. Instagram and TikTok cannot schedule
Neither API accepts a future publish time. This system's scheduler does the waiting.
**Consequence:** the worker must be running and reachable at the scheduled moment. If
your worker is down at 09:00, the post goes out late (the reconciler catches up), not on
time. Facebook, which schedules natively, is unaffected.

### 3. Instagram requires publicly-fetchable media URLs
Meta's servers fetch your image/video from a URL you supply; you cannot upload bytes.
**Consequence:** S3-compatible storage with public or presigned-public read is a hard
requirement for Instagram publishing. Localhost paths will never work.

### 4. Instagram cannot delete API-published media
The Graph API exposes no delete for media it published. `deletePost()` on the Instagram
adapter throws `CapabilityNotSupportedError`.
**Consequence:** a bad post must be removed by hand in the app. This is exactly why the
QA gates run *before* publish and why autonomous mode is conservative.

### 5. There is no legitimate commercial trend feed from IG / TikTok / FB
TikTok's Research API is restricted to approved academic and nonprofit researchers.
Meta exposes nothing equivalent. Scraping is a ToS violation and an account-ban risk, so
this system does not do it.
**Consequence:** trend discovery runs on news APIs, RSS, and search providers you
configure. It is genuinely useful, but it is not "what is trending on TikTok right now",
and the product never claims it is.

### 6. Instagram analytics have been substantially withdrawn
`impressions`, `plays`, `video_views` (non-Reels), `profile_views`, `website_clicks`,
`phone_call_clicks` are deprecated — requesting them **errors**. `views` replaces them.
**Consequence:** some metrics you may expect simply do not exist any more. The unified
analytics model marks them `unavailable` rather than storing a fabricated `0`, because a
zero would poison the learning engine.

### 7. Rate limits cap volume
Instagram: **100 API posts / rolling 24h** per account (carousel = 1), ~200 calls/user/hour.
**Consequence:** the brief's "3–5 carousels + 2–4 Reels per day" is comfortably inside
this, but the publisher still checks `content_publishing_limit` before every publish and
defers rather than failing.

## Things that need money or infrastructure, not permission

### 8. Finished video rendering needs FFmpeg and paid providers
The Reel pipeline composes: script → voice → visuals → captions → render. Voice
(ElevenLabs/OpenAI), stock or generated visuals, and music are **paid third-party
services**. `FFMPEG_PATH` must point at a real FFmpeg binary.
**Status in this build:** the pipeline, provider interfaces, and the FFmpeg compositor
are implemented. Providers without credentials configured throw
`ProviderNotConfiguredError` at call time — they do not return fake media.

### 9. Fact-checking is assisted, not guaranteed
The fact checker cross-references retrieved sources. It substantially reduces the rate of
false claims; it does not eliminate it. Treat `VERIFIED` as "corroborated by retrieved
sources", not "true".

### 10. "Viral potential" is a ranking score, not a prediction
`ViralPotentialScore` orders a queue. It does not predict virality, and the UI labels it
as a ranking aid. Anyone claiming otherwise is selling something.

## Deliberate product decisions (not platform limits)

| Decision | Reason |
| --- | --- |
| No DM automation | High policy risk, negligible content value |
| No comment auto-reply in v1 | Reputational risk without human review |
| No engagement pods / follow-unfollow | ToS violation, ban risk |
| No republishing others' content without license | Copyright agent blocks it |
