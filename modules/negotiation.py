from utils.llm_connector import LLMConnector

class NegotiationAssistant:
    """
    Simulates negotiation outcomes using an LLM.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    async def simulate_negotiation(self, property_details: dict, target_price: str) -> str:
        """
        Simulates a negotiation scenario for a given property and target price.
        """
        prompt = f"""Simulate a negotiation outcome for a property named '{property_details.get('name', 'N/A')}'
        located in '{property_details.get('location', 'N/A')}' with an asking price of '{property_details.get('price', 'N/A')}'.
        The buyer is offering '{target_price}'.
        Provide a realistic scenario in a few sentences, considering the seller's perspective and potential counter-offers.
        Focus on a concise, realistic outcome.
        """
        result = await self.llm_connector.call_llm_api(prompt)
        return result if result else "Could not simulate negotiation at this time."

