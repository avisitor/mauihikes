"""Utility functions for date formatting, time handling, and image downloading."""

import os
import time
import requests
from datetime import datetime

def sleep(seconds: int) -> None:
    """Sleep for the specified number of seconds with a print message."""
    print("Sleeping", seconds)
    time.sleep(seconds)

def convert_date_format(date_str: str) -> str:
    """Convert date from YYYY-MM-DD to MMM DD, YYYY format."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return date_obj.strftime("%b %d, %Y")

def add_am_if_missing(time_str: str) -> str:
    """Add AM suffix to time string if no AM/PM designation exists."""
    if "am" not in time_str.lower() and "pm" not in time_str.lower():
        return time_str + " AM"
    return time_str

def download_image(image_url: str, file_name: str) -> str:
    """Download an image from URL and save to specified file path."""
    try:
        if os.path.exists(file_name):
            os.unlink(file_name)
            
        response = requests.get(image_url)
        response.raise_for_status()
        
        with open(file_name, 'wb') as file:
            file.write(response.content)
        
        print(f"Image successfully downloaded: {file_name}")
        return file_name
    except Exception as e:
        print(f"An error occurred: {e}")
        return ""
