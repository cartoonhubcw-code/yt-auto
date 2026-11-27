"""All the settings you are likely to change live here."""

# ---- Channel content ----
NICHE = "science and technology"          # what your channel is about
AUDIENCE = "curious beginners"            # who you are explaining to
LANGUAGE = "English"                      # script language
TARGET_WORDS = 180                        # ~75-90 sec of narration
SCENES = 7                                # number of scenes (clips) per video

# ---- Voice (edge-tts). List all voices:  edge-tts --list-voices ----
VOICE = "en-IN-NeerjaNeural"
VOICE_RATE = "+0%"                        # e.g. "-5%" slower, "+10%" faster

# ---- Video ----
WIDTH, HEIGHT, FPS = 1280, 720, 30
CAPTIONS = True                           # burn subtitles into the video

# ---- YouTube ----
PUBLISH_TZ = "Asia/Kolkata"
PUBLISH_HOUR = 18                         # video goes public at 18:00 IST ...
PUBLISH_MINUTE = 0                        # ... every day
CATEGORY_ID = "27"                        # 27 = Education, 28 = Science & Tech
MADE_FOR_KIDS = False
AI_DISCLOSURE = True                      # mark as altered/synthetic content
DEFAULT_TAGS = ["explained", "explainer"]
