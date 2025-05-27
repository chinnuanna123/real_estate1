# tools/Google Search.py
import dataclasses
import os
import requests
import json
from typing import Union, List

# Define dataclasses to mimic the expected structure of the Google Search tool's output
@dataclasses.dataclass
class PerQueryResult:
    index: str | None = None
    publication_time: str | None = None # Not typically available directly from CSE snippet, but kept for consistency
    snippet: str | None = None
    source_title: str | None = None
    url: str | None = None
    title: str | None = None # Added title for better display

@dataclasses.dataclass
class SearchResults:
    query: str | None = None
    results: Union[List["PerQueryResult"], None] = None

# --- Helper function for fallback simulation ---
def _simulate_google_search(queries: List[str]) -> List[SearchResults]: # Corrected function name
    """
    (Internal) Simulates Google Search results for property listings when real API is not configured.
    """
    print(f"DEBUG: Falling back to SIMULATED Google Search for queries: {queries}")
    simulated_output: List[SearchResults] = []
    for query in queries:
        mock_per_query_results = [
            PerQueryResult(
                index="1",
                source_title="MagicBricks",
                title=f"Mock 2 BHK Apartment in Noida - {query}",
                snippet=f"Spacious 2BHK in a prime location. Price: ₹55 Lakh. Area: 1200 sq ft. Near {query.split('in ')[-1] if 'in ' in query else 'city center'}.",
                url="https://www.magicbricks.com/mock-property-1"
            ),
            PerQueryResult(
                index="2",
                source_title="99acres",
                title=f"Mock Independent House in {query.split('in ')[-1] if 'in ' in query else 'Delhi'} - {query}",
                snippet=f"Beautiful independent house. Price: ₹1.2 Crore. 3 BHK. Area: 1800 sq ft. Great for families.",
                url="https://www.99acres.com/mock-property-2"
            ),
            PerQueryResult(
                index="3",
                source_title="Housing.com",
                title=f"Mock Luxury Villa in {query.split('in ')[-1] if 'in ' in query else 'Gurgaon'} - {query}",
                snippet=f"High-end villa with all amenities. Rental yield potential. Price: ₹2.5 Crore. 4 BHK.",
                url="https://www.housing.com/mock-property-3"
            )
        ]
        simulated_output.append(SearchResults(query=query, results=mock_per_query_results))
    return simulated_output

# --- Main search function using actual API calls ---
def search(queries: List[str]) -> List[SearchResults]:
    """
    Makes actual Google Custom Search API calls to get real property listings.
    Requires GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables to be set.
    Falls back to simulated results if keys are missing or API call fails.
    """
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        print("WARNING: GOOGLE_API_KEY and/or GOOGLE_CSE_ID not set. Falling back to simulated results.")
        return _simulate_google_search(queries) # Corrected function call

    base_url = "https://www.googleapis.com/customsearch/v1"
    real_output: List[SearchResults] = []

    for query in queries:
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "num": 5, # Number of results to fetch per query (max 10 per request)
            "alt": "json" # Ensure JSON response
        }
        try:
            print(f"INFO: Making real Google Custom Search API call for query: '{query}'")
            response = requests.get(base_url, params=params)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            data = response.json()

            items = data.get('items', [])
            per_query_results: List[PerQueryResult] = []
            if items:
                for idx, item in enumerate(items):
                    # Extracting data from CSE results; exact fields depend on search engine config
                    per_query_results.append(
                        PerQueryResult(
                            index=str(idx + 1),
                            title=item.get('title'),
                            snippet=item.get('snippet'),
                            source_title=item.get('displayLink'), # e.g., "www.magicbricks.com"
                            url=item.get('link'),
                            publication_time=None # Not directly available from standard CSE results
                        )
                    )
            real_output.append(SearchResults(query=query, results=per_query_results))

        except requests.exceptions.RequestException as e:
            print(f"ERROR: Real Google Search API call failed for query '{query}': {e}")
            # Fallback to simulated results for this specific query if real API fails
            real_output.append(SearchResults(query=query, results=[]))
        except json.JSONDecodeError as e:
            print(f"ERROR: JSON decoding failed for Google Search API response for query '{query}': {e}")
            real_output.append(SearchResults(query=query, results=[]))
        except Exception as e:
            print(f"ERROR: An unexpected error occurred during Google Search API call for query '{query}': {e}")
            real_output.append(SearchResults(query=query, results=[]))

    # If all real API calls fail, but we've collected some data, return that.
    # Otherwise, if no real data was collected due to repeated errors, fall back to simulation.
    if any(res.results for res in real_output): # Check if any query returned real results
        return real_output
    else:
        print("WARNING: No real Google Search results obtained. Returning simulated results as a final fallback.")
        return _simulate_google_search(queries) # Corrected function call
