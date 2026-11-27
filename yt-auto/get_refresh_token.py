"""Run ONCE on your own computer to get the YouTube refresh token.

    pip install google-auth-oauthlib
    python get_refresh_token.py
"""
from google_auth_oauthlib.flow import InstalledAppFlow

client_id = input("OAuth client ID: ").strip()
client_secret = input("OAuth client secret: ").strip()

flow = InstalledAppFlow.from_client_config(
    {"installed": {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }},
    scopes=["https://www.googleapis.com/auth/youtube.upload"],
)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
print("\n=== Save this as the GitHub secret YT_REFRESH_TOKEN ===")
print(creds.refresh_token)
