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
        logging.info(f"Cookies saved to {COOKIE_CACHE}")
    except Exception as e:
        logging.error(f"Failed to save cookies: {e}")


def get_cookies_for_url(url: str) -> Optional[dict]:
    """Extract cookies for a given URL using pycookiecheat."""
    try:
        cookies_dict = firefox_cookies(url)
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


def auto_login() -> Optional[ytmusicapi.YTMusic]:
    """Automates the login process by extracting cookies from Chrome and bypassing the auth type check.

    If a cookie cache exists we prefer that data and avoid re-extraction from the browser.
    """

    # 1. Try load from cache first
    cookies_dict = load_cached_cookies()
    if cookies_dict is None:
        # 2. Get the real cookies from your Mac
        try:
            url = "https://music.youtube.com"
            cookies_dict = get_cookies_for_url(url)
            if cookies_dict is None:
                logging.error("[error] No cookies found for the specified URL.")
                return None
            # check if it is a dict instead of a list
            if not isinstance(cookies_dict, dict):
                logging.error("Unexpected cookie format: Expected a dict.")
                return None

            save_cookies(cookies_dict)
        except Exception as e:
            logging.error(f"Cookie extraction failed: {e}")
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

        logging.info("Verifying authentication...")
        yt.get_library_playlists(limit=1)
        logging.info("[success] The check has been bypassed.")
        return yt

    except Exception as e:
        logging.error(f"Setup failed: {e}")
        return None
