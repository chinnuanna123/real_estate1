import json
import re
from typing import List, Dict, Any, Optional
from utils.llm_connector import LLMConnector
from tools.google_search import search as google_search_tool
from starlette.concurrency import run_in_threadpool

class PropertySearch:
    def __init__(self, llm_connector: LLMConnector):
        self.llm_connector = llm_connector

    async def _extract_search_criteria(self, query: str) -> Dict[str, Any]:
        response_schema = {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "bedrooms": {"type": "integer"},
                "min_price": {"type": "number"},
                "max_price": {"type": "number"},
                "property_type": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["location"]
        }

        prompt = f"""
        Extract structured property search criteria from the following query:
        Query: "{query}"
        
        Return the location and relevant keywords for property search.
        """
        try:
            result = await self.llm_connector.call_llm_api(prompt, response_schema=response_schema)
            print(f"[DEBUG] LLM extraction result: {result}")
            
            if isinstance(result, dict) and result.get("location"):
                loc = result['location'].lower().strip()

                # ✅ Clean keywords: remove old keywords and ensure current location is primary
                if 'keywords' in result and isinstance(result['keywords'], list):
                    result['keywords'] = [kw for kw in result['keywords'] if kw.lower().strip() != loc]
                    if loc not in [kw.lower().strip() for kw in result['keywords']]:
                        result['keywords'] = [loc] + result['keywords']
                else:
                    result['keywords'] = [loc]

                return result

            else:
                # Fallback parsing
                return self._fallback_parse_query(query)
        except Exception as e:
            print(f"[DEBUG] LLM extraction failed: {e}")
            return self._fallback_parse_query(query)
    
    def _fallback_parse_query(self, query: str) -> Dict[str, Any]:
        """Fallback method to parse query when LLM fails"""
        import re
        
        # Extract location (words after 'in')
        location_match = re.search(r'\bin\s+([a-zA-Z\s,]+?)(?:\s|$)', query, re.IGNORECASE)
        location = location_match.group(1).strip() if location_match else "pune"
        
        # Extract keywords
        keywords = []
        if re.search(r'\d+\s*bhk', query, re.IGNORECASE):
            bhk_match = re.search(r'(\d+)\s*bhk', query, re.IGNORECASE)
            keywords.append(f"{bhk_match.group(1)} BHK")
        
        if re.search(r'flat|apartment', query, re.IGNORECASE):
            keywords.append("flat")
            
        if not keywords:
            keywords = ["2 BHK", "flat"]
            
        return {
            "location": location,
            "keywords": keywords
        }

    def _basic_regex_parse(self, title: str, snippet: str, default_location: str) -> Dict[str, Any]:
        text = (title + " " + snippet).lower()

        # Try extracting a numeric price
        match_price = re.search(r"₹\s?([0-9,.]+)\s*(crore|lakh|lac|cr)?", text)
        price = "Price not available"
        if match_price:
            val, unit = match_price.groups()
            num = float(val.replace(",", ""))
            if unit and "cr" in unit:
                price = f"₹{num:.2f} Cr"
            elif unit and ("lac" in unit or "lakh" in unit):
                price = f"₹{num:.2f} Lakh"
            else:
                price = f"₹{num:,.0f}"

        # Title clean-up
        clean_name = re.sub(r"(\d+\+|Explore|Buy|Rent).*", "", title).strip().title()

        # Location logic (fallback to default)
        location_match = re.search(r"in\s+([a-zA-Z\s,]+)", title, re.IGNORECASE)
        location = location_match.group(1).strip().title() if location_match else default_location

        # Extract BHK (bedrooms)
        bedrooms_match = re.search(r"(\d+)\s*(bhk|bedroom)", text)
        bedrooms = int(bedrooms_match.group(1)) if bedrooms_match else 2

        # Extract bathrooms
        bath_match = re.search(r"(\d+)\s*(bath|bathroom)", text)
        bathrooms = int(bath_match.group(1)) if bath_match else 2

        # Extract area in sqft
        area_match = re.search(r"(\d{3,5})\s*(sqft|sq\.\s*ft|square feet)", text)
        area_sqft = int(area_match.group(1)) if area_match else 1000

        return {
            "name": clean_name or "Unnamed Property",
            "location": location,
            "price": price,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "areaSqFt": area_sqft,
            "description": snippet.strip() if snippet else "No description available."
        }

    async def search_properties(self, preferences_text: str) -> Dict[str, Any]:
        try:
            # 1) Grab fresh criteria
            criteria  = await self._extract_search_criteria(preferences_text)
            location  = criteria.get("location", preferences_text)
            bedrooms  = criteria.get("bedrooms")
            ptype     = criteria.get("property_type")

            # 2) Build search_terms only from these fields
            parts = []
            if bedrooms:
                parts.append(f"{bedrooms} BHK")
            if ptype:
                parts.append(ptype)
            if location:
                parts.append(f"in {location}")

            # Fallback: if nothing parsed, use the raw preferences_text
            search_terms = " ".join(parts) if parts else preferences_text

            print(f"[SEARCH] Query: {search_terms}")
            print(f"[DEBUG] Parsed criteria: location={location}, bedrooms={bedrooms}, property_type={ptype}")
                
            google_results = await run_in_threadpool(google_search_tool, [search_terms])

            if not google_results or not google_results[0].results:
                print("[DEBUG] No results from google search, returning mock data for testing...")
                # Return mock data for testing
                mock_properties = [{
                    "id": "mock_1",
                    "name": f"2 BHK Flat in {location}",
                    "location": location,
                    "price": "₹75.00 Lakh",
                    "bedrooms": 2,
                    "bathrooms": 2,
                    "areaSqFt": 1200,
                    "description": f"Beautiful 2 BHK apartment located in {location}. This property offers modern amenities and excellent connectivity.",
                    "imageUrl": "https://placehold.co/400x300/E0F2F7/000000?text=Property+1",
                    "link": "#",
                    "property_type": "Apartment"
                }]
                return {"type": "properties", "data": mock_properties}

            properties = []
            for idx, res in enumerate(google_results[0].results[:5]):  # Process more results
                # Use the correct fields from PerQueryResult
                title = res.title or f"Property #{idx+1}"
                
                # Use formatted_description if available, otherwise fall back to raw_snippet or snippet
                description = (
                    res.formatted_description or 
                    res.raw_snippet or 
                    res.snippet or 
                    "No description available."
                )
                
                # If we have structured data from the enhanced search, use it
                if res.price and res.location and res.bedrooms:
                    property_obj = {
                        "id": f"property_{idx+1}",
                        "name": title,
                        "location": res.location,
                        "price": res.price,
                        "bedrooms": res.bedrooms or 2,
                        "bathrooms": res.bathrooms or 2,
                        "areaSqFt": res.area_sqft or 1000,
                        "description": description,
                        "imageUrl": f"https://placehold.co/400x300/E0F2F7/000000?text=Property+{idx+1}",
                        "link": res.url or "#",
                        "property_type": res.property_type or "Residential"
                    }
                else:
                    # Fall back to regex parsing for incomplete data
                    parsed = self._basic_regex_parse(title, description, location)
                    property_obj = {
                        "id": f"property_{idx+1}",
                        "name": parsed.get("name", title),
                        "location": parsed.get("location", location),
                        "price": parsed.get("price", "Price N/A"),
                        "bedrooms": parsed.get("bedrooms", 2),
                        "bathrooms": parsed.get("bathrooms", 2),
                        "areaSqFt": parsed.get("areaSqFt", 1000),
                        "description": parsed.get("description", description),
                        "imageUrl": f"https://placehold.co/400x300/E0F2F7/000000?text=Property+{idx+1}",
                        "link": res.url or "#"
                    }

                properties.append(property_obj)

            return {"type": "properties", "data": properties}

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print("❌ Google property search error:", repr(e))
            print("❌ Full traceback:")
            print(tb)
            return {"type": "error", "message": f"Search failed: {str(e)}"}