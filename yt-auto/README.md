# Free Daily YouTube Explainer Bot

Every day, GitHub Actions runs `main.py`, which: picks a topic -> writes a script (Gemini/Groq free tier)
-> makes the voiceover (edge-tts) -> builds the video (Pexels clips + FFmpeg + captions)
-> makes a thumbnail -> uploads to YouTube as **private with a scheduled publish time**.
YouTube flips it public at exactly the time you set. Cost: Rs 0.

## 0. Test locally first (no keys needed)
    pip install -r requirements.txt     # and install ffmpeg
    python main.py --dry-run            # creates dry_run_output.mp4

## 1. Get the free keys
| Secret | Where |
|---|---|
| `GEMINI_API_KEY` | aistudio.google.com -> Get API key (no card) |
| `GROQ_API_KEY` (optional backup) | console.groq.com -> API Keys |
| `PEXELS_API_KEY` | pexels.com/api (free). Without it you get text slides instead of footage |
| `TG_TOKEN`, `TG_CHAT` (optional) | Telegram: message @BotFather -> /newbot for the token; message your bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your chat id |

## 2. YouTube OAuth (one time)
1. console.cloud.google.com -> new project -> **APIs & Services -> Library -> YouTube Data API v3 -> Enable**.
2. **OAuth consent screen**: External, fill the basics, add your Google account as a test user.
3. **IMPORTANT: click "Publish app" so status is "In production".** If it stays in "Testing", your refresh token
   expires after 7 days and the automation silently breaks. (An unverified app is fine for your own channel;
   you will just see a "Google hasn't verified this app" warning once, click Advanced -> Continue.)
4. **Credentials -> Create credentials -> OAuth client ID -> Desktop app.** Copy client ID and secret.
5. On your PC: `python get_refresh_token.py`, log in with the Google account that owns the channel,
   and copy the printed refresh token.

## 3. GitHub
1. Create a repo and push this folder. (Public repo = unlimited free minutes. Private = 2,000 min/month, also enough.)
2. Repo -> Settings -> Secrets and variables -> Actions -> add: `GEMINI_API_KEY`, `PEXELS_API_KEY`,
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` (+ optional `GROQ_API_KEY`, `TG_TOKEN`, `TG_CHAT`).
3. Actions tab -> **daily-video -> Run workflow** to test once. Check your YouTube Studio -> Content: you should
   see a scheduled video.

## 4. Customize (config.py)
Niche, language, voice, number of scenes, publish time, category. Add your own topics to `topics.csv`
(one per line, `used` = 0). When the list runs out, the LLM invents new topics.

## Things to know
- **Timing**: the workflow runs at 12:00 IST but the video publishes at `PUBLISH_HOUR` (default 18:00 IST). GitHub cron
  can be late by several minutes; that doesn't matter because YouTube does the publishing.
- **Gemini free models change.** If a model is retired you'll get a Telegram alert; set a repo variable/secret
  `GEMINI_MODELS` (comma-separated) or rely on the Groq backup. Free-tier prompts may be used by Google.
- **Custom thumbnails** need a phone-verified channel (YouTube Studio -> Settings -> Channel -> Feature eligibility).
  The upload still succeeds without it.
- **API audit**: if uploads from your project are forced to stay private/locked, apply for the free YouTube API audit.
- **Monetization/quality**: YouTube can demonetize repetitive, mass-produced videos. Edit `topics.csv` with real,
  specific topics, review the first videos, and tune the prompt in `script_gen.py`. The LLM can make factual errors:
  skim scripts for the first week.
- **Public repo**: never commit keys (they live only in GitHub Secrets). `topics.csv` and `history.json` will be public.
