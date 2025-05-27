from modules.property_search import PropertySearch
from modules.negotiation import NegotiationAssistant
from modules.legal_guidance import LegalGuide
from modules.mortgage_recommendation import MortgageRecommender
from modules.neighborhood_insights import NeighborhoodAnalyzer
from modules.marketing_description import MarketingContentGenerator
from utils.llm_connector import LLMConnector
from typing import Optional, Dict, Any # Import necessary types

class HomeBuyingAgent:
    """
    The central agent that understands buyer intent and orchestrates
    various modules to fulfill requests.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.property_search = PropertySearch(llm_connector)
        self.negotiation_assistant = NegotiationAssistant(llm_connector)
        self.legal_guide = LegalGuide(llm_connector)
        self.mortgage_recommender = MortgageRecommender(llm_connector)
        self.neighborhood_analyzer = NeighborhoodAnalyzer(llm_connector)
        self.marketing_generator = MarketingContentGenerator(llm_connector)
        self.llm_connector = llm_connector # For intent recognition

    async def _determine_intent(self, query: str) -> str:
        """
        Uses LLM to determine the user's primary intent from a natural language query.
        This method is only called if the query is NOT a direct intent keyword.
        """
        prompt = f"""Analyze the following user query and identify the primary intent.
        Respond with one of these keywords:
        - SEARCH_PROPERTY
        - NEGOTIATE
        - LEGAL_GUIDANCE
        - MORTGAGE_RECOMMENDATION
        - NEIGHBORHOOD_INSIGHTS
        - MARKETING_DESCRIPTION
        - UNKNOWN

        Query: "{query}"
        Intent:"""
        intent = await self.llm_connector.call_llm_api(prompt)
        return intent.strip().upper() if intent else "UNKNOWN"

    async def process_request(self, 
                              user_id: str, 
                              query: str, 
                              property_details: Optional[Dict] = None, 
                              target_price: Optional[str] = None, 
                              **kwargs: Any) -> Dict: # Added **kwargs to capture additional parameters
        """
        Processes a user request by determining intent and calling the appropriate module.
        Prioritizes direct intent keywords sent from the frontend.

        Args:
            user_id (str): The ID of the user making the request.
            query (str): The user's natural language query or a direct intent keyword.
            property_details (dict, optional): Details of a selected property, if relevant to the query.
            target_price (str, optional): Target price for negotiation, if relevant.
            **kwargs: Additional parameters (e.g., income, credit_score for mortgage, passed from frontend).

        Returns:
            dict: A dictionary containing the type of response and the data.
        """
        # --- Direct Intent Keyword Check (Priority 1) ---
        # Normalize the query for robust matching
        normalized_query = query.strip().upper()

        if normalized_query == "SEARCH_PROPERTY":
            intent = "SEARCH_PROPERTY"
        elif normalized_query == "NEGOTIATE":
            intent = "NEGOTIATE"
        elif normalized_query == "LEGAL_GUIDANCE":
            intent = "LEGAL_GUIDANCE"
        elif normalized_query == "MORTGAGE_RECOMMENDATION":
            intent = "MORTGAGE_RECOMMENDATION"
        elif normalized_query == "NEIGHBORHOOD_INSIGHTS":
            intent = "NEIGHBORHOOD_INSIGHTS"
        elif normalized_query == "MARKETING_DESCRIPTION":
            intent = "MARKETING_DESCRIPTION"
        else:
            # --- Fallback to LLM for Natural Language Intent Recognition ---
            # Pass original query to LLM, as it expects natural language
            intent = await self._determine_intent(query) 

        print(f"User intent detected: {intent} for query: '{query}'")

        if intent == "SEARCH_PROPERTY":
            return await self.property_search.search_properties(query)
        elif intent == "NEGOTIATE": # Parameters are checked in the direct match or in the module
            if property_details and target_price:
                result = await self.negotiation_assistant.simulate_negotiation(property_details, target_price)
                return {"type": "negotiation_result", "data": result}
            else:
                return {"type": "error", "message": "Negotiation requires property details and target price."}
        elif intent == "LEGAL_GUIDANCE":
            result = await self.legal_guide.get_legal_guidance()
            return {"type": "legal_guidance", "data": result}
        elif intent == "MORTGAGE_RECOMMENDATION":
            # Extract parameters from kwargs as sent by frontend
            income = kwargs.get('income')
            credit_score = kwargs.get('credit_score')
            down_payment = kwargs.get('down_payment')
            loan_amount = kwargs.get('loan_amount')
            property_type_arg = kwargs.get('property_type') # Renamed to avoid conflict with function param if any

            if all(p is not None for p in [income, credit_score, down_payment, loan_amount, property_type_arg]):
                result = await self.mortgage_recommender.get_mortgage_recommendations(
                    income=float(income), # Ensure type conversion as values might come as Any
                    credit_score=int(credit_score),
                    down_payment=float(down_payment),
                    loan_amount=float(loan_amount),
                    property_type=str(property_type_arg)
                )
                return {"type": "mortgage_recommendation", "data": result}
            else:
                print(f"Warning: Missing parameters for MORTGAGE_RECOMMENDATION. Received: {kwargs}")
                return {"type": "error", "message": "Missing financial details for mortgage recommendation."}
        elif intent == "NEIGHBORHOOD_INSIGHTS":
            if property_details and property_details.get('location'):
                result = await self.neighborhood_analyzer.get_neighborhood_insights(property_details['location'])
                return {"type": "neighborhood_insights", "data": result}
            else:
                return {"type": "error", "message": "Neighborhood insights require property location details."}
        elif intent == "MARKETING_DESCRIPTION":
            if property_details:
                result = await self.marketing_generator.generate_marketing_description(property_details)
                return {"type": "marketing_description", "data": result}
            else:
                return {"type": "error", "message": "Marketing description requires property details."}
        else:
            # Default to property search if intent is UNKNOWN or parameters are missing for specific intents
            print(f"Intent '{intent}' not fully matched or parameters missing. Defaulting to property search.")
            return await self.property_search.search_properties(query)

