# TikTok quality test report for 0.1.5

Date: 2026-08-14

Update on 2026-08-14:

- Direct TikTok download is capped at Full HD/60 FPS where such a clean stream is
  available. Higher output sizes belong to the separate Upscale step.
- 1440p/2160p are upscale targets only. If the downloaded source is lower and
  the user enables Upscale, the app can process the file up to that target after
  download. This is labeled as processing, not source quality.
- Current experiments confirmed repeated Full HD candidates and some 60 FPS
  files through the independent app providers.

Scope: real download candidates from public TikTok videos and profiles:
`@karyselka_edits`, `@willsmith`, and `@tiktok`.
The tables record what the application-side fallback providers returned and what
`ffprobe` verified after download. They do not claim source quality that was not
present in the downloaded file.

Profile and collection checks:

| Target | Result | Details |
| --- | --- | --- |
| `https://www.tiktok.com/@karyselka_edits` | OK | 5 sample videos extracted |
| `https://www.tiktok.com/@willsmith` | OK | 5 sample videos extracted |
| `https://www.tiktok.com/@tiktok` | OK | 5 sample videos extracted |
| Collections/playlists on tested profiles | NOT FOUND | Lightweight profile scan did not expose public `/collection/` links |

`@milkapnacznfan` independent TikWM/ffprobe check on 2026-08-14:

| TikTok video id | Provider/candidate | Result | Verified quality | FPS | Codec | Audio | Watermark status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 7625040344861789460 | TikWM HD/original | OK | 720×1280 | 30 | H.265 | AAC | no-watermark candidate |
| 7624212645020798228 | TikWM HD/original | OK | 1080×1080 | 60 | H.265 | AAC | no-watermark candidate |
| 7622374632158481684 | TikWM HD/original | OK | 1080×1920 | 60 | H.265 | AAC | no-watermark candidate |
| 7622028691236801812 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | AAC | no-watermark candidate |
| 7620780157355298069 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | AAC | no-watermark candidate |
| 7620545422284655893 | TikWM HD/original | OK | 576×630 | 30 | H.264 | AAC | no-watermark candidate |
| 7620010482304404757 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | AAC | no-watermark candidate |
| 7619430914468187412 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | AAC | no-watermark candidate |
| 7618705116018822421 | TikWM HD/original | OK | 1080×1384 | 60 | H.265 | AAC | no-watermark candidate |
| 7617871353856757012 | TikWM HD/original | OK | 1080×1920 | 60 | H.265 | AAC | no-watermark candidate |

`@milkapnacznfan` background catalog quality timing on 2026-08-14:

| Metric | Result |
| --- | --- |
| Profile cards appeared | 4.83 s |
| Cards in profile | 39 |
| Verified cards by 10 s after profile appeared | 2-4 in repeated runs |
| Verified cards by 20 s after profile appeared | 9-10 in repeated runs |
| Verified cards after full background pass | 38 / 39 |
| Full background pass duration | 64.34 s after profile appeared |
| Known miss | 1 TikWM CDN candidate did not expose a valid ffprobe video stream |

| TikTok video id | Provider/candidate | Result | Verified quality | FPS | Codec | Audio | Watermark status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 7622374632158481684 | ssstik Full HD htmx | OK | 1080×1920 | 60 | H.265 | AAC | no-watermark original candidate |
| 7622374632158481684 | ssstik no-watermark | OK | 576×1024 | 30 | H.264 | AAC | no-watermark candidate |
| 7672908406939815200 | TikWM HD/original | OK | 1080×1440 | 60 | H.265 | AAC | no-watermark candidate |
| 7672908406939815200 | ssstik Full HD | FAILED | HTML response, not video | — | — | — | not verified |
| 7672908406939815200 | TikWM no-watermark | OK | 576×768 | 30 | H.264 | AAC | no-watermark candidate |
| 7672908406939815200 | ssstik no-watermark | OK | 576×768 | 30 | H.264 | AAC | no-watermark candidate |
| 7667469441751338272 | TikWM HD/original | OK | 720×1280 | 30 | H.265 | AAC | no-watermark candidate |
| 7667469441751338272 | ssstik Full HD | FAILED | HTML response, not video | — | — | — | not verified |
| 7667469441751338272 | TikWM no-watermark | OK | 576×1024 | 30 | H.264 | AAC | no-watermark candidate |
| 7666885945098095904 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | AAC | no-watermark candidate |
| 7666885745914776864 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | not rechecked | no-watermark candidate |
| 7666885078689140000 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | not rechecked | no-watermark candidate |
| 7666885078689140000 | ssstik Full HD | FAILED | HTML response, not video | — | — | — | not verified |
| 7660895656227228961 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | not rechecked | no-watermark candidate |
| 7660895656227228961 | ssstik Full HD | FAILED | HTML response, not video | — | — | — | not verified |
| 7657961583426948385 | TikWM HD/original | OK | 1080×1080 | 60 | H.265 | AAC | no-watermark candidate |
| 7657961583426948385 | TikWM no-watermark | OK | 576×576 | 30 | H.264 | AAC | no-watermark candidate |
| 7650337586845699360 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | not rechecked | no-watermark candidate |
| 7650337586845699360 | ssstik Full HD | FAILED | HTML response, not video | — | — | — | not verified |
| 7474304960574786859 | TikWM HD/original | OK | 1080×1920 | 30 | H.265 | AAC | no-watermark candidate |
| 7474304960574786859 | TikWM no-watermark | OK | 576×1024 | 30 | H.264 | AAC | no-watermark candidate |
| 7474304960574786859 | ssstik Full HD | FAILED | HTML response, not video | — | — | — | not verified |
| 7474304960574786859 | ssstik no-watermark | OK | 576×1024 | 30 | H.264 | AAC | no-watermark candidate |

