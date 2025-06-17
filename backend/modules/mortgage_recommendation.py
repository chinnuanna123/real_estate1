from utils.llm_connector import LLMConnector
from tools.mortgage_utils import calculate_emi_and_salary_requirements


class MortgageRecommender:
    """
    Recommends suitable mortgage options based on user financial data using LLM and chat history context.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    def _format_history(self, chat_history: list[dict]) -> str:
        """
        Formats the external chat history passed from the main agent.
        """
        return "\n".join([
            f"{msg['role'].capitalize()}: {msg['text']}" for msg in chat_history or []
        ])

    async def get_mortgage_recommendations(
        self,
        income: float,
        credit_score: int,
        down_payment: float,
        loan_amount: float,
        property_type: str,
        chat_history: list[dict],
        user_context: str = None
    ) -> str:
        """
        Generates personalized mortgage advice using financial data and past chat context.
        """

        # 📊 Step 1: Calculate EMI + Salary requirements
        interest_rate = 8.0  # Static for now; can be dynamic based on credit_score later
        tenure_years = 25

        financials = calculate_emi_and_salary_requirements(
            loan_amount=loan_amount,
            annual_interest_rate=interest_rate,
            tenure_years=tenure_years
        )

        # 📄 Step 2: Construct user message with financials
        user_message = f"""
Evaluate the following buyer's mortgage profile:

• Property Type: {property_type}
• Annual Income: ₹{income:,.2f}
• Credit Score: {credit_score}
• Down Payment Available: ₹{down_payment:,.2f}
• Desired Loan Amount: ₹{loan_amount:,.2f}
• Estimated EMI: ₹{financials['emi']} / month
• Minimum Monthly Salary Required: ₹{financials['min_monthly_salary']}
• Minimum Annual Salary Required: ₹{financials['min_annual_salary']}
• Tenure Assumed: {tenure_years} years @ {interest_rate:.1f}%
• Additional Context: {user_context or 'No extra context provided'}

Provide:
1. Best-suited mortgage type (Fixed/Floating/Hybrid) and rationale.
2. Interest rate range based on profile and current Indian market.
3. Recommended loan tenure for balanced EMI and interest.
4. EMI estimate with assumptions.
5. Tips to improve mortgage approval chances.
6. Key advice for first-time applicants dealing with Indian banks or NBFCs.
"""

        # 🤖 Step 3: Prompt with chat history + current request
        prompt_template = """
You are an expert mortgage advisor helping homebuyers in India.

Instructions:
- Read buyer's financial details and compute logical next steps.
- Use chat history context if available.
- Structure advice clearly in numbered sections.
- Make recommendations practical, especially for first-time buyers.

Chat History:
{chat_history}

User Input:
{input}
"""

        formatted_history = self._format_history(chat_history)
        prompt = prompt_template.format(chat_history=formatted_history, input=user_message)

        result = await self.llm_connector.call_llm_api(prompt=prompt)
        return result or "Could not retrieve mortgage recommendations at this time."
