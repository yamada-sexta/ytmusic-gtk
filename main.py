from data import HomePage
from data import ExploreData
import logging
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
        logging.info(f"Account Info: {info}")
        print(f"Account: {info.account_name}")

        # 2. Fetch the titles of your last 3 played songs
        raw_history = yt.get_history()
        history = Songs.validate_python(raw_history[:3])

        # log the history data
        logging.info(f"History Data: {history}")  # Log the first
        
        # Get explore
        raw_explore = yt.get_explore()
        
        # Parse the explore data
        explore_data = ExploreData.model_validate(raw_explore)
        logging.info(f"Explore Data: {explore_data}")  # Log the explore data

        raw_home = yt.get_home(limit=5)        
        # Parse the list of sections
        home_data = HomePage.validate_python(raw_home)
        # logging.info(f"Home Data: {home_data}")  # Log the home data

        for section in home_data:
            print(f"📌 Section: {section.title}")
            for item in section.contents[:2]: # Just looking at the first 2 items per section
                # If it has an author, it's likely a playlist. Otherwise, a track.
                creator = item.artists[0].name if item.artists else (item.author[0].name if item.author else "Unknown")
                print(f"   - {item.title} by {creator}")

        # 3. Check your library size
        library = yt.get_library_playlists(limit=5)
        logging.info(f"✅ Access Confirmed: Found {len(library)} playlists in your library.")

    except Exception as e:
        logging.error(f"Verification failed: {e}")
        logging.warning(
            "This usually means the cookies found were expired or for the wrong account."
        )
