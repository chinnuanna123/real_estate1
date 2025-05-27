from utils.llm_connector import LLMConnector

class NeighborhoodAnalyzer:
    """
    Provides insights into a given neighborhood using an LLM.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    async def get_neighborhood_insights(self, location: str) -> str:
        """
        Generates a detailed overview of a specified neighborhood.
        """
        prompt = f"""Provide a detailed overview of the neighborhood '{location}' in India.
        Include information on key amenities (schools, hospitals, shopping malls, parks),
        lifestyle (e.g., quiet residential, bustling commercial, family-friendly),
        safety aspects, and potential for property value appreciation or rental yield.
        Format it as a comprehensive, well-structured paragraph or a few bullet points.
        """
        result = await self.llm_connector.call_llm_api(prompt)
        return result if result else f"Could not retrieve insights for {location} at this time."

