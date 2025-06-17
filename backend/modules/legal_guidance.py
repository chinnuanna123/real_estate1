from utils.llm_connector import LLMConnector

class LegalGuide:
    """
    Provides guidance on legal and paperwork steps in Indian real estate transactions using LLM and injected chat history.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    def _format_history(self, chat_history: list[dict]) -> str:
        """
        Formats the external chat history passed from the main agent.
        """
        return "\n".join([
            f"{msg.get('role', 'User').capitalize()}: {msg.get('text', '')}"
            for msg in chat_history or []
        ])

    async def get_legal_guidance(
        self,
        query: str = "",
        property_type: str = "residential flat",
        city: str = "your city",
        chat_history: list[dict] = None
    ) -> str:
        """
        Handles different types of legal queries based on user input.

        Args:
            query (str): Raw user query or intent.
            property_type (str): Type of property.
            city (str): City for contextual response.
            chat_history (list[dict], optional): Chat context.

        Returns:
            str: LLM-generated legal guidance response.
        """
        formatted_history = self._format_history(chat_history or [])
        query_lower = query.lower()

        # Intent detection based on keywords
        if "stamp duty" in query_lower or "registration fee" in query_lower:
            user_message = f"Calculate the stamp duty and registration fee for a property worth ₹90 lakhs in {city}."
        elif "agreement to sell" in query_lower:
            user_message = "Draft a sample 'Agreement to Sell' for an apartment transaction in India."
        elif "encumbrance" in query_lower or "legal dispute" in query_lower:
            user_message = "Guide me on how to check if a property has legal disputes or encumbrances in India."
        elif "email" in query_lower and "seller" in query_lower:
            user_message = "Draft a professional email to the seller requesting all legal documents related to a property purchase."
        else:
            user_message = f"Provide legal guidance for buying a {property_type} in {city}."

        prompt_template = """
You are a real estate legal advisor in India.

Instructions:
- Clearly respond to the user's legal query about real estate (buying, due diligence, documentation, etc.).
- If asked to draft a sample agreement or email, generate a clear and helpful sample.
- If asked to calculate stamp duty, explain the typical percentage and give an estimate.
- If asked about disputes or encumbrances, explain how to verify them using official portals or legal support.
- Use simple and professional tone suitable for first-time buyers.

Chat Context:
{chat_history}

User Query:
{input}
"""

        prompt = prompt_template.format(chat_history=formatted_history, input=user_message)
        result = await self.llm_connector.call_llm_api(prompt=prompt)
        return result or "⚠️ Could not retrieve legal guidance at this time."
