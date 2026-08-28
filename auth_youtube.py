import os
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow


def main():
    load_dotenv()
    
    client_id = os.getenv("YT_CLIENT_ID")
    client_secret = os.getenv("YT_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("❌ Error: YT_CLIENT_ID or YT_CLIENT_SECRET missing in .env")
        return

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"]
        }
    }

    print("Opening Google OAuth flow...")
    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=["https://www.googleapis.com/auth/youtube.force-ssl"]
    )
    
    # This will open a browser window for you to log in
    creds = flow.run_local_server(port=0)

    if not creds.refresh_token:
        print("❌ No refresh token received! You might need to go to your Google Account > Security > Manage Third Party Access, revoke ReplyMind, and try this script again.")
        return

    out_dir = Path("secrets")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "refresh_token.txt"
    out_file.write_text(creds.refresh_token)
    
    print(f"\n✅ SUCCESS! Refresh token saved to {out_file}")
    print("You can now go back to the web UI and hit 'Fetch'!")

if __name__ == "__main__":
    main()
