# routes/home_buying_routes.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import traceback
import os
import json

# Import LLM-enhanced modules
from agents.home_buying_agent import HomeBuyingAgent
from modules.preference_manager import load_preferences, save_preferences
from modules.property_search import PropertySearch
from modules.selected_properties_manager import (
    save_selected_property,
    load_selected_properties,
    update_property_status,
    remove_selected_property,
    get_selection_summary
)
from tools.google_search import (
    search_properties,
    PerQueryResult,
    _extract_fields_from_snippet,
    format_property_description,
)
from utils.llm_connector import LLMConnector

router = APIRouter()

# Pydantic models
class SearchRequest(BaseModel):
    query: str

class PropertyResponse(BaseModel):
    title: Optional[str]
    url: Optional[str]
    location: Optional[str]
    price: Optional[str]
    area_sqft: Optional[int]
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    property_type: Optional[str]
    formatted_description: Optional[str]

class SearchResponse(BaseModel):
    properties: List[PropertyResponse]

class ProcessQueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    property_details: Optional[Dict] = None
    target_negotiation_price: Optional[str] = None
    income: Optional[float] = None
    credit_score: Optional[int] = None
    down_payment: Optional[float] = None
    loan_amount: Optional[float] = None
    property_type: Optional[str] = None
    chat_history: Optional[List[Dict[str, str]]] = None

class PreferenceRequest(BaseModel):
    user_id: str
    preferences: Dict

class SelectPropertyRequest(BaseModel):
    user_id: str
    property_data: Dict[str, Any]

class UpdatePropertyStatusRequest(BaseModel):
    user_id: str
    selection_id: str
    status: str
    notes: Optional[str] = ""

class RemovePropertyRequest(BaseModel):
    user_id: str
    selection_id: str

# Initialize AI components
llm_connector = LLMConnector(api_key=os.getenv("OPENAI_API_KEY", ""), llm_provider="openai")
home_buying_agent = HomeBuyingAgent(llm_connector)
home_buying_agent.property_searcher = PropertySearch(llm_connector)

# Search endpoint
@router.post("/search", response_model=SearchResponse)
async def search_endpoint(request: SearchRequest):
    query_text = request.query.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Query must not be empty")

    try:
        results = search_properties([query_text])
        all_properties = []
        for sr in results:
            if not sr.results:
                continue
            for p in sr.results:
                if not getattr(p, "formatted_description", None):
                    raw_desc = p.raw_snippet or ""
                    loc = p.location or "Unknown"
                    fields = _extract_fields_from_snippet(raw_desc, loc)
                    p.formatted_description = format_property_description(fields)

                all_properties.append(PropertyResponse(
                    title=p.title,
                    url=p.url,
                    location=p.location,
                    price=p.price,
                    area_sqft=p.area_sqft,
                    bedrooms=p.bedrooms,
                    bathrooms=p.bathrooms,
                    property_type=p.property_type,
                    formatted_description=p.formatted_description,
                ))
        return SearchResponse(properties=all_properties)

    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Sorry, something went wrong processing your request.")

# AI agent processing
@router.post("/process_query")
async def process_user_query(request: ProcessQueryRequest):
    try:
        request_data = request.dict(exclude_unset=True)
        query = request_data.pop('query')
        property_details = request_data.pop('property_details', None)
        target_negotiation_price = request_data.pop('target_negotiation_price', None)
        chat_history = request_data.pop('chat_history', None)
        user_id = request_data.get('user_id')

        response_data = await home_buying_agent.process_query(
            query=query,
            user_id=user_id,
            property_details=property_details,
            target_negotiation_price=target_negotiation_price,
            chat_history=chat_history,
            **{k: v for k, v in request_data.items() if k != 'user_id'}
        )

        if isinstance(response_data, dict):
            result_type = response_data.get("type", "unknown")
            return {
                "status": "success",
                "data": {
                    "type": result_type,
                    "data": response_data.get("data", "No additional info.")
                }
            }
        return {"response": str(response_data)}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing query: {e}")

# Preferences
@router.post("/save_preferences")
async def save_user_preferences(request: PreferenceRequest):
    try:
        save_preferences(request.user_id, request.preferences)
        return {"status": "success", "message": "Preferences saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving preferences: {e}")

@router.get("/load_preferences/{user_id}")
async def load_user_preferences(user_id: str):
    try:
        prefs = load_preferences(user_id)
        return {"status": "success", "data": prefs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading preferences: {e}")

# Visit and Paperwork (mocked)
@router.post("/book_visit")
async def book_visit_endpoint(property_details: Dict):
    return {"status": "success", "message": f"Visit for {property_details.get('name')} booked."}

@router.post("/handle_paperwork")
async def handle_paperwork_endpoint(property_details: Dict):
    return {"status": "success", "message": f"Paperwork for {property_details.get('name')} processed."}

# Property selection endpoints
@router.post("/select_property")
async def select_property_endpoint(request: SelectPropertyRequest):
    try:
        result = save_selected_property(request.user_id, request.property_data)
        return {
            "status": "success",
            "message": result.get("message", "Property selected successfully"),
            "data": {
                "property_name": request.property_data.get('name', 'Unknown'),
                "selection_saved": True
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error selecting property: {e}")

@router.get("/selected_properties/{user_id}")
async def get_selected_properties(user_id: str):
    try:
        selected_properties = load_selected_properties(user_id)
        summary = get_selection_summary(user_id)
        return {"status": "success", "data": {"selected_properties": selected_properties, "summary": summary}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading properties: {e}")

@router.post("/update_property_status")
async def update_property_status_endpoint(request: UpdatePropertyStatusRequest):
    try:
        result = update_property_status(request.user_id, request.selection_id, request.status, request.notes)
        return {"status": "success" if result["status"] == "success" else "error", "message": result["message"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating status: {e}")

@router.post("/remove_selected_property")
async def remove_selected_property_endpoint(request: RemovePropertyRequest):
    try:
        result = remove_selected_property(request.user_id, request.selection_id)
        return {"status": "success" if result["status"] == "success" else "error", "message": result["message"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing property: {e}")

@router.get("/selection_insights/{user_id}")
async def get_selection_insights(user_id: str):
    try:
        summary = get_selection_summary(user_id)
        if summary["total_selected"] == 0:
            return {
                "status": "success",
                "data": {
                    "insights": "No properties selected yet. Start exploring to get personalized insights!",
                    "recommendations": []
                }
            }

        insights_prompt = f"""
        Analyze this user's property selection pattern and provide insights:

        Selection Summary:
        - Total Properties Selected: {summary['total_selected']}
        - Preferred Locations: {summary['preferred_locations']}
        - Price Range: {summary['price_range']}
        - Bedroom Preferences: {summary['bedroom_preferences']}

        Recent Selections:
        {json.dumps(summary['recent_selections'], indent=2)}

        Provide:
        1. Pattern analysis (what type of properties they prefer)
        2. Budget analysis 
        3. Location preferences
        4. 3 specific recommendations for their next search

        Keep it concise and actionable.
        """
        insights = await llm_connector.call_llm_api(insights_prompt)
        return {"status": "success", "data": {"insights": insights, "summary": summary}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating insights: {e}")
