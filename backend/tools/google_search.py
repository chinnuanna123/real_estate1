import os
import re
import dataclasses
import json
import time
import random
from typing import Union, List, Optional
from tavily import TavilyClient
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup

# --- Dataclasses for property structure ---
@dataclasses.dataclass
class PerQueryResult:
    index: str | None = None
    publication_time: str | None = None
    snippet: str | None = None   # (kept for compatibility, but not used)
    source_title: str | None = None
    url: str | None = None
    price: str | None = None
    area_sqft: int | None = None
    location: str | None = None
    title: str | None = None
    raw_snippet: str | None = None  # Holds the full description text
    bedrooms: int | None = None
    bathrooms: int | None = None
    property_type: str | None = None
    formatted_description: str | None = None  # ← new field

    def __post_init__(self):
        """Ensure backward compatibility by populating snippet field"""
        if not self.snippet and self.raw_snippet:
            self.snippet = sanitize_snippet(self.raw_snippet)
        elif not self.snippet and self.formatted_description:
            self.snippet = self.formatted_description[:250] + "..." if len(self.formatted_description) > 250 else self.formatted_description

@dataclasses.dataclass
class SearchResults:
    query: str | None = None
    results: Union[List["PerQueryResult"], None] = None

# --- Helper functions ---
def sanitize_title(title: str) -> str:
    """Clean up property titles by removing common suffixes"""
    if not title:
        return "Untitled Property"
    title = re.sub(r'[-|\u2013].*$', '', title)
    title = title.replace("for Sale", "").replace("Explore", "")
    return title.strip().title()

def sanitize_snippet(snippet: str) -> str:
    """Clean and truncate property descriptions"""
    if not snippet:
        return "No description available."
    snippet = re.sub(r'\s+', ' ', snippet).strip()
    return snippet[:250] + '...' if len(snippet) > 250 else snippet

def clean_and_format_price(price_text: str) -> str:
    """
    Clean and format price text into standard format.
    Handles various Indian real estate price formats.
    """
    if not price_text:
        return "Price not available"

    price_text = re.sub(r'\s+', ' ', price_text).strip()
    price_text = re.sub(
        r'(onwards|negotiable|call for price|price on request)',
        '',
        price_text,
        flags=re.IGNORECASE
    )
    if re.search(r'call|request|enquire|contact', price_text, re.IGNORECASE):
        return "Price on request"

    patterns = [
        r'(\d+\.?\d*)\s*(?:-|to|–)\s*(\d+\.?\d*)\s*(crore|cr|lakh|lac|l|lakhs)',
        r'(\d+\.?\d*)\s*(crore|cr|lakh|lac|l|lakhs)',
        r'(?:₹|Rs\.?|INR)\s*(\d+\.?\d*)\s*(crore|cr|lakh|lac|l|lakhs)?',
        r'(?:₹|Rs\.?|INR)?\s*(\d{7,})',
        r'(?:₹|Rs\.?|INR)?\s*(\d{1,2},\d{2},\d{3,})',
        r'(\d+\.?\d*)\s*K\b'
    ]

    for pattern in patterns:
        match = re.search(pattern, price_text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if pattern.endswith('K\\b') and groups:
                value = float(groups[0])
                return f"₹{value/10:.2f} Lakh"
            if len(groups) == 3 and groups[2]:
                return f"₹{groups[0]} - {groups[1]} {groups[2].title()}"
            elif len(groups) >= 2 and groups[1]:
                value = float(groups[0])
                unit = groups[1].lower()
                if 'cr' in unit:
                    return f"₹{value:.2f} Cr"
                elif 'l' in unit:
                    return f"₹{value:.2f} Lakh"
            elif len(groups) >= 1:
                number_str = groups[0].replace(',', '')
                try:
                    value = float(number_str)
                    if value >= 10000000:
                        return f"₹{value/10000000:.2f} Cr"
                    elif value >= 100000:
                        return f"₹{value/100000:.2f} Lakh"
                    else:
                        return f"₹{value:,.0f}"
                except ValueError:
                    continue

    return "Price not available"

def extract_price_from_text(text: str) -> str:
    """Extract price from free-form text using multiple strategies"""
    if not text:
        return "Price not available"
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)

    price_context_patterns = [
        r'(?:price|cost|rate|amount|ask|asking|₹|rs\.?|inr)[:\s]*(\d+\.?\d*)\s*(cr|crore|lakh|lac|l)',
        r'(\d+\.?\d*)\s*(cr|crore|lakh|lac|l)\s*(?:only|onwards|negotiable)?',
        r'₹\s*(\d+\.?\d*)\s*(cr|crore|lakh|lac|l)?',
        r'(?:under|below|within|around|approx)\s*(\d+\.?\d*)\s*(cr|crore|lakh|lac|l)',
    ]

    for pattern in price_context_patterns:
        matches = re.findall(pattern, text)
        if matches:
            match = matches[0]
            if isinstance(match, tuple):
                value = match[0]
                unit = match[1] if len(match) > 1 else ''
                try:
                    num_value = float(value)
                    if unit:
                        if 'cr' in unit:
                            return f"₹{num_value:.2f} Cr"
                        elif 'l' in unit:
                            return f"₹{num_value:.2f} Lakh"
                    else:
                        if num_value > 100:
                            return f"₹{num_value/100:.2f} Lakh"
                        elif num_value > 10:
                            return f"₹{num_value:.2f} Lakh"
                        else:
                            return f"₹{num_value:.2f} Cr"
                except ValueError:
                    continue

    return "Price not available"

