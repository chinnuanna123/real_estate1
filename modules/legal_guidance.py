from utils.llm_connector import LLMConnector

class LegalGuide:
    """
    Provides guidance on the legal and paperwork process using an LLM.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    async def get_legal_guidance(self) -> str:
        """
        Generates an overview of the legal and paperwork process for property buying in India.
        """
        prompt = """Provide a concise overview of the typical legal and paperwork process involved in buying a residential property in India,
        from offer acceptance to property registration. Include key steps like:
        1. Offer and Acceptance (Agreement to Sell)
        2. Due Diligence (property title, encumbrances, approvals)
        3. Loan Sanction (if applicable)
        4. Stamp Duty Payment
        5. Property Registration (Deed of Conveyance)
        6. Mutation of Records
        Explain each step briefly in a clear, easy-to-understand manner.
        """
        result = await self.llm_connector.call_llm_api(prompt)
        return result if result else "Could not retrieve legal guidance at this time."

