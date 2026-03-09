"""Facebook event creation module using Selenium WebDriver."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

from config import CHROME_PROFILE, TEMP_IMAGE_PATH
from utils import sleep, download_image
from datetime import datetime

class FacebookEventCreator:
    def __init__(self, event_create_url: str, group_events_url: str):
        self.event_create_url = event_create_url      # /events/create/...
        self.group_events_url = group_events_url      # /groups/<id>/events/
        self.driver = self._setup_driver()
        self.events_created = 0

    def _setup_driver(self):
        """Configure and initialize Chrome WebDriver."""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument(f"--user-data-dir={CHROME_PROFILE}")

        # Configure content settings
        content_settings = {'notifications': 0, 'geolocation': 0}
        prefs = {'profile': {'managed_default_content_settings': content_settings}}
        chrome_options.add_experimental_option('prefs', prefs)
        chrome_options.add_argument('--disable-notifications')

        return webdriver.Chrome(options=chrome_options)

    def _force_load_events(self):
        """Scroll the events page to trigger lazy loading."""
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")

            for _ in range(5):
                old_height = self.driver.execute_script("return document.body.scrollHeight")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

                WebDriverWait(self.driver, 3).until(
                    lambda d: d.execute_script("return document.body.scrollHeight") != old_height
                )
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

        except Exception as e:
            print(f"Scrolling error: {e}")

    def _event_already_exists(self, title: str, date: str) -> bool:
        try:
            print("Checking for existing events on group events page...")

            self.driver.get(self.group_events_url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            sleep(2)

            self._force_load_events()
            self.driver.get(self.group_events_url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            sleep(2)

            self._force_load_events()
            self._expand_all_events()

            # Normalize date: "Feb 20, 2026" → "Feb 20"
            try:
                dt = datetime.strptime(date, "%b %d, %Y")
                month_day = dt.strftime("%b %d").lower()
            except:
                month_day = date.lower()

            # SELECT THE REAL EVENT CARDS
            cards = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div.x14vqqas.x1nb4dca.x1q0q8m5.xso031l.xsag5q8"
            )

            print(f"Found {len(cards)} event cards")

            for card in cards:
                text = card.text.lower()

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
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        last_count = 0

        while True:
            # Count current event cards
            cards = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div.x14vqqas.x1nb4dca.x1q0q8m5.xso031l.xsag5q8"
            )
            count = len(cards)

            # If count hasn't changed since last iteration, we're done
            if count == last_count:
                break

            last_count = count

            # Try clicking "See more"
            see_more = self.driver.find_elements(
                By.XPATH,
                "//span[normalize-space(text())='See more']/ancestor::div[@role='none' or @role='button']"
            )

            if not see_more:
                break

            try:
                self.driver.execute_script("arguments[0].click();", see_more[0])
            except Exception:
                break

            sleep(0.5)

            # Check scroll height change
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break

            last_height = new_height

    def create_event(self, params: dict) -> None:
        """Create a Facebook event with the provided parameters."""
        try:
            print(f"\n=== Creating Event {self.events_created + 1}: {params['title']} ===")

            # Early duplicate check on the group events list
            if self._event_already_exists(params["title"], params["date"]):
                print(f"⚠️ Event '{params['title']}' on {params['date']} already exists. Skipping.")
                return
            print(f"\n=== Creating Event {self.events_created + 1}: {params['title']} ===")
            
            self.driver.get(self.event_create_url)
            print(f"Retrieved page: {self.driver.title}")
            self.driver.implicitly_wait(3)

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
            
            if params.get('imageurl'):
                self._upload_event_image(params['imageurl'])
                print("Uploaded image")
            
            # Try to submit the event automatically, but handle failure gracefully
            submit_success = self._submit_event()
            
            if not submit_success:
                print("\n⚠️  MANUAL ACTION REQUIRED:")
                print("Please manually click the 'Create event' button in the browser window.")
                print("The script will wait for you to complete this action...")
                input("Press Enter after you have submitted the event to continue...")
            
            self.events_created += 1
            print(f"✅ Event {self.events_created} processing completed.")
            
            sleep(2)  # Brief pause between events
            
        except Exception as e:
            print(f"❌ An error occurred creating event: {e}")
            print("Attempting to continue with next event...")

    def _set_event_name(self, title: str) -> None:
        """Set the event name."""
        el = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Event name')]/following-sibling::input[1]")))
        el.send_keys(title)

    def _set_event_date(self, date: str) -> None:
        """Set the event date."""
        el = self.driver.find_element("xpath", "//span[contains(text(), 'Start date')]/following-sibling::div/input")
        el.click()
        el.clear()
        self.driver.execute_script('arguments[0].select()', el)
        el.send_keys(date)
        print(f"startdate After send_keys: {el.get_attribute('value')}")

    def _set_event_time(self, time: str) -> None:
        """Set the event time."""
        el = self.driver.find_element("xpath", "//span[contains(text(), 'Start time')]/following-sibling::div/input")
        el.click()
        el.clear()
        self.driver.execute_script('arguments[0].select()', el)
        el.send_keys(time)
        print(f"meetingtime After send_keys: {el.get_attribute('value')}")

    def _set_event_details(self, description: str) -> None:
        """Set the event description."""
        details = self.driver.find_element(By.CSS_SELECTOR, "textarea")
        details.send_keys(description)

    def _set_event_type(self) -> None:
        """Set the event type to in-person."""
        el = self.driver.find_element("xpath", "//span[text()='Is it in person or virtual?']")
        self.driver.execute_script("arguments[0].click();", el)
        print("Clicked on in-person")

        #sleep(7)
        el = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[text()='In person']")))
        el.click()
        print("clicked on In person")

    def _set_event_location(self, location: str) -> None:
        """Set the event location."""
        el = WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Add location']")))
        el.send_keys(location)
        el.send_keys(Keys.RETURN)
        self.driver.execute_script("arguments[0].blur();", el)
        print("blurred meetinglocation")

        details = self.driver.find_element(By.CSS_SELECTOR, "textarea")
        details.click()
        print("clicked on details")

    def _upload_event_image(self, image_url: str) -> None:
        """Upload an image for the event."""
        file = download_image(image_url, TEMP_IMAGE_PATH)
        if file:
            el = self.driver.find_element("xpath", '//input[@type="file"]')
            el.send_keys(file)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//img[contains(@src,'fbcdn')]"))
            )

    def _submit_event(self) -> bool:
        """Submit the event creation form.
        
        Returns:
            bool: True if submission was successful, False if manual action needed
        """
        try:
            # Try multiple strategies to find and click the submit button
            submit_selectors = [
                "//span[contains(text(), 'Create event')]/ancestor::div[@role='button']",
                "//span[contains(text(), 'Create event')]/parent::div[@role='button']",
                "//div[@role='button' and .//span[contains(text(), 'Create event')]]",
                "//span[contains(text(), 'Create event')]/ancestor::span/ancestor::div/ancestor::div",
                "[aria-label*='Create']",
                "div[role='button']:has(span:contains('Create event'))"
            ]
            
            submit_element = None
            
            # Try each selector until we find the button
            for selector in submit_selectors:
                try:
                    if selector.startswith('//'):
                        # XPath selector
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        # CSS selector
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        submit_element = elements[0]
                        print(f"Found submit button using selector: {selector}")
                        break
                except Exception as e:
                    print(f"Selector {selector} failed: {e}")
                    continue
            
            if not submit_element:
                print("❌ Could not find submit button with any selector")
                return False
            
            print(f"Submit element found: {submit_element.tag_name}, text: {submit_element.text}")
            
            # Try multiple click strategies
            click_strategies = [
                lambda el: el.click(),
                lambda el: self.driver.execute_script("arguments[0].click();", el),
                lambda el: self.driver.execute_script("arguments[0].focus(); arguments[0].click();", el),
                lambda el: (self.driver.execute_script("arguments[0].scrollIntoView(true);", el), el.click())[1]
            ]
            
            for i, strategy in enumerate(click_strategies):
                try:
                    print(f"Trying click strategy {i + 1}...")
                    strategy(submit_element)
                    sleep(20)  # Wait for potential page changes
                    
                    # Check if we're still on the same page or if submission worked
                    current_url = self.driver.current_url
                    if 'events/create' not in current_url or 'Event created' in self.driver.page_source:
                        print("✅ Submit appears successful!")
                        return True
                        
                except Exception as e:
                    print(f"Click strategy {i + 1} failed: {e}")
                    continue
            
            print("❌ All automated submit attempts failed")
            return False
            
        except Exception as e:
            print(f"❌ Submit error: {e}")
            return False
    
    def cleanup(self) -> None:
        """Clean up the WebDriver session."""
        try:
            if self.driver:
                print(f"\n🧹 Cleaning up browser session... Created {self.events_created} events.")
                self.driver.quit()
                self.driver = None
        except Exception as e:
            print(f"Warning: Error during cleanup: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically cleanup."""
        self.cleanup()