# --- Basic regex parser for fallback ---
def _basic_regex_parse_from_text(text: str, default_location: str = "Unknown") -> dict:
    """Extract property details from text using regex patterns"""
    text = text.lower()
    price = extract_price_from_text(text)

    bhk_match = re.search(r"(\d+)\s*(?:bhk|bedroom)", text)
    bedrooms = int(bhk_match.group(1)) if bhk_match else None

    bath_match = re.search(r"(\d+)\s*(?:bath|bathroom)", text)
    bathrooms = int(bath_match.group(1)) if bath_match else None

    area_match = re.search(r"(\d{3,5})\s*(?:sqft|sq\.?\s*ft|square feet)", text)
    area_sqft = int(area_match.group(1)) if area_match else None

    prop_type_match = re.search(
        r"(apartment|flat|villa|house|plot|land|commercial)",
        text,
        re.IGNORECASE
    )
    property_type = prop_type_match.group(1).title() if prop_type_match else "Residential"

    return {
        "price": price,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "area_sqft": area_sqft,
        "property_type": property_type
    }

# --- Extract discrete fields from raw snippet ---
def _extract_fields_from_snippet(raw_text: str, default_location: str) -> dict:
    """
    Take a raw snippet like "Carpet Area300 sqftStatusReady to MoveFloor4 out of 4..."
    and pull out named fields into a dict.
    """
    text = raw_text.strip()
    address = None
    remaining = text

    m_addr = re.search(r"Address\s*:\s*([^\r\n]+)", text, re.IGNORECASE)
    if m_addr:
        address = m_addr.group(1).strip()
        remaining = text[m_addr.end():].strip()

    lump = re.sub(r"\s+", "", remaining.lower())

    bedrooms = None
    m_bhk = re.search(r"(\d+)(?:bhk|bedroom)", lump)
    if m_bhk:
        bedrooms = int(m_bhk.group(1))

    bathrooms = None
    m_bath = re.search(r"bath(?:room)?(\d+)|(\d+)bath(?:room)?", lump)
    if m_bath:
        for g in m_bath.groups():
            if g and g.isdigit():
                bathrooms = int(g)
                break

    area_sqft = None
    m_area = re.search(r"(\d{3,5})(?:sqft|squarefeet|sq\.?ft)", lump)
    if m_area:
        area_sqft = int(m_area.group(1))

    status = None
    if "readytomove" in lump:
        status = "Ready to Move"
    elif "underconstruction" in lump:
        status = "Under Construction"
    elif "newlaunch" in lump or "new" in lump:
        status = "New"

    floor = None
    m_floor = re.search(r"floor(\d+)outof(\d+)", lump)
    if m_floor:
        floor = f"{m_floor.group(1)} out of {m_floor.group(2)}"

    transaction = None
    if "resale" in lump:
        transaction = "Resale"
    elif "new" in lump or "launch" in lump:
        transaction = "New"

    furnishing = None
    if "furnished" in lump:
        furnishing = "Furnished"
    elif "unfurnished" in lump:
        furnishing = "Unfurnished"

    balcony_count = None
    m_balcony = re.search(r"balcony(\d+)", lump)
    if m_balcony:
        balcony_count = int(m_balcony.group(1))

    price = extract_price_from_text(remaining)

    prop_type = None
    m_prop = re.search(
        r"(apartment|flat|villa|house|plot|land|commercial)",
        remaining,
        re.IGNORECASE
    )
    if m_prop:
        prop_type = m_prop.group(1).title()

    return {
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "area_sqft": area_sqft,
        "status": status,
        "floor": floor,
        "transaction": transaction,
        "furnishing": furnishing,
        "balcony_count": balcony_count,
        "price": price,
        "property_type": prop_type,
        "location": address or default_location
    }

