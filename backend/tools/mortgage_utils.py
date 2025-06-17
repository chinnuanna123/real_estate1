import math

def calculate_emi_and_salary_requirements(
    loan_amount: float,
    annual_interest_rate: float,
    tenure_years: int,
    max_emi_ratio: float = 0.5  # Banks typically allow 40%–50% of salary toward EMI
) -> dict:
    """
    Calculates EMI and required monthly/annual salary for a given loan.

    Parameters:
    - loan_amount: Total loan amount (e.g., 5000000 for ₹50 lakh)
    - annual_interest_rate: Annual interest rate in % (e.g., 8.5)
    - tenure_years: Loan tenure in years (e.g., 25)
    - max_emi_ratio: Max EMI-to-salary ratio banks allow (default 50%)

    Returns:
    - Dict with EMI, min monthly salary, min annual salary
    """

    # Convert to monthly interest
    monthly_rate = annual_interest_rate / (12 * 100)
    num_months = tenure_years * 12

    # EMI formula
    emi = loan_amount * monthly_rate * (math.pow(1 + monthly_rate, num_months)) / (math.pow(1 + monthly_rate, num_months) - 1)

    # Estimate minimum salary required
    min_monthly_salary = emi / max_emi_ratio
    min_annual_salary = min_monthly_salary * 12

    return {
        "emi": round(emi, 2),
        "min_monthly_salary": round(min_monthly_salary, 2),
        "min_annual_salary": round(min_annual_salary, 2)
    }
