import ytmusicapi
from pycookiecheat import chrome_cookies
import json
import os

# Constants for cache files
COOKIE_CACHE = "cookies.json"
BROWSER_JSON = "browser.json"


def load_cached_cookies():
    """Return cached cookies dict if available, otherwise None."""
    if os.path.exists(COOKIE_CACHE):
        try:
            with open(COOKIE_CACHE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    print(f"✅ Loaded cookies from {COOKIE_CACHE}")
                    return data
        except Exception as e:
            print(f"⚠️ Failed to read cached cookies: {e}")
    return None


def save_cookies(cookies_dict: dict):
    """Persist cookies dict to disk for reuse."""
    try:
        with open(COOKIE_CACHE, "w") as f:
            json.dump(cookies_dict, f)
        print(f"💾 Cookies saved to {COOKIE_CACHE}")
    except Exception as e:
        print(f"⚠️ Failed to save cookies: {e}")


def auto_login():
    """Automates the login process by extracting cookies from Chrome and bypassing the auth type check.

    If a cookie cache exists we prefer that data and avoid re-extraction from the browser.
    """

    # 1. Try load from cache first
    cookies_dict = load_cached_cookies()
    if cookies_dict is None:
        # 2. Get the real cookies from your Mac
        try:
            url = "https://music.youtube.com"
            cookies_dict = chrome_cookies(url)
            save_cookies(cookies_dict)
        except Exception as e:
            print(f"❌ Cookie extraction failed: {e}")
            return None

    cookie_string = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])

    # 2. Reconstruct the raw headers
    # We add a fake Authorization header that contains the magic word 'SAPISIDHASH'
    # This tricks determine_auth_type() into returning AuthType.BROWSER
    raw_headers = (
        "Accept: */*\n"
        "Accept-Language: en-US,en;q=0.9\n"
        "Content-Type: application/json\n"
        "X-Goog-AuthUser: 0\n"
        "x-origin: https://music.youtube.com\n"
        "Authorization: SAPISIDHASH dummy_hash_to_bypass_check\n"  # <--- THE FIX
        f"Cookie: {cookie_string}"
    )

    try:
        # 3. Official setup call
        # Now it will pass the internal check and identify as 'BROWSER'
        ytmusicapi.setup(filepath="browser.json", headers_raw=raw_headers)

        # 4. Initialize
        yt = ytmusicapi.YTMusic("browser.json")

        print("Verifying authentication...")
        yt.get_library_playlists(limit=1)
        print("🚀 Success! The check has been bypassed.")
        return yt

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return None


# Execution
yt = auto_login()

if yt:
    print("\n--- Running Final Verification ---")
    try:
        # 1. Get your account name/info
        info = yt.get_account_info()
        print(f"👤 Account: {info.get('name', 'Successfully Logged In')}")

        # 2. Fetch the titles of your last 3 played songs
        history = yt.get_history()
        print("\n🎵 Your Recent History:")
        for i, track in enumerate(history[:3], 1):
            title = track.get("title")
            artist = track.get("artists")[0].get("name")
            print(f"  {i}. {title} - {artist}")

        # 3. Check your library size
        library = yt.get_library_playlists(limit=5)
        print(f"\n✅ Access Confirmed: Found {len(library)} playlists in your library.")

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        print(
            "This usually means the cookies found were expired or for the wrong account."
        )
