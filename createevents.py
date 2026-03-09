"""Main script for creating Facebook events from Maui Hikes outings."""

import requests
import certifi
import argparse
from config import FIRST_DATE, LAST_DATE, PAGE, EVENT_URLS, GROUP_EVENT_URLS, OUTINGS_URL
from facebook_event_playwright import FacebookEventCreator
from utils import convert_date_format, add_am_if_missing
def parse_arguments():
    """Parse command line arguments to override default configuration."""
    parser = argparse.ArgumentParser(description='Create Facebook events from Maui Hikes outings.')
    parser.add_argument('--first-date', type=str, default=FIRST_DATE,
                        help=f'Only create events on or after this date (YYYY-MM-DD). Default: {FIRST_DATE}')
    parser.add_argument('--last-date', type=str, default=LAST_DATE,
                        help=f'Only create events on or before this date (YYYY-MM-DD). Default: {LAST_DATE}')
    parser.add_argument('--date', type=str, default=None,
                        help='Only create events on this date (YYYY-MM-DD).')
    parser.add_argument('--page', type=str, default=PAGE, choices=list(EVENT_URLS.keys()),
                        help=f'Facebook page to update. Default: {PAGE}')
    return parser.parse_args()

def main():
    # Parse command line arguments
    args = parse_arguments()
    first_date = args.first_date
    last_date = args.last_date

    if args.date is not None:
        first_date = args.date
        last_date = args.date
    page = args.page
    
    print(f"Using first date: {first_date}")
    print(f"Using Facebook page: {page}")
    
    try:
        # Set up headers for API request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537',
        }

        # Get all future outings
        response = requests.get(OUTINGS_URL, verify=certifi.where(), headers=headers)
        response.raise_for_status()
        outings = response.json()
        
        # Filter outings that meet the date criteria
        filtered_outings = [outing for outing in outings if outing['date'] >= first_date and outing['date'] <= last_date]
        
        if not filtered_outings:
            print(f"No events found on or after {first_date}")
            return
        
        print(f"Found {len(filtered_outings)} events to create")
        
        # Create Facebook events for each outing using context manager
        with FacebookEventCreator(EVENT_URLS[page], GROUP_EVENT_URLS[page]) as event_creator:
            for i, outing in enumerate(filtered_outings, 1):
                # Prepare event parameters
                params = {
                    'title': outing['title'],
                    'date': convert_date_format(outing['date']),
                    'meetingtime': add_am_if_missing(outing['meetingtime']),
                    'description': outing['description'] + "\nSign up: mauihikes.org/s?id=" + str(outing['id']) + "\n",
                    'meetinglocation': outing['meetinglocation'],
                    'imageurl': outing.get('imageurl', '').strip()
                }
                
                # Log event details
                print(f"\n📅 Event {i}/{len(filtered_outings)}: {params['title']}")
                print(f"📅 Date: {params['date']}")
                print(f"⏰ Time: {params['meetingtime']}")
                print(f"📍 Location: {params['meetinglocation']}")
                
                # Create the event
                event_creator.create_event(params)
                
                # Ask user if they want to continue after each event (except the last)
                if i < len(filtered_outings):
                    print(f"\n📊 Progress: {i}/{len(filtered_outings)} events processed")
                    #continue_choice = input("Continue with next event? (y/n/q): ").strip().lower()
                    #if continue_choice in ['n', 'no', 'q', 'quit']:
                    #    print("Stopping event creation as requested.")
                    #    break
        
        print(f"\n🎉 Event creation session completed!")
                
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()


