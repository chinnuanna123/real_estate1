from utils.llm_connector import LLMConnector

class MarketingContentGenerator:
    """
    Generates emotionally persuasive, SEO-optimized property marketing descriptions using LLM with injected chat history.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    def _format_history(self, chat_history: list[dict]) -> str:
        """
        Formats the external chat history passed from the main agent.
        """
        return "\n".join([f"{msg['role'].capitalize()}: {msg['text']}" for msg in chat_history or []])

    async def generate_marketing_description(self, property_details: dict, chat_history: list[dict]) -> str:
        """
        Generates persuasive marketing content with context from chat history.
        """
        user_message = f"""
Create a marketing description for the following property:

• Title: {property_details.get('name', 'N/A')}
• Location: {property_details.get('location', 'N/A')}
• Asking Price: {property_details.get('price', 'N/A')}
• Size: {property_details.get('areaSqFt', 'N/A')} sq. ft
• Bedrooms: {property_details.get('bedrooms', 'N/A')}
• Bathrooms: {property_details.get('bathrooms', 'N/A')}
• Original Description: {property_details.get('description', 'N/A')}
"""

        prompt_template = """
You are a skilled real estate copywriter in India. Write a compelling, emotionally engaging marketing description for a top-tier property listing (e.g., 99acres or Magicbricks).

Instructions:
- Begin with an eye-catching headline.
- Describe layout and ambience (e.g., light, ventilation, vibe).
- Highlight standout features: balcony, modular kitchen, Vaastu compliance, nearby schools or tech parks, etc.
- Recommend ideal buyers (professionals, families, retirees).
- End with a soft call to action like "Book your visit today".
- Write in paragraph format (100–150 words), warm and aspirational tone.

Chat Context:
{chat_history}

Input:
{input}
"""

        formatted_history = self._format_history(chat_history)
        prompt = prompt_template.format(chat_history=formatted_history, input=user_message)

        result = await self.llm_connector.call_llm_api(prompt=prompt)
        return result or "Could not generate marketing description at this time."
