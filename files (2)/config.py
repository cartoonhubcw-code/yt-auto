"""All the settings you are likely to change live here."""

# ---- What to make each day ----
MAKE_LONG = True                          # the full 16:9 explainer video
MAKE_SHORT = True                         # a separate 9:16 YouTube Short for the same topic

# ---- Channel content ----
NICHE = "science and technology"          # what your channel is about
AUDIENCE = "curious beginners"            # who you are explaining to
LANGUAGE = "English"                      # script language
# Long video: ~150 words per minute of narration.  900 words ~ 6 minutes.
TARGET_WORDS = 900
SCENES = 12                               # number of scenes in the long video

# Short: keep it under 60 seconds.  110 words ~ 45 seconds.
SHORT_WORDS = 110
SHORT_SCENES = 5

# ---- Voice (edge-tts). List all voices:  edge-tts --list-voices ----
VOICE = "en-IN-NeerjaNeural"
VOICE_RATE = "+0%"                        # e.g. "-5%" slower, "+10%" faster
SHORT_VOICE_RATE = "+8%"                  # Shorts feel better a little faster

# ---- Video ----
FPS = 30
ANIMATED_VISUALS = True                    # free code-drawn animations (set False = stock footage only)
# Real 3D scenes (Blender, free). Used only where Gemini picks a "3d_" visual; falls back to 2D if Blender fails.
BLENDER_3D = True
BLENDER_BIN = "blender"
BLENDER_SAMPLES = 24                      # lower = faster render, noisier
BLENDER_TIMEOUT = 1200                    # seconds per 3D scene, then fallback to 2D
MAX_3D_SCENES = 1                         # long video: max 3D scenes (render time)
MAX_3D_SCENES_SHORT = 0                   # Short: keep 0 (2D animations only = fast)
CAPTIONS = True                           # burn subtitles into the video

LONG_FORMAT = dict(
    name="long", width=1280, height=720, orientation="landscape", pad=0.5,
    slide_font=72, slide_wrap=24, max_3d=MAX_3D_SCENES,
    words_per_caption=7,
    caption_style="Fontname=DejaVu Sans,Fontsize=12,Bold=1,Outline=2,Shadow=0,MarginV=36",
)
SHORT_FORMAT = dict(
    name="short", width=1080, height=1920, orientation="portrait", pad=0.25,
    slide_font=96, slide_wrap=14, max_3d=MAX_3D_SCENES_SHORT,
    words_per_caption=3,                  # 2-4 big words at a time = the "Shorts look"
    # Alignment=2 = bottom-centre. MarginV is in libass units (288 = full height), so 48 puts the
    # caption baseline ~17% above the bottom: below the animation area, above the Shorts title bar.
    caption_style=("Fontname=DejaVu Sans,Fontsize=14,Bold=1,Outline=3,Shadow=0,"
                   "Alignment=2,MarginV=48,PrimaryColour=&H00FFFFFF"),
)

# ---- YouTube ----
PUBLISH_TZ = "Asia/Kolkata"
PUBLISH_HOUR = 18                         # long video goes public at 18:00 IST ...
PUBLISH_MINUTE = 0                        # ... every day
# The Short goes public AFTER the long video, so the link in its description is not dead.
SHORT_PUBLISH_HOUR = 19
SHORT_PUBLISH_MINUTE = 30
CATEGORY_ID = "27"                        # 27 = Education, 28 = Science & Tech
MADE_FOR_KIDS = False
AI_DISCLOSURE = True                      # mark as altered/synthetic content
DEFAULT_TAGS = ["explained", "explainer"]
SHORT_TAGS = ["shorts", "youtubeshorts", "facts"]
