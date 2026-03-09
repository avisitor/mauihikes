"""Facebook event creation module using Playwright."""

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from playwright_stealth import Stealth
from datetime import datetime
import time
import getpass
import os
from pathlib import Path

from config import TEMP_IMAGE_PATH, PLAYWRIGHT_PROFILE
from utils import sleep, download_image


def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


# Load environment variables from .env file
load_env_file()


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
            # Use Playwright's bundled Chromium (same as login_facebook.py)
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

    def _is_login_page(self) -> bool:
        """Check if current page is a Facebook login page."""
        return "login" in self.page.url.lower()

    def _login(self) -> bool:
        """
        Prompt for credentials and log into Facebook.
        Returns True if login appears successful, False otherwise.
        """
        print("\n" + "=" * 60)
        print("LOGIN REQUIRED")
        print("=" * 60)
        print("Facebook requires authentication to create events.")
        print()

        print(f"Current URL: {self.page.url}")

        # Navigate to main login page for consistent form
        print("Navigating to Facebook login page...")
        self.page.goto("https://www.facebook.com/login")
        self.page.wait_for_load_state("networkidle")
        sleep(2)

        print(f"Login page URL: {self.page.url}")
        print(f"Page title: {self.page.title()}")

        # Debug: save screenshot to help diagnose
        try:
            self.page.screenshot(path="/tmp/fb_login_page.png")
            print("Screenshot saved to /tmp/fb_login_page.png")
        except Exception as e:
            print(f"Could not save screenshot: {e}")

        # Get credentials from environment variables, fall back to prompting
        email = os.getenv("FACEBOOK_EMAIL")
        password = os.getenv("FACEBOOK_PASSWORD")

        if email and password:
            print(f"Using credentials from .env for: {email}")
        else:
            print("No credentials found in .env, prompting...")
            email = input("Enter your Facebook email or phone: ")
            password = getpass.getpass("Enter your Facebook password: ")

        # Try multiple selectors for email field (Facebook uses different variants)
        email_selectors = [
            "#email",
            "input[name='email']",
            "input[type='email']",
            "input[type='text'][name='email']",
            "input[data-testid='royal_email']",
        ]

        password_selectors = [
            "#pass",
            "input[name='pass']",
            "input[type='password']",
            "input[data-testid='royal_pass']",
        ]

        login_button_selectors = [
            "button[name='login']",
            "button[type='submit']",
            "button[data-testid='royal_login_button']",
            "#loginbutton",
            "button:has-text('Log in')",
            "button:has-text('Log In')",
            # input[type='submit'] last as it may be hidden
            "input[type='submit']",
        ]

        try:
            # Find and fill email
            email_input = None
            for selector in email_selectors:
                email_input = self.page.query_selector(selector)
                if email_input:
                    print(f"Found email field with selector: {selector}")
                    break

            if not email_input:
                print("Could not find email input field!")
                print("Available input fields on page:")
                inputs = self.page.query_selector_all("input")
                for inp in inputs[:10]:  # Show first 10
                    try:
                        attrs = self.page.evaluate(
                            """(el) => {
                            return {
                                id: el.id,
                                name: el.name,
                                type: el.type,
                                placeholder: el.placeholder
                            }
                        }""",
                            inp,
                        )
                        print(f"  Input: {attrs}")
                    except:
                        pass
                return False

            email_input.fill(email)

            # Find and fill password
            password_input = None
            for selector in password_selectors:
                password_input = self.page.query_selector(selector)
                if password_input:
                    print(f"Found password field with selector: {selector}")
                    break

            if not password_input:
                print("Could not find password input field!")
                return False

            password_input.fill(password)

            # Find and click login button
            login_button = None
            for selector in login_button_selectors:
                btn = self.page.query_selector(selector)
                if btn:
                    # Check if button is actually visible
                    is_visible = btn.is_visible()
                    if is_visible:
                        print(f"Found visible login button with selector: {selector}")
                        login_button = btn
                        break
                    else:
                        print(
                            f"Found login button with {selector} but it's not visible, trying next..."
                        )

            if not login_button:
                print("Could not find a visible login button!")
                # Try using keyboard to submit instead
                print("Attempting to submit via Enter key...")
                password_input.press("Enter")
            else:
                login_button.click()

            # Wait for navigation
            print("Logging in...")
            self.page.wait_for_load_state("networkidle")
            sleep(3)  # Give Facebook time to process

            # Wait a bit more and check URL multiple times (Facebook redirects can be slow)
            for _ in range(3):
                current_url = self.page.url.lower()
                print(f"Checking URL: {self.page.url}")

                # Check for 2FA/verification pages first (before checking for 'login')
                if (
                    "two_step_verification" in current_url
                    or "checkpoint" in current_url
                ):
                    return self._handle_2fa()

                # Also check for 2FA input field
                if self.page.query_selector("input[name='approvals_code']"):
                    return self._handle_2fa()

                # If we're on the homepage or somewhere else that's not login, success!
                if "login" not in current_url:
                    print("Login successful!")
                    return True

                # Still on login page, wait a bit more
                sleep(2)

            # After retries, still on login
            print("Login may have failed. Current URL:", self.page.url)
            print("Please check your credentials and try again.")
            return False

        except Exception as e:
            print(f"Error during login: {e}")
            return False

    def _handle_2fa(self) -> bool:
        """Handle two-factor authentication if required."""
        print("\n" + "-" * 40)
        print("TWO-FACTOR AUTHENTICATION REQUIRED")
        print("-" * 40)

        # Save screenshot for debugging
        try:
            self.page.screenshot(path="/tmp/fb_2fa_page.png")
            print("Screenshot saved to /tmp/fb_2fa_page.png")
        except Exception as e:
            print(f"Could not save screenshot: {e}")

        print(f"2FA page URL: {self.page.url}")

        # Try different 2FA input selectors
        twofa_selectors = [
            "input[name='approvals_code']",
            "input[type='text'][autocomplete='one-time-code']",
            "input[id='approvals_code']",
            "input[type='tel']",  # Some 2FA pages use tel input
            "input[type='number']",
            "input[type='text']",  # Generic fallback
        ]

        twofa_input = None
        for selector in twofa_selectors:
            elements = self.page.query_selector_all(selector)
            for el in elements:
                if el.is_visible():
                    print(f"Found 2FA input with selector: {selector}")
                    twofa_input = el
                    break
            if twofa_input:
                break

        if not twofa_input:
            print("Could not find 2FA input field.")
            print("Looking for input fields on the page...")
            inputs = self.page.query_selector_all("input")
            for inp in inputs[:10]:
                try:
                    is_visible = inp.is_visible()
                    attrs = self.page.evaluate(
                        """(el) => {
                        return {
                            id: el.id,
                            name: el.name,
                            type: el.type,
                            placeholder: el.placeholder
                        }
                    }""",
                        inp,
                    )
                    print(f"  Input (visible={is_visible}): {attrs}")
                except:
                    pass
            print("Current URL:", self.page.url)
            return False

        code = input("Enter the 2FA code from your authenticator app or SMS: ")

        try:
            twofa_input.fill(code)

            # Find and click submit button - check visibility
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Continue')",
                "button:has-text('Submit')",
            ]

            submit_button = None
            for selector in submit_selectors:
                btn = self.page.query_selector(selector)
                if btn and btn.is_visible():
                    submit_button = btn
                    break

            if submit_button:
                submit_button.click()
            else:
                # Try pressing Enter
                print("No visible submit button found, pressing Enter...")
                twofa_input.press("Enter")

            print("Submitting 2FA code...")
            self.page.wait_for_load_state("networkidle")
            sleep(3)

            print(f"Post-2FA URL: {self.page.url}")

            # Check if we passed 2FA
            current_url = self.page.url.lower()
            if (
                "checkpoint" not in current_url
                and "login" not in current_url
                and "two_step_verification" not in current_url
            ):
                print("2FA verification successful!")
                return True
            else:
                print("2FA verification may have failed or needs additional steps.")
                print("Current URL:", self.page.url)
                # Take another screenshot
                try:
                    self.page.screenshot(path="/tmp/fb_post_2fa.png")
                    print("Screenshot saved to /tmp/fb_post_2fa.png")
                except:
                    pass
                return False

        except Exception as e:
            print(f"Error during 2FA: {e}")
            return False

    def _ensure_logged_in(self) -> bool:
        """
        Check if logged in, and if not, perform login.
        Returns True if logged in successfully, False otherwise.
        """
        if self._is_login_page():
            return self._login()
        return True

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

            # Normalize date: "Feb 20, 2026" -> multiple formats to match
            # Facebook displays dates in various formats like:
            # "sat, mar 7" or "sat, mar 7 at 9:00 am" or "mar 7"
            try:
                dt = datetime.strptime(date, "%b %d, %Y")
                # Format without leading zero: "mar 7"
                month_day = dt.strftime("%b %-d").lower()
                # Also try with leading zero: "mar 07"
                month_day_padded = dt.strftime("%b %d").lower()
                # Just the day number
                day_num = str(dt.day)
                month_abbr = dt.strftime("%b").lower()
            except:
                month_day = date.lower()
                month_day_padded = date.lower()
                day_num = ""
                month_abbr = ""

            print(f"Looking for event with title containing: '{title.lower()}'")
            print(f"Looking for date matching: '{month_day}' or '{month_day_padded}'")

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

                # Try multiple date formats
                date_ok = (
                    month_day in text
                    or month_day_padded in text
                    # Also check for month + day separately (e.g., "mar" and "14" both in text)
                    or (
                        month_abbr
                        and day_num
                        and month_abbr in text
                        and f", {day_num}" in text
                    )
                    or (
                        month_abbr
                        and day_num
                        and month_abbr in text
                        and f" {day_num}" in text
                    )
                )

                if title_ok and date_ok:
                    print(f"Match found for '{title}' on date '{month_day}'")
                    return True
                elif title_ok:
                    print(
                        f"Title match for '{title}' but date '{month_day}' not found in card"
                    )
                elif date_ok:
                    print(
                        f"Date match for '{month_day}' but title '{title}' not found in card"
                    )

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

            try:
                self.page.goto(self.event_create_url, timeout=60000)
                # Use domcontentloaded instead of networkidle - Facebook never stops making requests
                self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                sleep(3)  # Give extra time for dynamic content to load
            except Exception as nav_error:
                print(f"Navigation error: {nav_error}")
                # Save screenshot for debugging
                try:
                    self.page.screenshot(path="/tmp/fb_nav_error.png")
                    print("Screenshot saved to /tmp/fb_nav_error.png")
                except:
                    pass
                raise

            print(f"Retrieved page: {self.page.title()}")
            print(f"Current URL: {self.page.url}")

            # Check if we're on the right page before proceeding
            if "events/create" not in self.page.url:
                print(f"WARNING: Redirected away from event creation page!")

                # Check if we're on a login page and attempt to log in
                if self._is_login_page():
                    print("Detected login page - attempting to authenticate...")
                    if self._login():
                        # Retry navigating to event creation page
                        print("Retrying navigation to event creation page...")
                        self.page.goto(self.event_create_url)
                        self.page.wait_for_load_state("networkidle")
                        print(f"Current URL after login: {self.page.url}")

                        if "events/create" not in self.page.url:
                            raise Exception(
                                f"Still redirected to {self.page.url} after login"
                            )
                    else:
                        raise Exception("Login failed - cannot create events")
                else:
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
        # Wait for the page to be ready
        sleep(2)
        el = self.page.wait_for_selector(
            "xpath=//span[contains(text(), 'Event name')]/following-sibling::input[1]",
            timeout=30000,
        )
        el.type(
            title
        )  # Use type() instead of fill() - more like Selenium's send_keys()

    def _set_event_date(self, date: str) -> None:
        """Set the event date."""
        el = self.page.locator(
            "xpath=//span[contains(text(), 'Start date')]/following-sibling::div/input"
        )
        el.click()
        # Triple-click to select all text in the field
        el.click(click_count=3)
        el.type(date)
        print(f"startdate After fill: {el.input_value()}")

    def _set_event_time(self, time_str: str) -> None:
        """Set the event time."""
        el = self.page.locator(
            "xpath=//span[contains(text(), 'Start time')]/following-sibling::div/input"
        )
        el.click()
        # Triple-click to select all text in the field
        el.click(click_count=3)
        el.type(time_str)
        print(f"meetingtime After fill: {el.input_value()}")

    def _set_event_details(self, description: str) -> None:
        """Set the event description."""
        details = self.page.locator("textarea").first
        details.fill(description)

    def _set_event_type(self) -> None:
        """Set the event type to in-person."""
        el = self.page.locator("xpath=//span[text()='Is it in person or virtual?']")
        # Use JavaScript click to bypass overlaying elements (like Selenium does)
        el.evaluate("el => el.click()")
        print("Clicked on in-person dropdown")

        in_person = self.page.wait_for_selector(
            "xpath=//span[text()='In person']", timeout=10000
        )
        # Use JavaScript click here too
        in_person.evaluate("el => el.click()")
        print("clicked on In person")

    def _set_event_location(self, location: str) -> None:
        """Set the event location."""
        el = self.page.wait_for_selector(
            "xpath=//input[@aria-label='Add location']", timeout=5000
        )
        el.fill(location)
        el.press("Enter")
        # Use JavaScript to blur since Playwright ElementHandle doesn't have blur()
        el.evaluate("el => el.blur()")
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