def format_property_description(fields: dict) -> str:
    """
    Given a dict with keys like bedrooms, area_sqft, status, floor, etc.,
    return a richer 3–4 sentence English description.
    """
    parts = []

    # Sentence 1: Type, BHK, location
    bhk = fields.get("bedrooms")
    ptype = fields.get("property_type") or "Property"
    loc = fields.get("location")
    if bhk and loc:
        parts.append(f"This is a {bhk} BHK {ptype.lower()} located in {loc}.")
    elif bhk:
        parts.append(f"This is a {bhk} BHK {ptype.lower()}.")
    elif loc:
        parts.append(f"This is a {ptype.lower()} in {loc}.")
    else:
        parts.append(f"This is a {ptype.lower()}.")

    # Sentence 2: Carpet area + furnishing/status
    area = fields.get("area_sqft")
    status = fields.get("status")
    furn = fields.get("furnishing")
    if area:
        if status and furn:
            parts.append(
                f"It offers a carpet area of {area} sq ft and is {status.lower()} and {furn.lower()}."
            )
        elif status:
            parts.append(f"It offers a carpet area of {area} sq ft and is {status.lower()}.")
        elif furn:
            parts.append(f"It offers a carpet area of {area} sq ft and is {furn.lower()}.")
        else:
            parts.append(f"It offers a carpet area of {area} sq ft.")
    else:
        if status and furn:
            parts.append(f"It is {status.lower()} and {furn.lower()}.")
        elif status:
            parts.append(f"It is {status.lower()}.")
        elif furn:
            parts.append(f"It is {furn.lower()}.")

    # Sentence 3: Floor, bathrooms, balconies
    floor = fields.get("floor")
    baths = fields.get("bathrooms")
    balconies = fields.get("balcony_count")
    extras = []
    if floor:
        extras.append(f"located on the {floor} floor")
    if baths:
        extras.append(f"{baths} bathroom{'s' if baths > 1 else ''}")
    if balconies is not None:
        extras.append(f"{balconies} balcony{'ies' if balconies != 1 else ''}")
    if extras:
        parts.append(
            "It features "
            + ", ".join(extras[:-1])
            + ("" if len(extras) == 1 else " and ")
            + extras[-1]
            + "."
        )

    # Sentence 4: Price and transaction
    price = fields.get("price")
    trans = fields.get("transaction")
    if price and trans:
        parts.append(f"The property is priced at {price} and is available on a {trans.lower()} basis.")
    elif price:
        parts.append(f"The property is priced at {price}.")
    elif trans:
        parts.append(f"It is available on a {trans.lower()} basis.")

    return " ".join(parts)

