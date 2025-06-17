import re
import json
from typing import Optional, List, Dict
from modules.negotiation import NegotiationAssistant
from modules.legal_guidance import LegalGuide
from modules.mortgage_recommendation import MortgageRecommender
from modules.neighborhood_insights import NeighborhoodAnalyzer
from modules.marketing_description import MarketingContentGenerator
from modules.selected_properties_manager import get_selection_summary, load_selected_properties

import re

def normalize_price(price_str: str) -> float:
    if not price_str:
        return 0.0

    price_str = price_str.lower().replace("₹", "").replace(",", "").strip()

    # Extract numeric value and unit using regex
    match = re.match(r"(\d+\.?\d*)\s*(cr|crore|lakh|lakhs)?", price_str)
    if not match:
        print(f"[WARNING] Could not parse price: {price_str}")
        return 0.0

    value, unit = match.groups()
    value = float(value)

    if unit in ["cr", "crore"]:
        return value * 1_00_00_000
    elif unit in ["lakh", "lakhs"]:
        return value * 1_00_000
    else:
        return value  # No unit → treat as raw rupees


class HomeBuyingAgent:
    def __init__(self, llm_connector):
        self.llm_connector = llm_connector
        self.negotiation_assistant = NegotiationAssistant(llm_connector)
        self.legal_guide = LegalGuide(llm_connector)
        self.mortgage_recommender = MortgageRecommender(llm_connector)
        self.neighborhood_analyzer = NeighborhoodAnalyzer(llm_connector)
        self.marketing_generator = MarketingContentGenerator(llm_connector)

        self.property_searcher = None  # Will be injected externally
        self.selected_property = None

        self.user_chat_history = {} 

    async def _determine_intent(self, query: str, chat_history: Optional[List[Dict[str, str]]] = None, user_id: str = None) -> str:
        """Enhanced intent detection with memory context"""
        
        # Get user's selection context for better intent detection
        selection_context = ""
        if user_id:
            try:
                summary = get_selection_summary(user_id)
                if summary["total_selected"] > 0:
                    selection_context = f"""
                    User Context: This user has previously selected {summary['total_selected']} properties in locations: {', '.join(summary['preferred_locations'][:3])}.
                    Recent interest in: {summary['selection_pattern']}
                    """
            except Exception as e:
                print(f"Warning: Could not load user context: {e}")
        
        messages = []
        if chat_history:
            for msg in chat_history:
                messages.append({"role": msg["role"], "parts": [{"text": msg["text"]}]})

        messages.append({
            "role": "user",
            "parts": [{"text": f"""
            {selection_context}
            
            Analyze the following user query and identify the primary intent.
            Consider the user's previous selections when determining intent.
            
            Respond with one of these keywords:
            - SEARCH_PROPERTY
            - NEGOTIATE
            - LEGAL_GUIDANCE
            - MORTGAGE_RECOMMENDATION
            - NEIGHBORHOOD_INSIGHTS
            - MARKETING_DESCRIPTION
            - COMPARE_SELECTED (when user wants to compare their selected properties)
            - SELECTION_INSIGHTS (when user asks about their selections, patterns, or budget analysis)
            - BUDGET_ANALYSIS (when user asks to analyze budget based on selections)
            - UNKNOWN

            Query: \"{query}\"
            Intent:
            """}]
        })

        intent = await self.llm_connector.call_llm_api(messages=messages)
        return intent.strip().upper() if intent else "UNKNOWN"

    async def _get_enhanced_context(self, user_id: str = None) -> str:
        """Get user's selection history to enhance LLM responses"""
        if not user_id:
            return ""
        
        try:
            summary = get_selection_summary(user_id)
            if summary["total_selected"] == 0:
                return ""  # Return empty string instead of the message
            
            selected_properties = load_selected_properties(user_id)
            
            context = f"""
            USER'S PROPERTY SELECTION HISTORY:
            - Total Properties Selected: {summary['total_selected']}
            - Preferred Locations: {', '.join(summary['preferred_locations'])}
            - Price Range Interest: {', '.join(summary['price_range'][:3])}
            - Bedroom Preferences: {summary['bedroom_preferences']}
            
            RECENT SELECTIONS:
            """
            
            for prop in summary['recent_selections']:
                context += f"""
            • {prop.get('name', 'Unknown')} in {prop.get('location', 'Unknown')}
              Price: {prop.get('price', 'N/A')}, {prop.get('bedrooms', 'N/A')} BHK
              Selected on: {prop.get('selected_at', 'Unknown')[:10]}
              Status: {prop.get('status', 'interested')}
            """
            
            return context
        except Exception as e:
            print(f"Warning: Could not load user context: {e}")
            return ""

    async def process_query(
        self,
        query: str,
        user_id: str = None,
        property_details: Optional[dict] = None,
        target_negotiation_price: Optional[str] = None,
        income: Optional[float] = None,
        credit_score: Optional[int] = None,
        down_payment: Optional[float] = None,
        loan_amount: Optional[float] = None,
        property_type: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> dict:
        
        # ✅ 1. Handle reset/forget command immediately
        if "reset" in query.lower() or "forget" in query.lower():
            from modules.selected_properties_manager import clear_selected_properties
            clear_selected_properties(user_id)
            self.user_chat_history[user_id] = []
            return {
                "type": "info",
                "message": "✅ Your selected properties and conversation history have been reset."
            }

        intent = await self._determine_intent(query, chat_history, user_id)
        print(f"[DEBUG] Detected intent: {intent} from query: {query}")
        print(f"[DEBUG] User ID received: {user_id}")

        # Get user context for enhanced responses
        user_context = await self._get_enhanced_context(user_id)

        if property_details:
            self.selected_property = property_details

        try:
            if intent == "SEARCH_PROPERTY":
                if not self.property_searcher:
                    return {"type": "error", "message": "Property searcher not initialized."}
                
                # Enhanced search with user context (only if user has selections)
                if user_context and user_id:
                    try:
                        summary = get_selection_summary(user_id)
                        if summary.get("total_selected", 0) > 0:
                            pattern = summary.get("selection_pattern", "")
                            enhanced_query = f"{query} (User has shown interest in: {pattern})"
                            return await self.property_searcher.search_properties(enhanced_query)
                    except Exception as e:
                        print(f"[DEBUG] Could not enhance query with user context: {e}")
                
                return await self.property_searcher.search_properties(query)

            elif intent == "COMPARE_SELECTED":
                return await self._handle_property_comparison(user_id)

            elif intent == "SELECTION_INSIGHTS":
                return await self._handle_selection_insights(user_id, query)

            elif intent == "NEGOTIATE":
                property_data = property_details or self.selected_property

                query_lower = query.lower()
                general_keywords = ["tactic", "how", "strategy", "respond", "negotiate if", "advice", "reasonable offer", "try to bring", "10%", "room to negotiate"]
                is_general_advice = any(kw in query_lower for kw in general_keywords)

                if not property_data or not target_negotiation_price or is_general_advice:
                    result = await self.negotiation_assistant.get_general_negotiation_advice(query)
                    self._append_history(user_id, "assistant", result)
                    return {"type": "negotiation_tips", "data": result}

                if user_id not in self.user_chat_history:
                    self.user_chat_history[user_id] = []
                self.user_chat_history[user_id].extend(chat_history or [])
                self._append_history(user_id, "user", query)  # 👈 Add user message to history

                result = await self.negotiation_assistant.simulate_negotiation(
                    property_details=property_data,
                    target_price=target_negotiation_price,
                    chat_history=self.user_chat_history[user_id],
                    buyer_context=user_context
                )

                if result:
                    self._append_history(user_id, "assistant", result)
                    return {"type": "negotiation_result", "data": result}
                else:
                    return {
                        "type": "error",
                        "message": f"Could not simulate negotiation for ₹{target_negotiation_price}."
                    }

            elif intent == "LEGAL_GUIDANCE":
                property_data = property_details or self.selected_property
                if property_data:
                    property_type = property_data.get("property_type", "residential flat")
                    location = property_data.get("location", "")
                    city = location.split(",")[-1].strip() if "," in location else "your city"

                    # Enhanced legal guidance with context
                    if user_context:
                        enhanced_prompt = f"""
                        User's Property Selection Context:
                        {user_context}
                        
                        Provide legal guidance for {property_type} in {city}, considering their selection pattern and experience level.
                        """
                        result = await self.legal_guide.get_legal_guidance(property_type, city)
                    else:
                        result = await self.legal_guide.get_legal_guidance(property_type, city)
                    
                    return {"type": "legal_guidance", "data": result}
                else:
                    return {"type": "error", "message": "Legal guidance requires property details."}

            elif intent == "MORTGAGE_RECOMMENDATION":
                property_data = property_details or self.selected_property
                if property_data:
                    mortgage_info = {
                        "income": income or 1200000,
                        "credit_score": credit_score or 750,
                        "down_payment": down_payment or 2000000,
                        "loan_amount": loan_amount or 8000000,
                        "property_type": property_type or property_data.get("property_type", "apartment")
                    }

                    if user_context and user_id:
                        try:
                            summary = get_selection_summary(user_id)
                            if summary.get("price_range") and summary["total_selected"] > 0:
                                context_note = f"User has shown interest in properties priced: {', '.join(summary['price_range'][:3])}"
                                print(f"[DEBUG] Adding price context: {context_note}")
                        except Exception as e:
                            print(f"[DEBUG] Could not add price context: {e}")

                    result = await self.mortgage_recommender.get_mortgage_recommendations(
                        mortgage_info["income"],
                        mortgage_info["credit_score"],
                        mortgage_info["down_payment"],
                        mortgage_info["loan_amount"],
                        mortgage_info["property_type"],
                        self.user_chat_history.get(user_id, [])
                    )

                    if result:
                        self._append_history(user_id, "assistant", result)

                    return {"type": "mortgage_recommendation", "data": result}
                else:
                    return {"type": "error", "message": "Mortgage recommendation requires property context."}


            elif intent == "NEIGHBORHOOD_INSIGHTS":
                property_data = property_details or self.selected_property
                if property_data:
                    location = property_data.get("location", "N/A")
                    city_parts = location.split(",")
                    city = city_parts[-1].strip() if len(city_parts) > 1 else "your city"

                    result = await self.neighborhood_analyzer.get_neighborhood_insights(location, city)
                    return {"type": "neighborhood_insights", "data": result}
                else:
                    return {"type": "error", "message": "Neighborhood insights require property context."}

            elif intent == "BUDGET_ANALYSIS":
                return await self._handle_selection_insights(user_id, query)

            elif intent == "MARKETING_DESCRIPTION":
                property_data = property_details or self.selected_property
                if property_data:
                    result = await self.marketing_generator.generate_marketing_description(property_data)
                    return {"type": "marketing_description", "data": result}
                else:
                    return {"type": "error", "message": "Marketing description requires property context."}

            else:
                # Handle unknown intents - check if it's selection-related
                query_lower = query.lower()
                if any(keyword in query_lower for keyword in ['selected', 'selection', 'budget', 'analyze', 'compare', 'pattern']):
                    if 'compare' in query_lower:
                        return await self._handle_property_comparison(user_id)
                    else:
                        return await self._handle_selection_insights(user_id, query)
                else:
                    return {"type": "error", "message": "I didn't understand that request. Could you please rephrase?"}

        except Exception as e:
            print(f"[ERROR] Exception in process_query: {e}")
            return {"type": "error", "message": str(e)}

    async def _handle_property_comparison(self, user_id: str) -> dict:
        """Handle property comparison requests"""
        print(f"[DEBUG] _handle_property_comparison called with user_id: {user_id}")
        
        if not user_id:
            return {"type": "error", "message": "User ID required for property comparison."}
        
        try:
            selected_properties = load_selected_properties(user_id)
            
            if len(selected_properties) < 2:
                return {
                    "type": "comparison_result", 
                    "data": "You need at least 2 selected properties to compare. Select more properties to get detailed comparisons."
                }
            
            # Create comparison using LLM
            comparison_prompt = f"""
            Compare these {len(selected_properties)} properties selected by the user:
            
            PROPERTIES TO COMPARE:
            """
            
            for i, prop in enumerate(selected_properties[:5], 1):  # Limit to 5 for readability
                comparison_prompt += f"""
            
            Property {i}: {prop.get('name', 'Unknown')}
            • Location: {prop.get('location', 'N/A')}
            • Price: {prop.get('price', 'N/A')}
            • Size: {prop.get('bedrooms', 'N/A')} BHK, {prop.get('areaSqFt', 'N/A')} sq ft
            • Selected: {prop.get('selected_at', 'Unknown')[:10]}
            • Status: {prop.get('status', 'interested')}
            """
            
            comparison_prompt += """
            
            Provide a detailed comparison covering:
            1. Price comparison and value analysis
            2. Location advantages/disadvantages
            3. Property features comparison
            4. Investment potential
            5. Recommendation on which property(ies) to prioritize
            
            Format as clear sections with actionable insights.
            """
            
            comparison_result = await self.llm_connector.call_llm_api(comparison_prompt)
            
            return {"type": "comparison_result", "data": comparison_result}
            
        except Exception as e:
            return {"type": "error", "message": f"Error comparing properties: {e}"}

    async def _handle_selection_insights(self, user_id: str, query: str) -> dict:
        """Handle requests for insights about user's selections"""
        print(f"[DEBUG] _handle_selection_insights called with user_id: {user_id}")
        
        if not user_id:
            return {"type": "error", "message": "User ID required for selection insights."}
        
        try:
            summary = get_selection_summary(user_id)
            
            if summary["total_selected"] == 0:
                return {
                    "type": "selection_insights",
                    "data": "You haven't selected any properties yet. Start exploring properties to get personalized insights about your preferences!"
                }
            
            insights_prompt = f"""
            User Query: "{query}"
            
            Analyze the user's property selection pattern and respond to their query:
            
            SELECTION SUMMARY:
            {summary}
            
            USER CONTEXT:
            {await self._get_enhanced_context(user_id)}
            
            Provide insights addressing their specific question, including:
            1. Pattern analysis of their selections
            2. Budget and location preferences
            3. Recommendations for next steps
            4. Any specific advice related to their query
            
            Be conversational and helpful.
            """
            
            insights = await self.llm_connector.call_llm_api(insights_prompt)
            
            return {"type": "selection_insights", "data": insights}
            
        except Exception as e:
            return {"type": "error", "message": f"Error generating insights: {e}"}

    def extract_price_from_text(self, text: str) -> Optional[str]:
        match = re.search(r"(\d+\.?\d*)\s*(lakh|lakhs|crore|cr)", text.lower())
        if match:
            value, unit = match.groups()
            unit_symbol = "Lakh" if "lakh" in unit else "Crore"
            return f"₹{value} {unit_symbol}"
        return None
    
    def _append_history(self, user_id: str, role: str, text: str):
        if not hasattr(self, "user_chat_history"):
            self.user_chat_history = {}

        if user_id not in self.user_chat_history:
            self.user_chat_history[user_id] = []

        self.user_chat_history[user_id].append({
            "role": role,
            "text": text
        })