Best verified results from the expanded matrix:

| Account | Link | Best provider | Verified quality | FPS | Codec | Audio | Watermark status | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `@milkapnacznfan` | `https://www.tiktok.com/@milkapnacznfan/video/7622374632158481684` | ssstik Full HD htmx | 1080×1920 | 60 | H.265 | AAC | no-watermark original candidate | OK |
| `@karyselka_edits` | `https://www.tiktok.com/@karyselka_edits/video/7672908406939815200` | TikWM HD/original | 1080×1440 | 60 | H.265 | AAC | no-watermark candidate | OK |
| `@karyselka_edits` | `https://www.tiktok.com/@karyselka_edits/video/7657961583426948385` | TikWM HD/original | 1080×1080 | 60 | H.265 | AAC | no-watermark candidate | OK |
| `@karyselka_edits` | `https://www.tiktok.com/@karyselka_edits/video/7667469441751338272` | TikWM HD/original | 720×1280 | 30 | H.265 | AAC | no-watermark candidate | OK |
| `@karyselka_edits` | `https://www.tiktok.com/@karyselka_edits/video/7666885945098095904` | TikWM HD/original | 576×1024 | 30 | H.264 | AAC | no-watermark candidate | OK |
| `@willsmith` | `https://www.tiktok.com/@willsmith/video/7474304960574786859` | TikWM HD/original | 1080×1920 | 30 | H.265 | AAC | no-watermark candidate | OK |
| `@willsmith` | `https://www.tiktok.com/@willsmith/video/7665013146339347726` | TikWM HD/original | 720×1280 | 30 | H.265 | AAC | no-watermark candidate | OK |
| `@willsmith` | `https://www.tiktok.com/@willsmith/video/7607555281492512030` | TikWM HD/original | 1080×1920 | 30 | H.265 | AAC | no-watermark candidate | OK |
| `@willsmith` | `https://www.tiktok.com/@willsmith/video/7606540755812814093` | TikWM HD/original | 1080×1920 | 30 | H.265 | AAC | no-watermark candidate | OK |
| `@tiktok` | `https://www.tiktok.com/@tiktok/video/7670293981833612574` | TikWM HD/original | 1080×1920 | 30 | H.265 | AAC | no-watermark candidate | OK |
| `@tiktok` | `https://www.tiktok.com/@tiktok/video/7669840443797966110` | TikWM HD/original | 1080×1920 | 30 | H.265 | AAC | no-watermark candidate | OK |
| `@tiktok` | `https://www.tiktok.com/@tiktok/video/7668726289376808222` | TikWM HD/original | 1080×1920 | 24 | H.265 | AAC | no-watermark candidate | OK |

Conclusion:

- Full HD/60 FPS is available for some TikTok videos through TikWM HD/original.
- Full HD is not stable for every tested profile video; several videos only
  produced 576p or 720p through automated no-watermark providers.
- TikWM HD/original repeatedly reached 1080p on several videos.
- The ssstik Full HD htmx capture is kept in this report only as evidence that
  TikTok can expose a higher-quality `_original.mp4` asset. The application does
  not use ssstik as a production download or preview provider.
- The production downloader uses independent candidates and verifies the real
  downloaded file with ffprobe before showing quality in the UI.
- Catalog cards no longer treat preliminary TikTok metadata as final truth.
  The profile appears first, then the first visible cards are updated in the
  background with verified TikWM/ffprobe downloadable quality.
- Background verification is rate-limit aware: TikWM API discovery is throttled
  and retried, while CDN ffprobe checks can run in parallel. This avoids turning
  profile opening into a minute-long wait while still filling real quality for
  the full catalog in the background.
- The downloader now probes audio streams too and ranks TikTok candidates as
  playable media first: audio + video is preferred before a higher-resolution
  silent file.
- The ssstik HD web flow depends on an htmx generator step. That finding explains
  why Full HD exists, but it is not a dependency of the app.
- A public TikTok URL discussed elsewhere as a large-source example was also
  tested; the current automated providers returned 1080p at best.
- Upscaling is therefore implemented as an explicit post-download option, not as
  a replacement for real source quality.
