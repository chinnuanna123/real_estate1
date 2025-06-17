import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import HTTPException

SELECTED_PROPERTIES_FILE = os.path.join("data", "selected_properties.json")

def load_selected_properties(user_id: str) -> List[Dict[str, Any]]:
    """
    Load user's selected properties from JSON file.
    """
    if not os.path.exists(SELECTED_PROPERTIES_FILE):
        print(f"DEBUG: Selected properties file not found at {SELECTED_PROPERTIES_FILE}. Returning empty list.")
        return []

    with open(SELECTED_PROPERTIES_FILE, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"WARNING: Selected properties file at {SELECTED_PROPERTIES_FILE} is empty or malformed. Returning empty list.")
            return []

        user_selections = data.get(user_id, [])
        print(f"DEBUG: Loaded {len(user_selections)} selected properties for user: {user_id}")
        return user_selections

def save_selected_property(user_id: str, property_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Save a selected property for a user with timestamp and selection context.
    """
    if not os.path.exists(os.path.dirname(SELECTED_PROPERTIES_FILE)):
        os.makedirs(os.path.dirname(SELECTED_PROPERTIES_FILE))
    
    # Load existing data
    data = {}
    if os.path.exists(SELECTED_PROPERTIES_FILE):
        with open(SELECTED_PROPERTIES_FILE, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}

    # Initialize user's selections if not exists
    if user_id not in data:
        data[user_id] = []

    # Add metadata to property
    enhanced_property = {
        **property_data,
        "selected_at": datetime.now().isoformat(),
        "selection_id": f"sel_{len(data[user_id]) + 1}_{int(datetime.now().timestamp())}",
        "user_notes": "",  # For future user annotations
        "status": "interested"  # interested, shortlisted, visited, rejected, etc.
    }

    # Check for duplicates (same URL)
    existing_urls = [prop.get("link") for prop in data[user_id]]
    if property_data.get("link") in existing_urls:
        print(f"Property already selected by user {user_id}: {property_data.get('name')}")
        return {"status": "already_selected", "message": "Property already in your selections"}

    # Add to user's selections
    data[user_id].append(enhanced_property)

    # Save back to file
    with open(SELECTED_PROPERTIES_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    
    print(f"Selected property saved for user {user_id}: {property_data.get('name')}")
    return {"status": "success", "message": f"Property '{property_data.get('name')}' added to your selections"}

def update_property_status(user_id: str, selection_id: str, new_status: str, notes: str = "") -> Dict[str, str]:
    """
    Update status/notes for a selected property (visited, rejected, etc.)
    """
    if not os.path.exists(SELECTED_PROPERTIES_FILE):
        return {"status": "error", "message": "No selected properties found"}

    with open(SELECTED_PROPERTIES_FILE, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid data file"}

    user_selections = data.get(user_id, [])
    
    # Find and update the property
    for prop in user_selections:
        if prop.get("selection_id") == selection_id:
            prop["status"] = new_status
            prop["user_notes"] = notes
            prop["updated_at"] = datetime.now().isoformat()
            
            # Save back to file
            with open(SELECTED_PROPERTIES_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            
            return {"status": "success", "message": f"Property status updated to {new_status}"}
    
    return {"status": "error", "message": "Property not found in selections"}

def remove_selected_property(user_id: str, selection_id: str) -> Dict[str, str]:
    """
    Remove a property from user's selections
    """
    if not os.path.exists(SELECTED_PROPERTIES_FILE):
        return {"status": "error", "message": "No selected properties found"}

    with open(SELECTED_PROPERTIES_FILE, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid data file"}

    user_selections = data.get(user_id, [])
    
    # Find and remove the property
    for i, prop in enumerate(user_selections):
        if prop.get("selection_id") == selection_id:
            removed_prop = user_selections.pop(i)
            
            # Save back to file
            with open(SELECTED_PROPERTIES_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            
            return {"status": "success", "message": f"Property '{removed_prop.get('name')}' removed from selections"}
    
    return {"status": "error", "message": "Property not found in selections"}

def get_selection_summary(user_id: str) -> Dict[str, Any]:
    """
    Get a summary of user's property selections for LLM context
    """
    selected_properties = load_selected_properties(user_id)
    
    if not selected_properties:
        return {
            "total_selected": 0, 
            "summary": "No properties selected yet",
            "recent_selections": [],
            "preferred_locations": [],
            "price_range": [],
            "bedroom_preferences": [],
            "selection_pattern": "User hasn't selected any properties yet"
        }
    
    # Analyze patterns
    price_range = []
    locations = []
    bedroom_counts = []
    
    for prop in selected_properties:
        if prop.get("price") and "₹" in prop["price"]:
            price_range.append(prop["price"])
        if prop.get("location"):
            locations.append(prop["location"])
        if prop.get("bedrooms"):
            bedroom_counts.append(prop["bedrooms"])
    
    # Create summary for LLM
    unique_locations = list(set(locations))
    summary = {
        "total_selected": len(selected_properties),
        "recent_selections": selected_properties[-3:],  # Last 3 for context
        "preferred_locations": unique_locations,
        "price_range": price_range,
        "bedroom_preferences": list(set(bedroom_counts)),
        "selection_pattern": f"User has selected {len(selected_properties)} properties" + 
                           (f", showing interest in {', '.join(unique_locations[:3])}" if unique_locations else "")
    }
    
    return summary