# --- Enhanced property page parser with website-specific selectors ---
def _parse_property_page(html_content: str, url: str, page: Optional[Page] = None) -> dict:
    """
    Parse property details from HTML with website-specific strategies, including a
    formatted, human-readable description.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    data: dict = {}

    # Get title
    title_tag = soup.find('title')
    data['title'] = sanitize_title(title_tag.get_text()) if title_tag else "Property Details"

    # Determine which website we're on
    domain = url.split("//")[-1].split("/")[0].lower()

    # --- PRICE EXTRACTION ---


    if "99acres.com" in domain:
        price_selectors = [
            'span.list_header_bold',
            'div.factTablePrice',
            'span.priceIconSpan',
            'div#priceSection',
            'div.list_header_semiBold',
            'td#priceDetail',
            'div[class*="projectPriceDetail"]',
            'span[class*="configurationCardsPrice"]'
        ]
    elif "magicbricks.com" in domain:
        price_selectors = [
            'div.priceSqft__price',
            'span.priceSqft__price--text',
            'div.prop-price',
            'div[class*="price-details"]',
            'div.mb-ldp__pricing',
            'span.m-srp-card__price',
            'div[class*="priceDetail"]',
            'div[class*="price"]',
            'span[class*="price"]'
        ]
    elif "housing.com" in domain:
        price_selectors = [
            'div.price-details',
            'span.price-value',
            'div[class*="price-section"]',
            'h1[class*="price"]',
            'div.display-price',
            'span[class*="listing-price"]'
        ]
    elif "squareyards.com" in domain:
        price_selectors = [
            'h3.price',
            'div[class*="price-tag"]',
            'span.amount',
            'div.project-price',
            'span[class*="property-price"]'
        ]
    elif "makaan.com" in domain:
        price_selectors = [
            'div[class*="price-wrap"]',
            'span.price',
            'div.listing-price',
            'td[class*="price"]',
            'div[data-rf="price"]'
        ]
    else:
        price_selectors = [
            '[class*="price"]',
            '[class*="Price"]',
            '[class*="cost"]',
            '[class*="amount"]',
            '[data-price]',
            '[itemprop="price"]',
            'h1:has-text("₹")',
            'h2:has-text("₹")',
            'span:has-text("Cr")',
            'span:has-text("Lakh")'
        ]

    price = None
    for selector in price_selectors:
        try:
            price_elements = soup.select(selector)
            for element in price_elements:
                price_text = element.get_text(strip=True)
                if price_text and any(
                    ind in price_text
                    for ind in ['₹', 'Rs', 'INR', 'Cr', 'Lac', 'Lakh'] + list('0123456789')
                ):
                    price = clean_and_format_price(price_text)
                    if price and price != "Price not available":
                        break
            if price and price != "Price not available":
                break
        except Exception:
            continue

    # Try meta tags if no price found
    if not price or price == "Price not available":
        meta_price = soup.find('meta', {'property': 'product:price:amount'})
        if not meta_price:
            meta_price = soup.find('meta', {'name': 'price'})
        if not meta_price:
            meta_price = soup.find('meta', {'content': re.compile(r'₹|Rs\.?\s*\d+')})
        if meta_price and meta_price.get('content'):
            price = clean_and_format_price(meta_price['content'])

    # Last resort: search all text
    if not price or price == "Price not available":
        body_text = soup.get_text(separator=' ')
        price = extract_price_from_text(body_text)

    data['price'] = price if price else "Price not available"

    # --- DESCRIPTION EXTRACTION (improved) ---
    raw_description = None
    description_selectors = {
        "99acres.com": [
            'div[class*="projectDescFull"]',
            'div[class*="allDescr"]',
            'div[class*="readMoreContent"]',
            'div[class*="projectDesc"]',
            'div[class*="factTableDescription"]',
            'div#aboutProperty',
            'p[class*="desc"]',
            'div[class*="overview"]'
        ],
        "magicbricks.com": [
            'div.mb-ldp__desc-overview',
            'div.mb-ldp__descriptionBody',
            'div[id^="descriptionWrapper"]',
            'div.mb-ldp__description__full',
            'div.mb-ldp__description__text',
            'div.mb-ldp__description',
            'div[class*="prop-desc"]',
            'div[id*="description"]',
            'div.m-srp-card__desc',
            'div[class*="overview"]',
            'div[class*="dtl__desc"]'
        ],
        "housing.com": [
            'div[class*="description"]',
            'div[class*="overview"]',
            'div.css-1hidcok',
            'div#description',
            'p[class*="desc"]',
            'div.listing-description'
        ],
        "squareyards.com": [
            'div[class*="project-description"]',
            'div[id*="description"]',
            'div[class*="prop-desc"]',
            'p[class*="desc"]',
            'div[class*="overview"]'
        ],
        "makaan.com": [
            'div[class*="description"]',
            'div.listing-description',
            'div[id*="desc"]',
            'p[class*="desc"]',
            'div[class*="overview"]'
        ],
        "default": [
            'div[class*="description"]',
            'div[class*="Description"]',
            'div[class*="overview"]',
            'div[class*="summary"]',
            'p[class*="desc"]',
            'div[id*="description"]',
            'div[id*="overview"]',
            '[itemprop="description"]',
            'p:contains("about")',
            'div:contains("description")'
        ]
    }

    selectors = description_selectors.get(domain, description_selectors["default"])
    for selector in selectors:
        try:
            desc_elements = soup.select(selector)
            for element in desc_elements:
                desc_text = element.get_text(separator=" ", strip=True)
                if desc_text and len(desc_text) > 50:
                    raw_description = desc_text
                    break
            if raw_description:
                break
        except Exception:
            continue

    # Fallback: meta description
    if not raw_description:
        meta_desc = (
            soup.find('meta', {'name': 'description'}) 
            or soup.find('meta', {'property': 'og:description'})
        )
        if meta_desc and meta_desc.get('content'):
            raw_description = meta_desc['content'].strip()

    # Final fallback: regex search in page body
    if not raw_description:
        body_text = soup.get_text(separator=' ')
        desc_match = re.search(
            r'(?:about|description|overview|details)\s*:\s*([^.!?]{50,500})',
            body_text, 
            re.IGNORECASE
        )
        if desc_match:
            raw_description = desc_match.group(1).strip()

    data['raw_description'] = raw_description or ""

    # --- AREA EXTRACTION ---
    area = None
    area_selectors = {
        "99acres.com": ['td#builtUpAreaDisplay', 'span[class*="ellipsis"][title*="sq.ft"]', 'td#superBuiltUpAreaDisplay'],
        "magicbricks.com": ['div.mb-ldp__dtls__body__list--size', 'span.m-srp-card__area', 'div.area'],
        "housing.com": ['div.css-1ty5xzi', 'div.area-details', 'span.area'],
        "squareyards.com": ['div.project-area', 'span.size'],
        "makaan.com": ['td.size', 'div.listing-details-size'],
        "default": ['[class*="area"]', '[class*="size"]', '[data-area]', 'span:contains("sq.ft")', 'div:contains("sqft")']
    }

    selectors = area_selectors.get(domain, area_selectors["default"])
    for selector in selectors:
        try:
            area_elements = soup.select(selector)
            for element in area_elements:
                area_text = element.get_text(strip=True)
                area_match = re.search(r'(\d{3,5})\s*(?:sqft|sq\.?\s*ft|square feet)', area_text, re.IGNORECASE)
                if area_match:
                    area = int(area_match.group(1))
                    break
            if area:
                break
        except Exception:
            continue

    data['area_sqft'] = area if area else None

    # --- BEDROOMS & BATHROOMS EXTRACTION ---
    body_text = soup.get_text(separator=' ').lower()
    bhk_match = re.search(r'(\d+)\s*(?:BHK|bhk|Bedroom|bedroom)', body_text, re.IGNORECASE)
    data['bedrooms'] = int(bhk_match.group(1)) if bhk_match else None
    bath_match = re.search(r'(\d+)\s*(?:Bath|bath|Bathroom|bathroom)', body_text, re.IGNORECASE)
    data['bathrooms'] = int(bath_match.group(1)) if bath_match else None

    # --- PROPERTY TYPE EXTRACTION ---
    prop_type_match = re.search(
        r'(apartment|flat|villa|house|plot|land|commercial)',
        body_text,
        re.IGNORECASE
    )
    data['property_type'] = prop_type_match.group(1).title() if prop_type_match else "Residential"

    # --- LOCATION EXTRACTION ---
    location = None
    location_selectors = {
        "99acres.com": ['div#locality', 'span.locName', 'div.project-address'],
        "magicbricks.com": ['div.mb-ldp__dtls__body__list--location', 'span.m-srp-card__title--loc'],
        "housing.com": ['div.css-1c9b2d8', 'span.location'],
        "squareyards.com": ['div.project-locality', 'span.locality'],
        "makaan.com": ['div.locWrap', 'span.locality'],
        "default": ['[class*="location"]', '[class*="locality"]', '[itemprop="address"]', 'span:contains(" in ")']
    }

    selectors = location_selectors.get(domain, location_selectors["default"])
    for selector in selectors:
        try:
            loc_elements = soup.select(selector)
            for element in loc_elements:
                loc_text = element.get_text(strip=True)
                if loc_text and len(loc_text) > 3:
                    location = loc_text.strip()
                    break
            if location:
                break
        except Exception:
            continue

    data['location'] = location if location else "Unknown"

    return data

# --- Stealth browser setup functions ---
def setup_stealth_page(page: Page):
    """
    Configure a page with stealth settings to avoid detection.
    """
    stealth_js = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            {
                0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                description: "Portable Document Format",
                filename: "internal-pdf-viewer",
                length: 1,
                name: "Chrome PDF Plugin"
            },
            {
                0: {type: "application/x-nacl", suffixes: "", description: "Native Client"},
                description: "Native Client",
                filename: "internal-nacl-plugin",
                length: 1,
                name: "Native Client"
            }
        ]
    });
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
    const originalConsoleDebug = console.debug;
    console.debug = function(...args) {
        if (args[0] && typeof args[0] === 'string' && args[0].includes('webdriver')) {
            return;
        }
        return originalConsoleDebug.apply(console, args);
    };
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    """
    page.add_init_script(stealth_js)

