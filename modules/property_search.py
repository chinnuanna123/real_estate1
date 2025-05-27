import json
import re
from typing import List, Dict, Any, Optional
from utils.llm_connector import LLMConnector
from tools.google_search import search as google_search_tool # Ensure this is 'Google Search', not 'Google Search'

class PropertySearch:
    """
    Handles property search queries, extracting criteria and using LLM for mock generation
    or external tools (like Google Search) to find relevant properties.
    Uses enhanced regex for robust parsing of Google Search snippets to reduce LLM calls.
    """
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    async def _extract_search_criteria(self, query: str) -> Dict[str, Any]:
        """
        Uses the LLM to extract structured search criteria from a natural language query.
        This LLM call happens once per user search query.
        """
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "Primary location mentioned in the query (e.g., 'Noida', 'Koramangala, Bangalore')."},
                "bedrooms": {"type": "INTEGER", "description": "Number of bedrooms (e.g., 2 for 2BHK). Can be null."},
                "min_price": {"type": "NUMBER", "description": "Minimum budget in Lakhs or Crores, converted to a number. Can be null."},
                "max_price": {"type": "NUMBER", "description": "Maximum budget in Lakhs or Crores, converted to a number. Can be null."},
                "property_type": {"type": "STRING", "description": "Type of property (e.g., 'apartment', 'house', 'villa'). Can be null."},
                "keywords": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Additional keywords for search (e.g., 'furnished', 'near park')."}
            },
            "required": ["location"]
        }

        prompt = f"""Extract property search criteria from the following user query.
        Convert prices to numerical values in Lakhs (e.g., '50 Lakhs' -> 50, '1.2 Crore' -> 120).
        If a price range is given (e.g., 'between 50-70 Lakhs'), populate both min_price and max_price.
        If only a maximum price is given (e.g., 'under 50 Lakhs'), populate only max_price.
        If only a minimum price is given (e.g., 'above 1 Crore'), populate only min_price.
        Ensure the location is always provided.

        Query: "{query}"
        """
        try:
            extracted_data = await self.llm_connector.call_llm_api(prompt, response_schema=response_schema)
            if isinstance(extracted_data, dict):
                return extracted_data
            else:
                print(f"Warning: LLM did not return expected structured data for criteria extraction: {extracted_data}")
                return {"location": query, "keywords": [query]}
        except Exception as e:
            print(f"Error extracting search criteria with LLM: {e}")
            return {"location": query, "keywords": [query]}

    def _basic_regex_parse(self, title: str, snippet: str, default_location: str) -> Dict[str, Any]:
        """
        Enhanced regex and rule-based parsing for property details from title and snippet.
        This avoids additional LLM calls for each search result.
        """
        combined_text = (title + " " + snippet).lower() # Combine and lower for easier matching

        # --- Price Extraction ---
        price_str = "Price N/A"
        # Regex patterns for various price formats (most specific to least specific)
        price_patterns = [
            r'₹?\s*(\d+\.?\d*)\s*(crore|cr)',                     # e.g., ₹1.2 Crore, 1.5 Cr
            r'₹?\s*(\d+\.?\d*)\s*(lakh|lac|lacs)',                # e.g., ₹55 Lakh, 60 Lacs
            r'(\d+)\s*(?:-|\s*to\s*)?\s*(\d+)?\s*(?:lakh|crore|cr)?', # e.g., 50-70 Lakh, 1.2-1.5 Cr
            r'under\s*₹?\s*(\d+\.?\d*)\s*(lakh|crore|cr)',        # e.g., under ₹70 Lakh
            r'above\s*₹?\s*(\d+\.?\d*)\s*(lakh|crore|cr)',        # e.g., above ₹1 Crore
            r'₹?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(lakh|crore|cr)?' # General number with comma, optional unit
        ]

        for pattern in price_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                value = match.group(1).replace(',', '') # Remove commas from number
                unit = match.group(2) if len(match.groups()) > 1 else None # Check if unit exists
                
                if unit:
                    if 'crore' in unit or 'cr' in unit:
                        price_str = f"₹{float(value):.2f} Crore"
                    elif 'lakh' in unit or 'lac' in unit:
                        price_str = f"₹{float(value):.2f} Lakh"
                else: # If no specific unit, try to infer or just display as is
                    if float(value) > 10000000: # Heuristic: if very large number, assume crore
                        price_str = f"₹{float(value)/10000000:.2f} Crore"
                    elif float(value) > 100000: # Heuristic: if large number, assume lakh
                        price_str = f"₹{float(value)/100000:.2f} Lakh"
                    else:
                        price_str = f"₹{float(value):,.0f}" # Just a raw number

                # Handle ranges if two numbers are captured by some patterns
                if len(match.groups()) > 1 and match.group(2) and re.match(r'^\d+(\.\d+)?$', match.group(2).replace(',', '')):
                    value2 = match.group(2).replace(',', '')
                    price_str += f" - ₹{value2}" # Simple concatenation for range display
                
                break # Found a price, break from loop

        # --- Bedrooms Extraction ---
        bedrooms_val = 0
        bedrooms_match = re.search(r'(\d+)\s*(bhk|bed|beds|bedroom|bedrooms)', combined_text)
        if bedrooms_match:
            bedrooms_val = int(bedrooms_match.group(1))
        elif 'studio' in combined_text:
            bedrooms_val = 1 # Commonly considered 1-bedroom equivalent for display
        elif '1rk' in combined_text:
            bedrooms_val = 0 # Or 1, depending on definition (Room-kitchen, no separate bed)

        # --- Bathrooms Extraction ---
        bathrooms_val = 0
        bathrooms_match = re.search(r'(\d+)\s*(bath|baths|bathroom|bathrooms)', combined_text)
        if bathrooms_match:
            bathrooms_val = int(bathrooms_match.group(1))

        # --- Area Extraction ---
        area_val = 0
        area_match_sqft = re.search(r'(\d+)\s*(sq\.?\s*ft|sqft|sft|s\.f\.t\.)', combined_text)
        area_match_sqm = re.search(r'(\d+)\s*(sq\.?\s*m|sqm)', combined_text)
        area_match_other_units = re.search(r'(\d+)\s*(yards|yd|acres)', combined_text) # Example for other units

        if area_match_sqft:
            area_val = int(area_match_sqft.group(1))
        elif area_match_sqm:
            area_val = int(float(area_match_sqm.group(1)) * 10.764) # Convert sq m to sq ft
        elif area_match_other_units:
            # Add conversion for other units if necessary
            pass # For now, just pass

        # --- Location Refinement ---
        # Try to extract a more specific location from the title first
        # Example: "Flats for Sale in Kodigehalli Main Road Bangalore" -> "Kodigehalli Main Road, Bangalore"
        # This regex tries to capture a common pattern like "in [Location Name]"
        parsed_location = default_location
        location_patterns = [
            r'(?:in|near)\s+([\w\s,.-]+(?:road|layout|extension|colony|nagar|puram|city|town|district|mumbai|delhi|bangalore|noida|gurgaon))',
            r'in\s+([\w\s,.-]+)',
            r'([a-z\s]+(?:road|layout|extension|colony|nagar|puram|city|town)\s*\-?\s*[a-z\s]+)', # More generic place name
        ]
        
        for pattern in location_patterns:
            loc_match = re.search(pattern, title + " " + snippet, re.IGNORECASE)
            if loc_match and loc_match.group(1):
                extracted_loc = loc_match.group(1).strip()
                # A heuristic to prevent overly generic or irrelevant matches
                if len(extracted_loc.split()) > 1 or extracted_loc.lower() in [s.lower() for s in ["noida", "delhi", "bangalore", "gurgaon", "mumbai", "kolkata", "chennai", "hyderabad", "pune"]]:
                     parsed_location = extracted_loc
                     break # Found a good location, break

        # Fallback for name from title
        name_from_title = title.split(' - ')[0].strip() if ' - ' in title else title.strip()
        if name_from_title.lower().startswith('flats for sale in'):
            name_from_title = name_from_title.replace('flats for sale in', '').strip()

        return {
            "name": name_from_title,
            "location": parsed_location,
            "price": price_str,
            "bedrooms": bedrooms_val,
            "bathrooms": bathrooms_val,
            "areaSqFt": area_val,
            "description": snippet or "No detailed description available.",
        }


    async def search_properties(self, preferences_text: str) -> Dict[str, Any]:
        """
        Searches for properties based on user preferences.
        Tries LLM generation first, then falls back to Google Search with regex-enhanced parsing.
        """
        print(f"Attempting LLM-based property generation for: '{preferences_text}'")

        llm_prompt_mock_properties = f"""Generate a JSON array of 3-5 mock real estate properties based on the following buyer preferences: "{preferences_text}".
        Each property object should have:
        - "id": a unique string ID
        - "name": a catchy name for the property
        - "location": a specific location (e.g., "Koramangala, Bengaluru" or "Marine Drive, Mumbai")
        - "price": a realistic price in INR (e.g., "₹1.5 Crore", "₹85 Lakh")
        - "bedrooms": number of bedrooms
        - "bathrooms": number of bathrooms
        - "areaSqFt": area in square feet
        - "description": a brief, appealing description of the property, including details relevant to rental yield if applicable.
        - "imageUrl": a placeholder image URL (e.g., "https://placehold.co/400x300/E0F2F7/000000?text=Home")
        Ensure the JSON is valid and only contains the array.
        If the preferences are very specific and cannot be easily mocked, try to generate properties that align conceptually.
        """

        property_schema = {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "name": {"type": "STRING"},
                    "location": {"type": "STRING"},
                    "price": {"type": "STRING"},
                    "bedrooms": {"type": "NUMBER"},
                    "bathrooms": {"type": "NUMBER"},
                    "areaSqFt": {"type": "NUMBER"},
                    "description": {"type": "STRING"},
                    "imageUrl": {"type": "STRING"}
                },
                "required": ["id", "name", "location", "price", "bedrooms", "bathrooms", "areaSqFt", "description", "imageUrl"]
            }
        }

        try:
            parsed_properties = await self.llm_connector.call_llm_api(llm_prompt_mock_properties, response_schema=property_schema)
            if parsed_properties and isinstance(parsed_properties, list) and len(parsed_properties) > 0:
                print("LLM successfully generated mock properties.")
                return {"type": "properties", "data": parsed_properties}
            else:
                print("LLM did not generate sufficient mock properties. Falling back to Google Search.")
        except Exception as e:
            print(f"Error during LLM mock property generation: {e}. Falling back to Google Search.")

        # Fallback to Google Search if LLM generation fails or returns no properties
        print(f"Initiating Google Search for live properties based on: '{preferences_text}'")
        search_criteria = await self._extract_search_criteria(preferences_text)
        print(f"Extracted search criteria for Google Search: {search_criteria}")

        location_from_criteria = search_criteria.get("location")
        bedrooms = search_criteria.get("bedrooms")
        min_price = search_criteria.get("min_price")
        max_price = search_criteria.get("max_price")
        property_type = search_criteria.get("property_type")
        keywords = search_criteria.get("keywords", [])

        google_query_parts = []
        if bedrooms:
            google_query_parts.append(f"{bedrooms} BHK")
        if property_type:
            google_query_parts.append(property_type)
        if location_from_criteria:
            google_query_parts.append(f"in {location_from_criteria}")
        if min_price and max_price:
            google_query_parts.append(f"price between {min_price} Lakhs and {max_price} Lakhs")
        elif min_price:
            google_query_parts.append(f"price above {min_price} Lakhs")
        elif max_price:
            google_query_parts.append(f"price under {max_price} Lakhs")
        if keywords:
            google_query_parts.extend(keywords)

        final_google_query = " ".join(google_query_parts) + " properties India"
        if not final_google_query.strip():
            final_google_query = f"properties in {preferences_text} India"

        print(f"Performing Google Search with query: '{final_google_query}'")

        try:
            google_results = google_search_tool(queries=[final_google_query])
            
            formatted_google_results: List[Dict[str, Any]] = []
            if google_results and google_results[0].results:
                for idx, res in enumerate(google_results[0].results[:5]):
                    parsed_details = self._basic_regex_parse(
                        title=res.title,
                        snippet=res.snippet,
                        default_location=location_from_criteria or "Unknown Location"
                    )

                    formatted_google_results.append({
                        "id": f"gs_{idx+1}",
                        "name": parsed_details.get('name', res.title),
                        "location": parsed_details.get('location', location_from_criteria or "Unknown Location"),
                        "price": parsed_details.get('price', "Price N/A"),
                        "bedrooms": parsed_details.get('bedrooms', 0),
                        "bathrooms": parsed_details.get('bathrooms', 0),
                        "areaSqFt": parsed_details.get('areaSqFt', 0),
                        "description": parsed_details.get('description', res.snippet or "No detailed description available."),
                        "imageUrl": f"https://placehold.co/400x300/E0F2F7/000000?text=Google+Search+{idx+1}",
                        "link": res.url
                    })
            
            if formatted_google_results:
                print("Google Search provided results with regex-enhanced parsing.")
                return {"type": "properties", "data": formatted_google_results}
            else:
                print("Google Search found no relevant results even with regex parsing.")
                return {"type": "Google Search", "data": google_results[0].results if google_results and google_results[0].results else []}

        except Exception as e:
            print(f"Error during Google property search with regex parsing: {e}")
            return {"type": "error", "message": f"Failed to perform property search: {e}"}

