from utils.llm_connector import LLMConnector

class MortgageRecommender:
    """
    Recommends suitable mortgage options based on user financial data using an LLM.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    async def get_mortgage_recommendations(self,
                                           income: float,
                                           credit_score: int,
                                           down_payment: float,
                                           loan_amount: float,
                                           property_type: str) -> str:
        """
        Generates personalized mortgage recommendations.

        Args:
            income (float): User's annual income.
            credit_score (int): User's credit score.
            down_payment (float): User's down payment amount.
            loan_amount (float): Desired loan amount.
            property_type (str): Type of property (e.g., "apartment", "independent house").

        Returns:
            str: A string containing personalized mortgage recommendations.
        """
        prompt = f"""Based on the following financial information, provide personalized mortgage recommendations for a property in India:

        - Annual Income: ₹{income:,.2f}
        - Credit Score: {credit_score}
        - Down Payment: ₹{down_payment:,.2f}
        - Desired Loan Amount: ₹{loan_amount:,.2f}
        - Property Type: {property_type}

        Consider different types of mortgage products available in India (e.g., fixed-rate, floating-rate, hybrid),
        typical eligibility criteria, and factors that might influence interest rates.
        Suggest which type of mortgage might be most suitable given these parameters and briefly explain why.
        Also, mention any general advice regarding mortgage applications in India.
        Format the recommendations as a comprehensive, well-structured paragraph or a few bullet points.
        """
        # Changed call_gemini_api to call_llm_api
        result = await self.llm_connector.call_llm_api(prompt)
        return result if result else "Could not retrieve mortgage recommendations at this time."

