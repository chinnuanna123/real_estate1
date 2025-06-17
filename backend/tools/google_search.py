import os
import re
import dataclasses
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
    snippet: str | None = None
    source_title: str | None = None
    url: str | None = None
    price: str | None = None
    area_sqft: int | None = None
    location: str | None = None
    title: str | None = None
    raw_snippet: str | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    property_type: str | None = None
    formatted_description: str | None = None
    amenities: List[str] | None = None
    landmarks: List[str] | None = None

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

def _basic_regex_parse_from_text(text: str, default_location: str = "Unknown") -> dict:
    """Extract property details from text using regex patterns, including amenities and landmarks"""
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

    # Extract amenities
    amenities = []
    amenity_patterns = r"(gym|pool|parking|garden|lift|elevator|clubhouse|security|play area|power backup)"
    for match in re.finditer(amenity_patterns, text, re.IGNORECASE):
        amenities.append(match.group(0).title())
    amenities = list(dict.fromkeys(amenities))

    # Extract landmarks
    landmarks = []
    landmark_patterns = r"(near\s*(?:metro|school|hospital|mall|airport|park|market)\s*[^\.,;]{0,50})"
    for match in re.finditer(landmark_patterns, text, re.IGNORECASE):
        landmarks.append(match.group(0).strip().title())
    landmarks = list(dict.fromkeys(landmarks))

    return {
        "price": price,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "area_sqft": area_sqft,
        "property_type": property_type,
        "amenities": amenities if amenities else None,
        "landmarks": landmarks if landmarks else None
    }

