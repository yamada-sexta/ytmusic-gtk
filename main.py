from client import auto_login
from data import Songs
from data import AccountInfo
import logging

log = logging.getLogger(__name__)



# Init logging
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(levelname)s] %(message)s"
)


# Execution
yt = auto_login()

if yt:
    print("\n--- Running Final Verification ---")
    try:
        # 1. Get your account name/info
        data = yt.get_account_info()
        info = AccountInfo(**data)
    # log all info
        logging.info(f"Account Info: {info}")
        print(f"👤 Account: {info.account_name}")

        # 2. Fetch the titles of your last 3 played songs
        raw_history = yt.get_history()
        history = Songs.validate_python(raw_history[:3])

        # log the history data
        logging.info(f"History Data: {history[:3]}")  # Log the first
        print("\n🎵 Your Recent History:")
        for i, track in enumerate(history[:3], 1):
            title = track.title
            artist = track.artists[0].name
            print(f"  {i}. {title} - {artist}")

        # 3. Check your library size
        library = yt.get_library_playlists(limit=5)
        logging.info(f"✅ Access Confirmed: Found {len(library)} playlists in your library.")

    except Exception as e:
        logging.error(f"Verification failed: {e}")
        logging.warning(
            "This usually means the cookies found were expired or for the wrong account."
        )