def random_delay(min_seconds: float = 1, max_seconds: float = 3):
    """Add human-like random delays"""
    delay = random.uniform(min_seconds, max_seconds)
    print(f"  Waiting {delay:.1f} seconds...")
    time.sleep(delay)

def simulate_human_behavior(page: Page):
    """Simulate human-like interaction with the page"""
    try:
        for _ in range(random.randint(2, 4)):
            x = random.randint(100, 1000)
            y = random.randint(100, 700)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.1, 0.3))
        scroll_distance = random.randint(100, 300)
        page.evaluate(f"window.scrollBy(0, {scroll_distance})")
        time.sleep(random.uniform(0.5, 1))
        if random.random() > 0.5:
            page.evaluate(f"window.scrollBy(0, -{scroll_distance//2})")
            time.sleep(random.uniform(0.3, 0.7))
    except Exception as e:
        print(f"  Note: Human simulation issue: {e}")

# --- Main search function ---
def search_properties(queries: List[str]) -> List[SearchResults]:
    """
    Main search function that properly manages browser lifecycle with enhanced error handling.
    """
    if not queries:
        return []
    
    all_results: List[SearchResults] = []
    
    # Validate input and flatten if needed
    flattened_queries = []
    for q in queries:
        if isinstance(q, list):
            flattened_queries.extend(q)
        else:
            flattened_queries.append(q)
    
    valid_queries = [q.strip() for q in flattened_queries if q and isinstance(q, str) and q.strip()]
    if not valid_queries:
        return [SearchResults(query="", results=[])]

    # Setup Tavily if available
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    if not TAVILY_API_KEY:
        print("⚠️  WARNING: TAVILY_API_KEY not set. Will use limited search.")
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,  # Change to False for debugging
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                ]
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                locale='en-US',
                timezone_id='Asia/Kolkata'
            )
            page = context.new_page()
            setup_stealth_page(page)

            for query in valid_queries:
                try:
                    print(f"\n{'='*60}")
                    print(f"🏠 Searching for: '{query}'")
                    print(f"{'='*60}")

                    property_urls: List[dict] = []

                    # 1) Tavily search if API key is set
                    if tavily_client:
                        try:
                            print("📡 Using Tavily search...")
                            domains = [
                                "99acres.com",
                                "magicbricks.com",
                                "housing.com",
                                "squareyards.com",
                                "makaan.com",
                                "indiaproperty.com",
                                "commonfloor.com"
                            ]
                            response = tavily_client.search(
                                query=query,
                                include_domains=domains,
                                max_results=4
                            )
                            if response and "results" in response:
                                for item in response["results"]:
                                    url = item.get("url", "")
                                    if url and not any(skip in url for skip in ['search', 'listings', 'results']):
                                        property_urls.append({
                                            "url": url,
                                            "title": item.get("title", ""),
                                            "snippet": item.get("content", "")
                                        })
                                # Keep only 99acres.com or magicbricks.com URLs
                                property_urls = [
                                    p for p in property_urls
                                    if "magicbricks.com" in p["url"].lower()
                                    #or "99 acres.com" in p["url"].lower()
                                ]
                                print(f"  ✓ Kept {len(property_urls)} URLs from 99acres/magicbricks")
                        except Exception as e:
                            print(f"  ✗ Tavily search failed: {e}")

                    # 2) Manual search fallback
                    if not property_urls:
                        print("🔍 Performing manual search on property websites...")
                        try:
                            manual_urls = perform_manual_search(page, query)
                            property_urls.extend(manual_urls)
                            print(f"  ✓ Found {len(property_urls)} URLs from manual search")
                        except Exception as e:
                            print(f"  ✗ Manual search failed: {e}")

                    # 3) Process found properties
                    per_query_results: List[PerQueryResult] = []
                    for idx, prop_info in enumerate(property_urls):
                        url = prop_info["url"] if isinstance(prop_info, dict) else prop_info
                        print(f"\n📍 Property {idx+1}: {url}")

                        try:
                            random_delay(2, 4)
                            page.goto(url, wait_until="domcontentloaded", timeout=30000)
                            page.wait_for_timeout(random.randint(2000, 4000))
                            simulate_human_behavior(page)

                            # Expand MagicBricks "Read more"
                            if "magicbricks.com" in url.lower():
                                try:
                                    more_btn = (
                                        page.query_selector("text=Read more")
                                        or page.query_selector("text=View all details")
                                    )
                                    if more_btn:
                                        more_btn.click()
                                        page.wait_for_timeout(1200)
                                except Exception:
                                    pass

                            # Expand 99acres "View all details" / "Read more"
                            if "99acres.com" in url.lower():
                                try:
                                    more_selector = page.query_selector("text=View all details")
                                    if more_selector:
                                        more_selector.click()
                                        page.wait_for_timeout(1000)
                                    else:
                                        alt_selector = page.query_selector("text=Read more")
                                        if alt_selector:
                                            alt_selector.click()
                                            page.wait_for_timeout(1000)
                                except Exception:
                                    pass

                            # Now grab fully expanded HTML
                            html_content = page.content()
                            parsed_data = _parse_property_page(html_content, url, page)

                            # Build the 3–4 sentence description
                            raw_desc = parsed_data.get("raw_description", "")
                            location = parsed_data.get("location", "Unknown")
                            fields = _extract_fields_from_snippet(raw_desc, location)
                            pretty_description = format_property_description(fields)

                            print(f"  ✓ Extracted successfully")
                            print(f"    Price: {parsed_data.get('price', 'Not found')}")
                            print(f"    Location: {parsed_data.get('location', 'Not found')}")
                            print(f"    Description: {pretty_description}")

                            result = PerQueryResult(
                                index=str(idx + 1),
                                title=parsed_data.get("title", "Property Details"),
                                source_title=url.split("//")[-1].split("/")[0],
                                url=url,
                                price=parsed_data.get("price"),
                                area_sqft=parsed_data.get("area_sqft"),
                                location=parsed_data.get("location"),
                                bedrooms=parsed_data.get("bedrooms"),
                                bathrooms=parsed_data.get("bathrooms"),
                                property_type=parsed_data.get("property_type"),
                                raw_snippet=parsed_data.get("raw_description", ""),
                                formatted_description=pretty_description
                            )
                            
                            # Ensure snippet is populated for backward compatibility
                            if not result.snippet:
                                result.snippet = sanitize_snippet(pretty_description or raw_desc)

                            per_query_results.append(result)

                        except Exception as e:
                            print(f"  ✗ Error: {e}")
                            # fallback logic if needed
                            if isinstance(prop_info, dict) and prop_info.get("snippet"):
                                fallback_data = _basic_regex_parse_from_text(
                                    f"{prop_info.get('title', '')} {prop_info.get('snippet', '')}",
                                    query
                                )
                                per_query_results.append(
                                    PerQueryResult(
                                        index=str(idx + 1),
                                        title=sanitize_title(prop_info.get("title", "")),
                                        snippet=sanitize_snippet(prop_info.get("snippet", "")),
                                        source_title=url.split("//")[-1].split("/")[0],
                                        url=url,
                                        price=fallback_data.get("price"),
                                        area_sqft=fallback_data.get("area_sqft"),
                                        location=query,
                                        bedrooms=fallback_data.get("bedrooms"),
                                        bathrooms=fallback_data.get("bathrooms"),
                                        property_type=fallback_data.get("property_type"),
                                        formatted_description=None
                                    )
                                )

                    all_results.append(SearchResults(query=query, results=per_query_results))

                except Exception as e:
                    print(f"✗ Error processing query '{query}': {e}")
                    # Add empty result for this query
                    all_results.append(SearchResults(query=query, results=[]))

            context.close()
            browser.close()

    except Exception as e:
        print(f"✗ Critical error in search_properties: {e}")
        # Return empty results for all queries instead of crashing
        all_results = [SearchResults(query=q, results=[]) for q in valid_queries]

    return all_results

