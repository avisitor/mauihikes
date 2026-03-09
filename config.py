"""Configuration settings for the Facebook event creation system."""

# Only events on or after this date will be added to Facebook
FIRST_DATE = "2026-01-01"
LAST_DATE = "2026-12-31"

# Which Facebook page to update
PAGE = "mauihikes"

# Facebook event creation URLs
EVENT_URLS = {
    "rob": "https://www.facebook.com/events/create/?acontext=%7B%22event_action_history%22%3A[%7B%22mechanism%22%3A%22left_rail%22%2C%22surface%22%3A%22bookmark%22%7D]%2C%22ref_notif_type%22%3Anull%7D&dialog_entry_point=bookmark",
    "mauihikes": "https://www.facebook.com/events/create?acontext=%7B%22event_action_history%22%3A[%7B%22mechanism%22%3A%22upcoming_events_for_group%22%2C%22surface%22%3A%22group%22%7D]%2C%22ref_notif_type%22%3Anull%7D&dialog_entry_point=group_events_tab&group_id=1544834229140020",
}

GROUP_EVENT_URLS = {
    "mauihikes": "https://www.facebook.com/groups/SierraClubMauiHikes/events"
}

# API endpoint for future outings
OUTINGS_URL = "https://mauihikes.org/s/ops/getfutureoutings"

# Chrome user profile path (for Selenium)
CHROME_PROFILE = "/Users/robw/.config/google-chrome/Default"

# Playwright browser profile directory (stores login state)
PLAYWRIGHT_PROFILE = "/Users/robw/.playwright-profile"

# Temporary file location for downloaded images
TEMP_IMAGE_PATH = "/tmp/hike.jpg"
