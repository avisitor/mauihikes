"""Facebook event creation module using Playwright."""

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from playwright_stealth import Stealth
from datetime import datetime
import time

from config import TEMP_IMAGE_PATH, PLAYWRIGHT_PROFILE
from utils import sleep, download_image


class FacebookEventCreator:
    def __init__(self, event_create_url: str, group_events_url: str):
        self.event_create_url = event_create_url  # /events/create/...
        self.group_events_url = group_events_url  # /groups/<id>/events/
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.events_created = 0
        self._setup_browser()

    def _setup_browser(self):
        """Configure and initialize Playwright browser with persistent context."""
        self.playwright = sync_playwright().start()

        # Use persistent context with Chrome profile to maintain login state
        # This uses the same profile as the Selenium version, sharing the logged-in session
        # Stealth args help avoid headless detection by Facebook
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=PLAYWRIGHT_PROFILE,
            headless=True,
            executable_path="/usr/bin/chromium-browser",  # Use system Chromium
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

        self.page = self.context.new_page()
        Stealth().apply_stealth_sync(
            self.page
        )  # Apply stealth patches to avoid headless detection

    def _force_load_events(self):
        """Scroll the events page to trigger lazy loading."""
        try:
            last_height = self.page.evaluate("document.body.scrollHeight")

            for _ in range(5):
                old_height = self.page.evaluate("document.body.scrollHeight")
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

                try:
                    self.page.wait_for_function(
                        f"document.body.scrollHeight !== {old_height}", timeout=3000
                    )
                except:
                    pass

                new_height = self.page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

        except Exception as e:
            print(f"Scrolling error: {e}")

    def _event_already_exists(self, title: str, date: str) -> bool:
        try:
            print("Checking for existing events on group events page...")

            self.page.goto(self.group_events_url)
            self.page.wait_for_load_state("domcontentloaded")
            sleep(2)

            self._force_load_events()
            self.page.goto(self.group_events_url)
            self.page.wait_for_load_state("domcontentloaded")
            sleep(2)

            self._force_load_events()
            self._expand_all_events()

            # Normalize date: "Feb 20, 2026" -> "feb 20"
            # Use %-d to avoid leading zeros (e.g., "mar 7" not "mar 07")
            # since Facebook displays dates without leading zeros
            try:
                dt = datetime.strptime(date, "%b %d, %Y")
                month_day = dt.strftime("%b %-d").lower()
            except:
                month_day = date.lower()

            # SELECT THE REAL EVENT CARDS
            cards = self.page.query_selector_all(
                "div.x14vqqas.x1nb4dca.x1q0q8m5.xso031l.xsag5q8"
            )

            print(f"Found {len(cards)} event cards")

            for card in cards:
                text = card.text_content().lower()

                print("---- EVENT CARD ----")
                print(text)
                print("--------------------")

                title_ok = title.lower() in text
                date_ok = month_day in text

                if title_ok and date_ok:
                    print(f"Match found for '{title}' on '{month_day}'")
                    return True

            return False

        except Exception as e:
            print(f"Error checking existing events: {e}")
            return False

    def _expand_all_events(self):
        """Click 'See more' until no additional events load."""
        last_height = self.page.evaluate("document.body.scrollHeight")
        last_count = 0

        while True:
            # Count current event cards
            cards = self.page.query_selector_all(
                "div.x14vqqas.x1nb4dca.x1q0q8m5.xso031l.xsag5q8"
            )
            count = len(cards)

            # If count hasn't changed since last iteration, we're done
            if count == last_count:
                break

            last_count = count

            # Try clicking "See more"
            see_more = self.page.query_selector_all(
                "xpath=//span[normalize-space(text())='See more']/ancestor::div[@role='none' or @role='button']"
            )

            if not see_more:
                break

            try:
                see_more[0].click()
            except Exception:
                break

            sleep(0.5)

            # Check scroll height change
            new_height = self.page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break

            last_height = new_height

    def create_event(self, params: dict) -> None:
        """Create a Facebook event with the provided parameters."""
        try:
            print(
                f"\n=== Creating Event {self.events_created + 1}: {params['title']} ==="
            )

            # Early duplicate check on the group events list
            if self._event_already_exists(params["title"], params["date"]):
                print(
                    f"Event '{params['title']}' on {params['date']} already exists. Skipping."
                )
                return
            print(
                f"\n=== Creating Event {self.events_created + 1}: {params['title']} ==="
            )

            self.page.goto(self.event_create_url)
            self.page.wait_for_load_state("networkidle")
            print(f"Retrieved page: {self.page.title()}")
            print(f"Current URL: {self.page.url}")

            # Check if we're on the right page before proceeding
            if "events/create" not in self.page.url:
                print(f"WARNING: Redirected away from event creation page!")
                print("This may indicate a login issue or Facebook blocking.")
                raise Exception(
                    f"Redirected to {self.page.url} instead of event creation page"
                )

            self._set_event_name(params["title"])
            print("Set title")
            self._set_event_date(params["date"])
            print("Set date")
            self._set_event_time(params["meetingtime"])
            print("Set time")
            self._set_event_details(params["description"])
            print("Set description")
            self._set_event_type()
            print("Set event type")
            self._set_event_location(params["meetinglocation"])
            print("Set location")

            if params.get("imageurl"):
                self._upload_event_image(params["imageurl"])
                print("Uploaded image")

            # Try to submit the event automatically, but handle failure gracefully
            submit_success = self._submit_event()

            if not submit_success:
                print("\nMANUAL ACTION REQUIRED:")
                print(
                    "Please manually click the 'Create event' button in the browser window."
                )
                print("The script will wait for you to complete this action...")
                input("Press Enter after you have submitted the event to continue...")

            self.events_created += 1
            print(f"Event {self.events_created} processing completed.")

            sleep(2)  # Brief pause between events

        except Exception as e:
            print(f"An error occurred creating event: {e}")
            print("Attempting to continue with next event...")

    def _set_event_name(self, title: str) -> None:
        """Set the event name."""
        el = self.page.wait_for_selector(
            "xpath=//span[contains(text(), 'Event name')]/following-sibling::input[1]",
            timeout=10000,
        )
        el.fill(title)

    def _set_event_date(self, date: str) -> None:
        """Set the event date."""
        el = self.page.locator(
            "xpath=//span[contains(text(), 'Start date')]/following-sibling::div/input"
        )
        el.click()
        el.fill("")  # Clear the field
        el.evaluate("el => el.select()")
        el.fill(date)
        print(f"startdate After fill: {el.input_value()}")

    def _set_event_time(self, time: str) -> None:
        """Set the event time."""
        el = self.page.locator(
            "xpath=//span[contains(text(), 'Start time')]/following-sibling::div/input"
        )
        el.click()
        el.fill("")  # Clear the field
        el.evaluate("el => el.select()")
        el.fill(time)
        print(f"meetingtime After fill: {el.input_value()}")

    def _set_event_details(self, description: str) -> None:
        """Set the event description."""
        details = self.page.locator("textarea").first
        details.fill(description)

    def _set_event_type(self) -> None:
        """Set the event type to in-person."""
        el = self.page.locator("xpath=//span[text()='Is it in person or virtual?']")
        el.click()
        print("Clicked on in-person")

        in_person = self.page.wait_for_selector(
            "xpath=//span[text()='In person']", timeout=10000
        )
        in_person.click()
        print("clicked on In person")

    def _set_event_location(self, location: str) -> None:
        """Set the event location."""
        el = self.page.wait_for_selector(
            "xpath=//input[@aria-label='Add location']", timeout=5000
        )
        el.fill(location)
        el.press("Enter")
        el.blur()
        print("blurred meetinglocation")

        details = self.page.locator("textarea").first
        details.click()
        print("clicked on details")

    def _upload_event_image(self, image_url: str) -> None:
        """Upload an image for the event."""
        file = download_image(image_url, TEMP_IMAGE_PATH)
        if file:
            # Playwright's file input handling
            file_input = self.page.locator('input[type="file"]')
            file_input.set_input_files(file)
            self.page.wait_for_selector(
                "xpath=//img[contains(@src,'fbcdn')]", timeout=10000
            )

    def _submit_event(self) -> bool:
        """Submit the event creation form.

        Returns:
            bool: True if submission was successful, False if manual action needed
        """
        try:
            # Try multiple strategies to find and click the submit button
            submit_selectors = [
                "xpath=//span[contains(text(), 'Create event')]/ancestor::div[@role='button']",
                "xpath=//span[contains(text(), 'Create event')]/parent::div[@role='button']",
                "xpath=//div[@role='button' and .//span[contains(text(), 'Create event')]]",
                "xpath=//span[contains(text(), 'Create event')]/ancestor::span/ancestor::div/ancestor::div",
                "[aria-label*='Create']",
            ]

            submit_element = None

            # Try each selector until we find the button
            for selector in submit_selectors:
                try:
                    if selector.startswith("xpath="):
                        elements = self.page.query_selector_all(selector)
                    else:
                        elements = self.page.query_selector_all(selector)

                    if elements:
                        submit_element = elements[0]
                        print(f"Found submit button using selector: {selector}")
                        break
                except Exception as e:
                    print(f"Selector {selector} failed: {e}")
                    continue

            if not submit_element:
                print("Could not find submit button with any selector")
                return False

            tag_name = submit_element.evaluate("el => el.tagName")
            text = submit_element.text_content()
            print(f"Submit element found: {tag_name}, text: {text}")

            # Try multiple click strategies
            click_strategies = [
                lambda el: el.click(),
                lambda el: el.evaluate("el => el.click()"),
                lambda el: (
                    el.evaluate("el => el.focus()"),
                    el.evaluate("el => el.click()"),
                ),
                lambda el: (el.scroll_into_view_if_needed(), el.click()),
            ]

            for i, strategy in enumerate(click_strategies):
                try:
                    print(f"Trying click strategy {i + 1}...")
                    strategy(submit_element)
                    sleep(20)  # Wait for potential page changes

                    # Check if we're still on the same page or if submission worked
                    current_url = self.page.url
                    page_content = self.page.content()
                    if (
                        "events/create" not in current_url
                        or "Event created" in page_content
                    ):
                        print("Submit appears successful!")
                        return True

                except Exception as e:
                    print(f"Click strategy {i + 1} failed: {e}")
                    continue

            print("All automated submit attempts failed")
            return False

        except Exception as e:
            print(f"Submit error: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up the browser session."""
        try:
            print(
                f"\nCleaning up browser session... Created {self.events_created} events."
            )
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
            self.context = None
            self.playwright = None
        except Exception as e:
            print(f"Warning: Error during cleanup: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically cleanup."""
        self.cleanup()