def perform_manual_search(page: Page, query: str) -> List[dict]:
    """
    Perform manual search on property websites when Tavily is not available.
    Now only grabs individual-detail URLs for MagicBricks (those containing "/property-details/").
    """
    results: List[dict] = []
    search_configs = [
        {
            "site":     "99acres.com",
            "url":      f"https://www.99acres.com/search/property/buy/residential-all/{query.replace(' ', '-')}",
            "selector": "a[class*='body_med']"
        },
        {
            "site":     "magicbricks.com",
            "url":      (
                f"https://www.magicbricks.com/property-for-sale/residential-real-estate?"
                f"proptype=Multistorey-Apartment,Builder-Floor-Apartment,Penthouse,Studio-Apartment"
                f"&cityName={query.split()[-1]}"
            ),
            # Only grab links that look like a detail page (they have "/property-details/")
            "selector": "h2.mb-srp__card--title a[href*='property-details']"
        },
        {
            "site":     "housing.com",
            "url":      f"https://housing.com/in/buy/{query.replace(' ', '-')}",
            "selector": "a[class*='listing-card']"
        }
    ]

    for config in search_configs:
        try:
            print(f"  Searching on {config['site']}…")
            page.goto(config["url"], wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)

            links = page.query_selector_all(config["selector"])[:3]
            for link in links:
                href = link.get_attribute("href")
                if href:
                    # MagicBricks sometimes returns a relative URL; force the full URL
                    if not href.startswith("http"):
                        href = f"https://{config['site']}{href}"
                    results.append({"url": href, "title": "", "snippet": ""})
        except Exception as e:
            print(f"    Failed on {config['site']}: {e}")

    return results

