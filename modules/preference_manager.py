import json
import os
from fastapi import HTTPException # Import HTTPException

PREFERENCES_FILE = os.path.join("data", "preferences.json")

def load_preferences(user_id: str) -> dict:
    """
    Loads user preferences from a JSON file.
    Raises HTTPException with status 404 if preferences for the user are not found.
    """
    if not os.path.exists(PREFERENCES_FILE):
        # If the file itself doesn't exist, no preferences have been saved at all.
        # This is a valid scenario for a new application/user.
        # We can return an empty dict or raise 404 if we strictly expect the file.
        # For now, let's return empty if the file doesn't exist, and raise 404 if user_id not in file.
        print(f"DEBUG: Preferences file not found at {PREFERENCES_FILE}. Returning empty preferences.")
        return {} # No file means no preferences for anyone yet

    with open(PREFERENCES_FILE, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"WARNING: Preferences file at {PREFERENCES_FILE} is empty or malformed. Returning empty preferences.")
            return {} # Handle empty or malformed JSON gracefully

        user_prefs = data.get(user_id)
        if user_prefs is None:
            # If the user_id is not found in the loaded data, it means preferences for this user don't exist.
            print(f"DEBUG: Preferences for user_id '{user_id}' not found in {PREFERENCES_FILE}.")
            raise HTTPException(status_code=404, detail="Preferences for this user not found.")
        
        print(f"DEBUG: Preferences loaded for user: {user_id}")
        return user_prefs

def save_preferences(user_id: str, preferences: dict):
    """
    Saves user preferences to a JSON file.
    """
    if not os.path.exists(os.path.dirname(PREFERENCES_FILE)):
        os.makedirs(os.path.dirname(PREFERENCES_FILE))
    
    data = {}
    if os.path.exists(PREFERENCES_FILE):
        with open(PREFERENCES_FILE, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {} # Handle empty or malformed JSON

    data[user_id] = preferences
    with open(PREFERENCES_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Preferences saved for user: {user_id}")
