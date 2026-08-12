# TikTok quality test report for 0.1.5

Date: 2026-08-12

Scope: real download candidates from the public `@karyselka_edits` TikTok profile.
The table records what the application-side fallback providers returned and what
`ffprobe` verified after download. It does not claim source quality that was not
present in the downloaded file.

| TikTok video id | Provider/candidate | Result | Verified quality | FPS | Codec | Watermark status |
| --- | --- | --- | --- | --- | --- | --- |
| 7672908406939815200 | TikWM HD/original | OK | 1080×1440 | 60 | H.265 | no-watermark candidate |
| 7672908406939815200 | ssstik Full HD | FAILED | HTML response, not video | — | — | not verified |
| 7667469441751338272 | TikWM HD/original | OK | 720×1280 | 30 | H.265 | no-watermark candidate |
| 7667469441751338272 | ssstik Full HD | FAILED | HTML response, not video | — | — | not verified |
| 7666885945098095904 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | no-watermark candidate |
| 7666885745914776864 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | no-watermark candidate |
| 7666885078689140000 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | no-watermark candidate |
| 7666885078689140000 | ssstik Full HD | FAILED | HTML response, not video | — | — | not verified |
| 7660895656227228961 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | no-watermark candidate |
| 7660895656227228961 | ssstik Full HD | FAILED | HTML response, not video | — | — | not verified |
| 7657961583426948385 | TikWM HD/original | OK | 1080×1080 | 60 | H.265 | no-watermark candidate |
| 7650337586845699360 | TikWM HD/original | OK | 576×1024 | 30 | H.264 | no-watermark candidate |
| 7650337586845699360 | ssstik Full HD | FAILED | HTML response, not video | — | — | not verified |
| 7474304960574786859 | TikWM HD/original | OK | 1080×1920 | 30 | H.265 | no-watermark candidate |
| 7474304960574786859 | TikWM no-watermark | OK | 576×1024 | 30 | H.264 | no-watermark candidate |
| 7474304960574786859 | ssstik Full HD | FAILED | HTML response, not video | — | — | not verified |
| 7474304960574786859 | ssstik no-watermark | OK | 576×1024 | 30 | H.264 | no-watermark candidate |

Conclusion:

- Full HD/60 FPS is available for some TikTok videos through TikWM HD/original.
- Full HD is not stable for every tested profile video; several videos only
  produced 576p or 720p through automated no-watermark providers.
- The ssstik HD web flow was not usable as a normal automated provider in this
  test because its HD candidate returned HTML instead of an MP4 stream. This
  matches the observed manual site behavior where HD may depend on a human
  browser/ad/Cloudflare step.
- A public TikTok URL discussed as a 4K example in yt-dlp issue 14172 was also
  tested; the current automated providers returned 1080p at best, not 4K.
- Upscaling is therefore implemented as an explicit post-download option, not as
  a replacement for real source quality.
