from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any # Import Any for **kwargs

from agents.home_buying_agent import HomeBuyingAgent
from modules.preference_manager import load_preferences, save_preferences
from utils.llm_connector import LLMConnector
import os # Ensure os is imported

# Initialize LLMConnector globally or pass it around
# --- THIS LINE IS CRITICAL - CHANGED TO USE OPENAI_API_KEY AND llm_provider="openai" ---
llm_connector = LLMConnector(api_key=os.getenv("OPENAI_API_KEY", ""), llm_provider="openai") 

home_buying_agent: HomeBuyingAgent = HomeBuyingAgent(llm_connector) 

router = APIRouter()

class ProcessQueryRequest(BaseModel):
    user_id: str
    query: str
    property_details: Optional[Dict] = None
    target_negotiation_price: Optional[str] = None
    # Add new financial parameters to the request model
    income: Optional[float] = None
    credit_score: Optional[int] = None
    down_payment: Optional[float] = None
    loan_amount: Optional[float] = None
    property_type: Optional[str] = None
    chat_history: Optional[List[Dict[str, str]]] = None # Ensure this is present for chatbot

class PreferenceRequest(BaseModel):
    user_id: str
    preferences: Dict

@router.post("/process_query")
async def process_user_query(request: ProcessQueryRequest):
    """
    Processes a user's query using the HomeBuyingAgent.
    This is the main entry point for user interactions.
    """
    try:
        # Get all request data as a mutable dictionary
        request_data = request.dict(exclude_unset=True)

        # Extract parameters that are explicitly defined in process_request's signature
        # Use .pop() to remove them from request_data, so they are not passed via **request_data
        user_id = request_data.pop('user_id')
        query = request_data.pop('query')
        property_details = request_data.pop('property_details', None) # Use .pop with default to handle Optional fields
        target_price = request_data.pop('target_negotiation_price', None) # Use .pop with default
        chat_history = request_data.pop('chat_history', None) # Ensure chat_history is popped

        # Pass the extracted explicit parameters, and then unpack the remaining kwargs
        response_data = await home_buying_agent.process_request(
            user_id=user_id,
            query=query,
            property_details=property_details,
            target_price=target_price,
            chat_history=chat_history, # Pass chat_history explicitly
            **request_data # Pass remaining fields (income, credit_score, etc.) as kwargs
        )
        return {"status": "success", "data": response_data}
    except Exception as e:
        # Log the full exception for debugging
        print(f"Error in process_user_query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {e}")

@router.post("/save_preferences")
async def save_user_preferences(request: PreferenceRequest):
    """
    Saves user preferences (including last search results) to storage.
    """
    try:
        save_preferences(request.user_id, request.preferences)
        return {"status": "success", "message": "Preferences saved successfully."}
    except Exception as e:
        print(f"Error in save_user_preferences: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving preferences: {e}")

@router.get("/load_preferences/{user_id}")
async def load_user_preferences(user_id: str):
    """
    Loads user preferences from storage.
    """
    try:
        prefs = load_preferences(user_id)
        return {"status": "success", "data": prefs}
    except Exception as e:
        print(f"Error in load_user_preferences: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading preferences: {e}")

# Additional simulated endpoints for direct actions if needed by frontend
@router.post("/book_visit")
async def book_visit_endpoint(property_details: Dict):
    """Simulates booking a visit."""
    print(f"Simulating visit booking for: {property_details.get('name')}")
    return {"status": "success", "message": f"Visit for {property_details.get('name')} simulated as booked."}

@router.post("/handle_paperwork")
async def handle_paperwork_endpoint(property_details: Dict):
    """Simulates handling paperwork."""
    print(f"Simulating paperwork for: {property_details.get('name')}")
    return {"status": "success", "message": f"Paperwork for {property_details.get('name')} simulated as handled."}
