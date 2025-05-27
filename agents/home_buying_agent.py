from modules.property_search import PropertySearch
from modules.negotiation import NegotiationAssistant
from modules.legal_guidance import LegalGuide
from modules.mortgage_recommendation import MortgageRecommender
from modules.neighborhood_insights import NeighborhoodAnalyzer
from modules.marketing_description import MarketingContentGenerator
from utils.llm_connector import LLMConnector
from typing import Optional, Dict, Any, List # Import List for chat_history

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

    async def _determine_intent(self, query: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Uses LLM to determine the user's primary intent from a natural language query
        in the context of chat history.
        """
        # Prepare messages for LLM API call, including chat history
        messages = []
        if chat_history:
            for msg in chat_history:
                # Assuming chat_history is in {'role': 'user'/'agent', 'text': '...'} format
                messages.append({"role": msg["role"], "parts": [{"text": msg["text"]}]})
        
        # Add the current query for intent detection
        messages.append({"role": "user", "parts": [{"text": f"""Analyze the following user query and identify the primary intent.
        Respond with one of these keywords:
        - SEARCH_PROPERTY
        - NEGOTIATE
        - LEGAL_GUIDANCE
        - MORTGAGE_RECOMMENDATION
        - NEIGHBORHOOD_INSIGHTS
        - MARKETING_DESCRIPTION
        - UNKNOWN

        Query: "{query}"
        Intent:"""}]})

        # Pass the full messages list to the LLM connector
        # Assuming llm_connector.call_llm_api is updated to accept 'messages'
        intent = await self.llm_connector.call_llm_api(messages=messages) 
        return intent.strip().upper() if intent else "UNKNOWN"

    async def process_request(self, 
                              user_id: str, 
                              query: str, 
                              property_details: Optional[Dict] = None, 
                              target_price: Optional[str] = None, 
                              chat_history: Optional[List[Dict[str, str]]] = None, # Added chat_history to signature
                              **kwargs: Any) -> Dict:
        """
        Processes a user request by determining intent and calling the appropriate module.
        Prioritizes direct intent keywords sent from the frontend.

        Args:
            user_id (str): The ID of the user making the request.
            query (str): The user's natural language query or a direct intent keyword.
            property_details (dict, optional): Details of a selected property, if relevant to the query.
            target_price (str, optional): Target price for negotiation, if relevant.
            chat_history (list, optional): List of previous chat messages for conversational context.
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
            # Pass original query AND chat_history to _determine_intent for conversational context
            intent = await self._determine_intent(query, chat_history) 

        print(f"User intent detected: {intent} for query: '{query}'") # This log will confirm the intent

        if intent == "SEARCH_PROPERTY":
            return await self.property_search.search_properties(query)
        elif intent == "NEGOTIATE":
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
            property_type_arg = kwargs.get('property_type') 

            if all(p is not None for p in [income, credit_score, down_payment, loan_amount, property_type_arg]):
                result = await self.mortgage_recommender.get_mortgage_recommendations(
                    income=float(income), 
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