def _extract_fields_from_snippet(raw_text: str, default_location: str) -> dict:
    """
    Extract fields from raw snippet, including amenities and landmarks
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

    # Extract amenities
    amenities = []
    amenity_patterns = r"(gym|pool|parking|garden|lift|elevator|clubhouse|security|play area|power backup)"
    for match in re.finditer(amenity_patterns, remaining.lower(), re.IGNORECASE):
        amenities.append(match.group(0).title())
    amenities = list(dict.fromkeys(amenities))

    # Extract landmarks
    landmarks = []
    landmark_patterns = r"(near\s*(?:metro|school|hospital|mall|airport|park|market)\s*[^\.,;]{0,50})"
    for match in re.finditer(landmark_patterns, remaining.lower(), re.IGNORECASE):
        landmarks.append(match.group(0).strip().title())
    landmarks = list(dict.fromkeys(landmarks))

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
        "location": address or default_location,
        "amenities": amenities if amenities else None,
        "landmarks": landmarks if landmarks else None
    }

def format_property_description(fields: dict) -> str:
    """
    Generate a richer description including amenities and landmarks
    """
    parts = []

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

    floor = fields.get("floor")
    baths = fields.get("bathrooms")
    balconies = fields.get("balcony_count")
    amenities = fields.get("amenities")
    extras = []
    if floor:
        extras.append(f"located on the {floor} floor")
    if baths:
        extras.append(f"{baths} bathroom{'s' if baths > 1 else ''}")
    if balconies is not None:
        extras.append(f"{balconies} balcony{'ies' if balconies != 1 else ''}")
    if amenities:
        extras.append(f"amenities like {', '.join(amenities[:3]).lower()}{' and more' if len(amenities) > 3 else ''}")
    if extras:
        parts.append(
            "It features "
            + ", ".join(extras[:-1])
            + ("" if len(extras) == 1 else " and ")
            + extras[-1]
            + "."
        )

    price = fields.get("price")
    trans = fields.get("transaction")
    landmarks = fields.get("landmarks")
    if price and trans:
        parts.append(f"The property is priced at {price} and is available on a {trans.lower()} basis.")
    elif price:
        parts.append(f"The property is priced at {price}.")
    elif trans:
        parts.append(f"It is available on a {trans.lower()} basis.")
    if landmarks:
        parts.append(f"It is conveniently located {', '.join(landmarks[:2]).lower()}{' and other landmarks' if len(landmarks) > 2 else ''}.")

    return " ".join(parts)

def _parse_property_page(html_content: str, url: str, page: Optional[Page] = None) -> dict:
    """
    Parse property details with amenities and landmarks
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    data: dict = {}

    title_tag = soup.find('title')
    data['title'] = sanitize_title(title_tag.get_text()) if title_tag else "Property Details"

    domain = url.split("//")[-1].split("/")[0].lower()

    price_selectors = {
        "99acres.com": [
            'span.list_header_bold',
            'div.factTablePrice',
            'span.priceIconSpan',
            'div#priceSection',
            'div.list_header_semiBold',
            'td#priceDetail',
            'div[class*="projectPriceDetail"]',
            'span[class*="configurationCardsPrice"]'
        ],
        "magicbricks.com": [
            'div.priceSqft__price',
            'span.priceSqft__price--text',
            'div.prop-price',
            'div[class*="price-details"]',
            'div.mb-ldp__pricing',
            'span.m-srp-card__price',
            'div[class*="priceDetail"]',
            'div[class*="price"]',
            'span[class*="price"]'
        ],
        "housing.com": [
            'div.price-details',
            'span.price-value',
            'div[class*="price-section"]',
            'h1[class*="price"]',
            'div.display-price',
            'span[class*="listing-price"]'
        ],
        "squareyards.com": [
            'h3.price',
            'div[class*="price-tag"]',
            'span.amount',
            'div.project-price',
            'span[class*="property-price"]'
        ],
        "makaan.com": [
            'div[class*="price-wrap"]',
            'span.price',
            'div.listing-price',
            'td[class*="price"]',
            'div[data-rf="price"]'
        ],
        "default": [
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
    }
    price = None
    selectors = price_selectors.get(domain, price_selectors["default"])
    for selector in selectors:
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
    if not price or price == "Price not available":
        meta_price = soup.find('meta', {'property': 'product:price:amount'})
        if not meta_price:
            meta_price = soup.find('meta', {'name': 'price'})
        if not meta_price:
            meta_price = soup.find('meta', {'content': re.compile(r'₹|Rs\.?\s*\d+')})
        if meta_price and meta_price.get('content'):
            price = clean_and_format_price(meta_price['content'])
    if not price or price == "Price not available":
        body_text = soup.get_text(separator=' ')
        price = extract_price_from_text(body_text)
    data['price'] = price if price else "Price not available"

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
    if not raw_description:
        meta_desc = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
        if meta_desc and meta_desc.get('content'):
            raw_description = meta_desc['content'].strip()
    if not raw_description:
        body_text = soup.get_text(separator=' ')
        desc_match = re.search(r'(?:about|description|overview|details)\s*:\s*([^.!?]{50,500})', body_text, re.IGNORECASE)
        if desc_match:
            raw_description = desc_match.group(1).strip()
    data['raw_description'] = raw_description or ""

    amenities = []
    amenities_selectors = {
        "99acres.com": [
            'div#amenitiesSection ul li',
            'div[class*="amenities"] li',
            'span[class*="amenity"]',
            'div.factTableAmenities',
            'div[id*="amenities"] ul li',
            'div[class*="Amenities"] li',
            'div[id*="Amenities"] li',
            'ul[class*="amenityList"] li',
            'div.keypoint li'
        ],
        "magicbricks.com": [
            'div.mb-ldp__dtls__amenities li',
            'div.mb-ldp__amenity--list li',
            'div[class*="amenities"] li',
            'span[class*="amenity"]',
            'div[id*="amenities"] ul li',
            'div.mb-ldp__dtls__body__list--amenities',
            'ul#features li',
            'div.m-srp-card__amenity li',
            'div.mb-ldp__dtls__body__list--item:contains("Amenities") li',
            'div.component__features li'
        ],
        "housing.com": [
            'div.css-1v2k6a4 li',
            'div[class*="amenities"] li',
            'ul[class*="amenity-list"] li',
            'div[id*="amenities"] li'
        ],
        "default": [
            '[class*="amenities"] li',
            '[class*="amenity"] li',
            '[data-amenity]',
            'li:contains("gym")',
            'li:contains("pool")',
            'li:contains("parking")',
            'div:contains("amenities") li'
        ]
    }
    selectors = amenities_selectors.get(domain, amenities_selectors["default"])
    for selector in selectors:
        try:
            amenity_elements = soup.select(selector)
            for element in amenity_elements:
                # Check for amenities in direct text or nested elements
                amenity_text = element.get_text(strip=True).lower()
                # Handle nested div or span for items like "lift(s)"
                nested_div = element.find('div') or element.find('span')
                if nested_div:
                    nested_text = nested_div.get_text(strip=True).lower()
                    if nested_text:
                        amenity_text = nested_text
                # Clean up the text
                amenity_text = re.sub(r'[^a-z\s]', '', amenity_text).strip()
                # Split concatenated words if necessary (e.g., "elv high garden")
                words = amenity_text.split()
                potential_amenities = []
                current_amenity = []
                for word in words:
                    current_amenity.append(word)
                    combined = ''.join(current_amenity)
                    # Expanded list of keywords
                    if any(keyword in combined for keyword in [
                        'gym', 'pool', 'swimming', 'parking', 'garden', 'lift', 'elevator',
                        'clubhouse', 'security', 'play', 'power', 'backup', 'terrace',
                        'jogging', 'track', 'sports', 'community', 'hall'
                    ]):
                        # Map common misspellings or abbreviations
                        if 'elv' in combined or 'elevator' in combined:
                            potential_amenities.append('Lift')
                        elif 'pool' in combined or 'swimming' in combined:
                            potential_amenities.append('Swimming Pool')
                        elif 'garden' in combined:
                            potential_amenities.append('Garden')
                        elif 'parking' in combined:
                            potential_amenities.append('Parking')
                        elif 'gym' in combined:
                            potential_amenities.append('Gym')
                        elif 'clubhouse' in combined:
                            potential_amenities.append('Clubhouse')
                        elif 'security' in combined:
                            potential_amenities.append('Security')
                        elif 'play' in combined:
                            potential_amenities.append('Play Area')
                        elif 'power' in combined or 'backup' in combined:
                            potential_amenities.append('Power Backup')
                        elif 'terrace' in combined:
                            potential_amenities.append('Terrace')
                        elif 'jogging' in combined or 'track' in combined:
                            potential_amenities.append('Jogging Track')
                        elif 'sports' in combined:
                            potential_amenities.append('Sports Facility')
                        elif 'community' in combined or 'hall' in combined:
                            potential_amenities.append('Community Hall')
                        current_amenity = []
                    elif len(current_amenity) > 2:  # Avoid overly long concatenations
                        current_amenity = [word]
                if potential_amenities:
                    amenities.extend(potential_amenities)
            # Remove duplicates while preserving order
            amenities = list(dict.fromkeys(amenities))
            if amenities:
                break
        except Exception:
            continue
    # Fallback: If no amenities found, try regex on body text
    if not amenities:
        body_text = soup.get_text(separator=' ').lower()
        amenity_patterns = r"(gym|pool|swimming|parking|garden|lift|elevator|clubhouse|security|play\s*area|power\s*backup|terrace|jogging\s*track|sports\s*facility|community\s*hall)"
        for match in re.finditer(amenity_patterns, body_text, re.IGNORECASE):
            amenity = match.group(0).title()
            if 'Pool' in amenity or 'Swimming' in amenity:
                amenity = 'Swimming Pool'
            elif 'Lift' in amenity or 'Elevator' in amenity:
                amenity = 'Lift'
            elif 'Play' in amenity:
                amenity = 'Play Area'
            elif 'Power' in amenity or 'Backup' in amenity:
                amenity = 'Power Backup'
            elif 'Jogging' in amenity or 'Track' in amenity:
                amenity = 'Jogging Track'
            elif 'Sports' in amenity:
                amenity = 'Sports Facility'
            elif 'Community' in amenity or 'Hall' in amenity:
                amenity = 'Community Hall'
            if amenity not in amenities:
                amenities.append(amenity)
    data['amenities'] = amenities if amenities else None

    landmarks = []
    landmarks_selectors = {
        "99acres.com": [
            'div#localitySection ul li',
            'div[class*="landmark"] li',
            'div[class*="nearby"] li',
            'div.factTableLocality',
            'div[id*="landmarks"] ul li'
        ],
        "magicbricks.com": [
            'div.mb-ldp__dtls__locality li',
            'div.mb-ldp__nearby--list li',
            'div[class*="landmark"] li',
            'div[class*="nearby"] li',
            'div[id*="locality"] ul li'
        ],
        "housing.com": [
            'div.css-1v2k6a4-nearby li',
            'div[class*="landmark"] li',
            'ul[class*="nearby-list"] li',
            'div[id*="landmarks"] li'
        ],
        "default": [
            '[class*="landmark"] li',
            '[class*="nearby"] li',
            '[data-landmark]',
            'li:contains("metro")',
            'li:contains("school")',
            'li:contains("hospital")',
            'div:contains("nearby") li'
        ]
    }
    selectors = landmarks_selectors.get(domain, landmarks_selectors["default"])
    for selector in selectors:
        try:
            landmark_elements = soup.select(selector)
            for element in landmark_elements:
                landmark_text = element.get_text(strip=True).lower()
                if any(keyword in landmark_text for keyword in ['metro', 'school', 'hospital', 'mall', 'airport', 'park', 'market', 'station']):
                    landmarks.append(landmark_text.title())
            landmarks = list(dict.fromkeys(landmarks))
            if landmarks:
                break
        except Exception:
            continue
    if not landmarks:
        body_text = soup.get_text(separator=' ').lower()
        landmark_patterns = r"(near\s*(?:metro|school|hospital|mall|airport|park|market)\s*[^\.,;]{0,50})"
        for match in re.finditer(landmark_patterns, body_text, re.IGNORECASE):
            landmarks.append(match.group(0).strip().title())
        landmarks = list(dict.fromkeys(landmarks))
    data['landmarks'] = landmarks if landmarks else None

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

    body_text = soup.get_text(separator=' ').lower()
    bhk_match = re.search(r'(\d+)\s*(?:BHK|bhk|Bedroom|bedroom)', body_text, re.IGNORECASE)
    data['bedrooms'] = int(bhk_match.group(1)) if bhk_match else None
    bath_match = re.search(r'(\d+)\s*(?:Bath|bath|Bathroom|bathroom)', body_text, re.IGNORECASE)
    data['bathrooms'] = int(bath_match.group(1)) if bath_match else None

    prop_type_match = re.search(
        r'(apartment|flat|villa|house|plot|land|commercial)',
        body_text,
        re.IGNORECASE
    )
    data['property_type'] = prop_type_match.group(1).title() if prop_type_match else "Residential"

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

def perform_manual_search(page: Page, query: str) -> List[dict]:
    """
    Perform manual search on property websites when Tavily is not available.
    Now includes scraping of titles and descriptions from search results.
    """
    results: List[dict] = []
    search_configs = [
        {
            "site": "99acres.com",
            "url": f"https://www.99acres.com/search/property/buy/residential-all/{query.replace(' ', '-')}",
            "listing_selector": "div.srpWrap",
            "title_selector": "div._srpttl.srpttl.fwn.wdthFix480.lf",
            "desc_selector": "div.lf.f13.hm10.mb5",
            "link_selector": "a[class*='body_med']"
        },
        {
            "site": "magicbricks.com",
            "url": (
                f"https://www.magicbricks.com/property-for-sale/residential-real-estate?"
                f"proptype=Multistorey-Apartment,Builder-Floor-Apartment,Penthouse,Studio-Apartment"
                f"&cityName={query.split()[-1]}"
            ),
            "listing_selector": "div.mb-srp__card",
            "title_selector": "h2.mb-srp__card--title",
            "desc_selector": "div.mb-srp__card__summary__list",
            "link_selector": "h2.mb-srp__card--title a[href*='property-details']"
        },
        {
            "site": "housing.com",
            "url": f"https://housing.com/in/buy/{query.replace(' ', '-')}",
            "listing_selector": "article.listing-card",
            "title_selector": "h2.listing-card__title",
            "desc_selector": "div.listing-card__desc",
            "link_selector": "a[class*='listing-card']"
        }
    ]

    for config in search_configs:
        try:
            print(f"  Searching on {config['site']}…")
            page.goto(config["url"], wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)

            # Scroll to load more listings
            for _ in range(2):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)

            # Wait for listings to load
            page.wait_for_selector(config["listing_selector"], timeout=10000)

            # Extract listings
            listings = page.query_selector_all(config["listing_selector"])[:3]
            for listing in listings:
                title = ""
                desc = ""
                href = ""
                try:
                    title = listing.query_selector(config["title_selector"]).inner_text().strip()
                except Exception as e:
                    print(f"    Failed to extract title on {config['site']}: {e}")
                try:
                    desc = listing.query_selector(config["desc_selector"]).inner_text().strip()
                except Exception as e:
                    print(f"    Failed to extract description on {config['site']}: {e}")
                try:
                    link = listing.query_selector(config["link_selector"])
                    href = link.get_attribute("href")
                    if href and not href.startswith("http"):
                        href = f"https://{config['site']}{href}"
                except Exception as e:
                    print(f"    Failed to extract link on {config['site']}: {e}")
                if href:
                    results.append({"url": href, "title": title, "snippet": desc})
        except Exception as e:
            print(f"    Failed on {config['site']}: {e}")

    return results

