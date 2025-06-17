from utils.llm_connector import LLMConnector
import re

class NegotiationAssistant:
    """
    Handles real estate negotiation simulations and seller counteroffer predictions using LLM.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    def _format_history(self, chat_history: list[dict]) -> str:
        """
        Formats the external chat history passed from the main agent.
        """
        return "\n".join([f"{msg['role'].capitalize()}: {msg['text']}" for msg in chat_history or []])

    def _extract_last_offer(self, chat_history: list[dict]) -> str:
        """
        Extracts the last offer made by the user from chat history.
        """
        pattern = re.compile(r"\b(?:₹)?(\d+[\d.,]*)(\s*crore|\s*lakh|\s*cr|\s*lakhs)?", re.IGNORECASE)
        offers = []
        for msg in chat_history:
            if msg['role'] == 'user':
                matches = pattern.findall(msg['text'])
                for value, unit in matches:
                    value = float(value.replace(',', ''))
                    if unit.strip().lower() in ['cr', 'crore']:
                        offers.append(value * 10000000)
                    elif unit.strip().lower() in ['lakh', 'lakhs']:
                        offers.append(value * 100000)
                    else:
                        offers.append(value)
        return offers[-1] if offers else None

    async def simulate_negotiation(
        self,
        property_details: dict,
        target_price: str,
        chat_history: list[dict],
        buyer_context: str = None
    ) -> str:
        """
        Simulates a negotiation scenario using provided chat history and buyer context.
        """
        formatted_history = self._format_history(chat_history)
        previous_offer = self._extract_last_offer(chat_history[:-1])

        user_message = f"""
Negotiate the following:
• Property: {property_details.get('name', 'N/A')} in {property_details.get('location', 'N/A')}
• Asking Price: ₹{property_details.get('price', 'N/A')}
• Area: {property_details.get('areaSqFt', 'N/A')} sq.ft
• Bedrooms: {property_details.get('bedrooms', 'N/A')}
• My Offer: ₹{target_price}
• Buyer Context: {buyer_context or "No additional context"}
• Previous Offer: ₹{int(previous_offer):,} (if any)
""" if previous_offer else f"""
Negotiate the following:
• Property: {property_details.get('name', 'N/A')} in {property_details.get('location', 'N/A')}
• Asking Price: ₹{property_details.get('price', 'N/A')}
• Area: {property_details.get('areaSqFt', 'N/A')} sq.ft
• Bedrooms: {property_details.get('bedrooms', 'N/A')}
• My Offer: ₹{target_price}
• Buyer Context: {buyer_context or "No additional context"}
"""

        prompt_template = """
You are a skilled real estate negotiation assistant for buyers in India.

Your goal is to help a buyer negotiate better with the seller. The buyer may have made previous offers in this conversation. Reference that context and respond accordingly.

Here is the chat history (most recent at the bottom):

{chat_history}

The buyer is continuing the negotiation and has now made a new offer.

Current Offer Context:
{input}

---

Instructions:
1. If the buyer has made a **previous offer**, refer to it directly in your response.
2. Compare the new offer with the earlier one and calculate the discount percentage.
3. Simulate seller response, suggest a reasonable counter-offer, and give clear tactics.
4. Maintain polite, professional tone.
5. If the user asks **how to close the deal**, provide **next steps** like:
  • Drafting a formal email
  • Requesting the seller’s agent contact
  • Preparing token amount/payment plan
6. Still provide offer, tactics, walk-away price, and a closing message.

Respond concisely in this format:
1. Suggested Offer Price: ₹X (with reason)
2. Negotiation Tactics:
   - ...
3. Walk-away Price: ₹Y
4. Optional: Message to Seller
"""

        prompt = prompt_template.format(chat_history=formatted_history, input=user_message)
        result = await self.llm_connector.call_llm_api(prompt=prompt)
        return result or "Could not simulate negotiation at this time."

    async def get_general_negotiation_advice(self, user_question: str) -> str:
        """
        Responds with general negotiation advice when no specific property or price is involved.
        """
        prompt = f"""
You are a skilled real estate negotiation assistant in India.

The user is asking for general negotiation guidance related to property purchases.

User question:
"{user_question}"

Respond with 2–3 clear, practical negotiation tactics or strategies that a homebuyer can use when dealing with sellers. Focus on polite language, psychology, and market leverage. Avoid pricing unless mentioned.

Keep the response brief, professional, and actionable.
"""
        result = await self.llm_connector.call_llm_api(prompt)
        return result or "I'm unable to provide negotiation advice at the moment."
