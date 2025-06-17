from utils.llm_connector import LLMConnector

class NeighborhoodAnalyzer:
    """
    Provides lifestyle, safety, investment, and amenity insights for a neighborhood using LLM and external chat history.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    def _format_history(self, chat_history: list[dict]) -> str:
        """
        Formats the external chat history passed from the main agent.
        """
        return "\n".join([f"{msg['role'].capitalize()}: {msg['text']}" for msg in chat_history or []])

    async def get_neighborhood_insights(
        self,
        location: str,
        city: str = "your city",
        chat_history: list[dict] = None
    ) -> str:
        """
        Generates descriptive insights about a neighborhood's lifestyle, safety, connectivity, and real estate value.
        """
        user_message = f"""
Provide neighborhood insights for {location}, {city}, India.
"""

        prompt_template = """
You are a real estate neighborhood analyst in India.

Guidelines:
- Share useful, updated insights about the locality.
- Include info on connectivity, amenities, lifestyle, safety, and real estate trends.
- Be conversational and helpful — tone should be warm and trustworthy.
- Wrap up with a summary on whether this is a good area for families or investment.

Neighborhood Insight Request:
{input}

Chat Context:
{chat_history}
"""

        formatted_history = self._format_history(chat_history or [])
        prompt = prompt_template.format(chat_history=formatted_history, input=user_message)

        result = await self.llm_connector.call_llm_api(prompt=prompt)
        return result or f"Could not retrieve insights for {location}, {city} at this time."
