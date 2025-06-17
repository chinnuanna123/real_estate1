import json
from tools.google_search import GoogleSearchTool

class MockScraper:
    """
    A simulated data ingestion module.
    In a real application, this would perform actual web scraping or
    integrate with real estate listing APIs.
    """
    def __init__(self):
        self.google_search_tool = GoogleSearchTool()

    def get_mock_listings(self, query: str) -> list[dict]:
        """
        Generates mock property listings based on a query.
        This is a placeholder for actual scraping.
        """
        print(f"Simulating data ingestion for query: '{query}'")

        # Example mock properties - these would ideally come from a real data source
        # or be generated more dynamically based on query analysis.
        mock_properties = [
            {
                "id": "prop_001",
                "name": "Luxury 2BHK in Koramangala",
                "location": "Koramangala, Bengaluru",
                "price": "₹48 Lakh",
                "bedrooms": 2,
                "bathrooms": 2,
                "areaSqFt": 1100,
                "description": "Spacious 2BHK apartment in the heart of Koramangala. Ideal for young professionals, close to IT parks and vibrant nightlife. High rental yield potential due to prime location. Good schools nearby.",
                "imageUrl": "https://placehold.co/400x300/E0F2F7/000000?text=Koramangala+Home"
            },
            {
                "id": "prop_002",
                "name": "Modern 2BHK in HSR Layout",
                "location": "HSR Layout, Bengaluru",
                "price": "₹45 Lakh",
                "bedrooms": 2,
                "bathrooms": 2,
                "areaSqFt": 1050,
                "description": "Contemporary 2BHK flat in family-friendly HSR Layout. Excellent connectivity and proximity to tech hubs. Known for its planned infrastructure and green spaces. Strong rental demand.",
                "imageUrl": "https://placehold.co/400x300/F0F8FF/000000?text=HSR+Layout+Home"
            },
            {
                "id": "prop_003",
                "name": "Compact 2BHK in Marathahalli",
                "location": "Marathahalli, Bengaluru",
                "price": "₹38 Lakh",
                "bedrooms": 2,
                "bathrooms": 1,
                "areaSqFt": 900,
                "description": "Affordable 2BHK in a bustling area, perfect for investment. High footfall and commercial activity ensure consistent rental income. Close to major bus routes and shopping centers.",
                "imageUrl": "https://placehold.co/400x300/FAFAD2/000000?text=Marathahalli+Home"
            }
        ]

        # In a real scenario, you'd parse the query and return relevant mock data.
        # For simplicity, we'll return a subset or all based on a very basic check.
        lower_query = query.lower()
        filtered_properties = []
        for prop in mock_properties:
            if "2bhk" in lower_query and prop["bedrooms"] == 2:
                price_match = False
                if "50 lakhs" in lower_query or "50 lakh" in lower_query:
                    # Simple check for price under 50 Lakhs
                    try:
                        price_val = float(prop["price"].replace('₹', '').replace('Lakh', '').replace('Crore', '00').strip())
                        if "Crore" in prop["price"]:
                            price_val *= 100 # Convert Crore to Lakhs for comparison
                        if price_val <= 50:
                            price_match = True
                    except ValueError:
                        pass # Ignore if price parsing fails

                if price_match or ("50 lakhs" not in lower_query and "50 lakh" not in lower_query):
                    if ("nearby area" in lower_query or "high rental" in lower_query) and \
                       ("rental" in prop["description"].lower() or "investment" in prop["description"].lower()):
                        filtered_properties.append(prop)
                    elif "nearby area" not in lower_query and "high rental" not in lower_query:
                         filtered_properties.append(prop)

        return filtered_properties if filtered_properties else mock_properties # Return all if no specific match

    def get_real_data_fallback(self, query: str) -> list[dict]:
        """
        Fallback to Google Search if mock data is insufficient or not relevant.
        """
        print(f"Falling back to Google Search for real data for query: '{query}'")
        return self.google_search_tool.search(query)

