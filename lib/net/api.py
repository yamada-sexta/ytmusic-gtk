def add_path_to_sys_path():
    # Add path to sys.path
    import sys, os, pathlib, json

    # sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
    project = pathlib.Path(__file__).resolve().parent.parent.parent
    print(f"Project: {project}")
    sys.path.append(str(project))


if __name__ == "__main__":
    add_path_to_sys_path()


from lib.net.client import YTClient
from lib.data import AccountInfo
from pycookiecheat import firefox_cookies, chrome_cookies
import ytmusicapi
from typing import Optional
import os
import json
import logging

COOKIE_CACHE = "cookies.json"
BROWSER_JSON = "browser.json"


def load_cached_cookies() -> Optional[dict]:
    """Return cached cookies dict if available, otherwise None."""
    if os.path.exists(COOKIE_CACHE):
        try:
            with open(COOKIE_CACHE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    logging.info(f"[success] Loaded cookies from {COOKIE_CACHE}")
                    return data
        except Exception as e:
            logging.warning(f"Failed to read cached cookies: {e}")
    return None


def save_cookies(cookies_dict: dict):
    """Persist cookies dict to disk for reuse."""
    try:
        with open(COOKIE_CACHE, "w") as f:
            json.dump(cookies_dict, f)
        os.chmod(COOKIE_CACHE, 0o600)
        logging.info(f"Cookies saved to {COOKIE_CACHE}")
    except Exception as e:
        logging.error(f"Failed to save cookies: {e}")


def get_cookies_for_url(url: str) -> Optional[dict]:
    """Extract cookies for a given URL using pycookiecheat."""
    try:
        try:
            cookies_dict = firefox_cookies(url)
        except Exception:
            cookies_dict = None
        if cookies_dict and isinstance(cookies_dict, dict):
            logging.info(f"Extracted cookies for {url}")
            return cookies_dict

        cookies_dict = chrome_cookies(url)
        if cookies_dict and isinstance(cookies_dict, dict):
            logging.info(f"Extracted cookies for {url}")
            return cookies_dict

        logging.error(f"No cookies found for {url} in either browser.")
        return None
    except Exception as e:
        logging.error(f"Error extracting cookies for {url}: {e}")
        return None


def auto_login(force_refresh: bool = False) -> Optional[ytmusicapi.YTMusic]:
    """Automates login, with automatic fallback to fresh browser cookies if cached ones expire."""

    cookies_dict = None

    # Try load from cache unless we are forcing a refresh
    if not force_refresh:
        cookies_dict = load_cached_cookies()

    # Extract fresh cookies from the browser if no cache or forced refresh
    if cookies_dict is None:
        logging.info("Fetching fresh cookies from browser...")
        url = "https://music.youtube.com"
        cookies_dict = get_cookies_for_url(url)

        if not cookies_dict or not isinstance(cookies_dict, dict):
            logging.error("[error] Failed to get valid cookies from browser.")
            return None

        save_cookies(cookies_dict)

    cookie_string = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])

    # Reconstruct the raw headers
    raw_headers = (
        "Accept: */*\n"
        "Accept-Language: en-US,en;q=0.9\n"
        "Content-Type: application/json\n"
        "X-Goog-AuthUser: 0\n"
        "x-origin: https://music.youtube.com\n"
        "Authorization: SAPISIDHASH dummy_hash_to_bypass_check\n"
        f"Cookie: {cookie_string}"
    )

    try:
        # Official setup call
        ytmusicapi.setup(filepath=BROWSER_JSON, headers_raw=raw_headers)
        os.chmod(BROWSER_JSON, 0o600)
        yt = ytmusicapi.YTMusic(BROWSER_JSON)

        # Verify authentication
        logging.info("Verifying authentication...")
        info = yt.get_account_info()
        try:
            
            account = AccountInfo.model_validate(info)
            logging.info(f"Logged in as: {account.account_name} ({account.channel_handle})")
        except Exception as e:
            logging.error(f"Error occurred while fetching account info: {e}")
            logging.error(f"Info: {info}")
            raise ValueError("Failed to verify authentication")

        playlists = yt.get_library_playlists(limit=1)
        if not playlists:
            logging.warning(
                "Authentication succeeded but failed to fetch playlists. Check your session."
            )
            raise ValueError("Expired cookies")
        logging.info("[success] Authentication verified.")
        return yt

    except Exception as e:
        # If verification fails and we haven't forced a refresh yet, the cache is stale.
        if not force_refresh:
            logging.warning(
                f"Auth failed (cookies likely expired). Refreshing from browser... Error: {e}"
            )
            # Recursively call auto_login, but force it to grab fresh cookies
            return auto_login(force_refresh=True)
        else:
            # If it fails even with fresh browser cookies, your actual browser session is logged out.
            logging.error(
                f"Setup failed even with fresh browser cookies. Please log into YT Music in Chrome/Firefox. Error: {e}"
            )
            return None


def main():
    # add_path_to_sys_path()
    yt = auto_login()
    if not yt:

        return
    playlists = yt.get_library_playlists(limit=2)
    import json

    with open("debug_playlists.json", "w") as f:
        json.dump(playlists, f, indent=2)

    print(playlists)


if __name__ == "__main__":
    main()