def search_properties(queries: List[str]) -> List[SearchResults]:
    """
    Main search function, including amenities and landmarks
    """
    all_results: List[SearchResults] = []

    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    if not TAVILY_API_KEY:
        print("⚠️  WARNING: TAVILY_API_KEY not set. Will use limited search.")
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--window-size=1920,1080',
                '--start-maximized'
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

        for query in queries:
            print(f"\n{'='*60}")
            print(f"🏠 Searching for: '{query}'")
            print(f"{'='*60}")

            property_urls: List[dict] = []

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
                        max_results=3
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
                        property_urls = [
                            p for p in property_urls
                            if "99acres.com" in p["url"].lower()
                            or "magicbricks.com" in p["url"].lower()
                        ]
                        print(f"  ✓ Kept {len(property_urls)} URLs from 99acres/magicbricks")
                except Exception as e:
                    print(f"  ✗ Tavily search failed: {e}")

            if not property_urls:
                print("🔍 Performing manual search...")
                manual_urls = perform_manual_search(page, query)
                property_urls.extend(manual_urls)

            per_query_results: List[PerQueryResult] = []
            for idx, prop_info in enumerate(property_urls):
                url = prop_info["url"] if isinstance(prop_info, dict) else prop_info
                print(f"\n📍 Property {idx+1}: {url}")

                try:
                    random_delay(2, 4)
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(random.randint(2000, 4000))
                    simulate_human_behavior(page)

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

                    html_content = page.content()
                    parsed_data = _parse_property_page(html_content, url, page)

                    # Use pre-scraped title and description if available
                    parsed_data["title"] = prop_info.get("title") or parsed_data.get("title", "Property Details")
                    raw_desc = prop_info.get("snippet") or parsed_data.get("raw_description", "")
                    parsed_data["raw_description"] = raw_desc

                    location = parsed_data.get("location", "Unknown")
                    fields = _extract_fields_from_snippet(raw_desc, location)
                    pretty_description = format_property_description(fields)

                    print(f"  ✓ Extracted successfully")
                    print(f"    Price: {parsed_data.get('price', 'Not found')}")
                    print(f"    Location: {parsed_data.get('location', 'Not found')}")
                    print(f"    Amenities: {parsed_data.get('amenities', 'None')}")
                    print(f"    Landmarks: {parsed_data.get('landmarks', 'None')}")
                    print(f"    Description: {pretty_description}")

                    per_query_results.append(
                        PerQueryResult(
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
                            formatted_description=pretty_description,
                            amenities=parsed_data.get("amenities"),
                            landmarks=parsed_data.get("landmarks")
                        )
                    )

                except Exception as e:
                    print(f"  ✗ Error: {e}")
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
                                amenities=fallback_data.get("amenities"),
                                landmarks=fallback_data.get("landmarks"),
                                formatted_description=None
                            )
                        )

            all_results.append(SearchResults(query=query, results=per_query_results))

        context.close()
        browser.close()

    return all_results

def search(queries: List[str]) -> List[SearchResults]:
    """
    Expose a top-level `search(...)` for other modules
    """
    return search_properties(queries)

# --- Main execution ---
if __name__ == "__main__":
    queries = [
        "2 bhk flat for sale in whitefield, bangalore"
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
                    print(f"   🛠️ Amenities: {', '.join(prop.amenities) if prop.amenities else 'None'}")
                    print(f"   📍 Landmarks: {', '.join(prop.landmarks) if prop.landmarks else 'None'}")
                    print(f"   📝 Description: {prop.formatted_description}")
            else:
                print("❌ No properties found for this query.")
    else:
        print("❌ No search results were returned.")