def search(queries: List[str]) -> List[SearchResults]:
    """
    Expose a top-level search function for other modules.
    This ensures compatibility with property_search.py
    """
    try:
        return search_properties(queries)
    except Exception as e:
        print(f"Search error: {e}")
        # Return empty results instead of crashing
        return [SearchResults(query=q, results=[]) for q in queries]

# --- Main execution ---
if __name__ == "__main__":
    queries = [
        "2 bhk flat for sale in whitefield, bagalore"
    ]

    print("🚀 Starting property search...")
    print("💡 This uses stealth techniques to avoid detection")
    print("📝 Set TAVILY_API_KEY environment variable for better results\n")

    property_data = search_properties(queries)

    if property_data:
        for search_result in property_data:
            print(f"\n{'='*60}")
            print(f"📊 Results for: '{search_result.query}'")
            print('=' * 60)

            if search_result.results:
                for prop in search_result.results:
                    print(f"\n🏠 Property {prop.index}")
                    print(f"   📌 Title: {prop.title}")
                    print(f"   🔗 URL: {prop.url}")
                    print(f"   📍 Location: {prop.location}")
                    print(f"   💰 Price: {prop.price}")
                    print(f"   📝 Description: {prop.formatted_description}")
            else:
                print("❌ No properties found for this query.")
    else:
        print("❌ No search results were returned.")