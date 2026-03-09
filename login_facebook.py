#!/usr/bin/env python3
"""
Login to Facebook using Playwright in headed mode.

This script opens a visible browser window where you can manually log into Facebook.
The session will be saved to the Playwright profile directory for use by createevents.py.

Usage: python login_facebook.py
"""

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from config import PLAYWRIGHT_PROFILE


def main():
    print(f"Opening browser with profile at: {PLAYWRIGHT_PROFILE}")
    print("Please log into Facebook in the browser window that opens.")
    print(
        "After logging in successfully, close the browser window to save the session."
    )
    print()

    with sync_playwright() as playwright:
        # Launch in HEADED mode (headless=False) so you can interact
        # IMPORTANT: Use the same browser args, viewport, user_agent, and locale
        # as facebook_event_playwright.py to maintain consistent fingerprint
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=PLAYWRIGHT_PROFILE,
            headless=False,  # Show the browser window
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-notifications",
                "--disable-geolocation",
                "--no-sandbox",
            ],
            permissions=[],  # Deny all permissions by default
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            locale="en-US",
        )

        page = context.new_page()
        Stealth().apply_stealth_sync(
            page
        )  # Match stealth patches from facebook_event_playwright.py
        page.goto("https://www.facebook.com/")

        print("Browser opened. Log in to Facebook, then close the browser window.")
        print("Waiting for browser to close...")

        # Wait for the user to close the browser
        try:
            page.wait_for_event("close", timeout=0)  # Wait forever
        except:
            pass

        context.close()
        print("Session saved! You can now run createevents.py")


if __name__ == "__main__":
    main()
