from utils.llm_connector import LLMConnector

class MarketingContentGenerator:
    """
    Generates marketing descriptions for properties using an LLM.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    async def generate_marketing_description(self, property_details: dict) -> str:
        """
        Creates a compelling marketing description for a given property.
        """
        prompt = f"""Write a compelling real estate marketing description for the following property:
        Name: {property_details.get('name', 'N/A')}
        Location: {property_details.get('location', 'N/A')}
        Price: {property_details.get('price', 'N/A')}
        Bedrooms: {property_details.get('bedrooms', 'N/A')}
        Bathrooms: {property_details.get('bathrooms', 'N/A')}
        Area: {property_details.get('areaSqFt', 'N/A')} SqFt
        Original Description: {property_details.get('description', 'N/A')}

        Highlight its unique selling points and appeal to potential buyers looking for a great investment or a dream home.
        Make it engaging and persuasive, suitable for a property listing.
        """
        result = await self.llm_connector.call_llm_api(prompt)
        return result if result else "Could not generate marketing description at this time."
