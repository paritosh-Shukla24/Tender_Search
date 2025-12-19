#!/usr/bin/env python3
"""
TED API Tender Fetcher - FIXED Multi-Lot Detection
Version: 7.0 - identifier-lot ARRAY Based Multi-Lot Detection
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict
import time

# =============================================================================
# CONFIGURATION
# =============================================================================

TED_API_URL = "https://api.ted.europa.eu/v3/notices/search"
REQUEST_TIMEOUT = 30

# COMPREHENSIVE FIELD SET - Based on TED API Documentation
TENDER_FIELDS = [
    # === CORE IDENTIFICATION (8 fields) ===
    "notice-identifier",           # UUID - Primary key
    "publication-number",          # TED reference (NNNNNN-YYYY)
    "notice-type",                 # cn-standard, pin-only, can-standard
    "form-type",                   # Form category
    "procedure-identifier",        # Links related notices
    "notice-title",                # Main title (multilingual)
    "title-lot",                   # Lot-specific title
    "description-lot",             # Lot description
    "description-proc",            # Procedure description
    "description-part",            # Part description  
    "additional-information-lot",  # Additional lot information
    "additional-info-proc",        # Additional procedure info
    "contract-conditions-description-lot",  # Contract performance details
    "strategic-procurement-description-lot",  # Strategic procurement details
    "procedure-features",          # Main features of procedure
    
    # === DATES & DEADLINES (6 fields) ===
    "publication-date",            # When published
    "deadline-receipt-tender-date-lot",      # Tender submission deadline
    "deadline-receipt-expressions-date-lot", # EOI deadline
    "deadline-receipt-request-date-lot",     # Request to participate
    "dispatch-date",               # Sent to TED
    "deadline-date-lot",           # Generic deadline
    
    # === CLASSIFICATION (4 fields) ===
    "classification-cpv",          # CPV code (e.g., 72000000)
    "main-classification-lot",     # Primary CPV indicator
    "contract-nature",             # services/supplies/works
    "procedure-type",              # open/restricted/negotiated
    
    # === BUYER INFORMATION (10 fields) ===
    "organisation-name-buyer",     # Official buyer name
    "buyer-name",                  # Simple buyer name
    "buyer-country",               # Country code
    "buyer-city",                  # City
    "buyer-email",                 # Contact email
    "buyer-profile",               # Buyer profile URL
    "buyer-legal-type",            # Legal classification
    "organisation-city-buyer",     # Org city
    "organisation-street-buyer",   # Org street
    "buyer-touchpoint-name",       # Contact person
    
    # === FINANCIAL (3 fields) ===
    "estimated-value-lot",         # Value as number
    "estimated-value-cur-lot",     # Value with currency {amount, currency}
    "tender-value-cur",            # Actual awarded value
    
    # === LOCATION (4 fields) ===
    "place-of-performance-country-lot",  # Where work happens
    "place-of-performance-city-lot",     # City location
    "place-of-performance-subdiv-lot",   # NUTS code
    "place-of-performance",              # Description
    
    # === LOT STRUCTURE (4 fields) - CRITICAL FOR MULTI-LOT ===
    "identifier-lot",              # LOT-0001, LOT-0002, etc.
    "internal-identifier-lot",     # Internal reference
    "title-lot",                   # Lot title
    "description-lot",             # Lot description
    
    # === STRATEGIC FLAGS (6 fields) ===
    "sme-lot",                     # SME suitable
    "framework-agreement-lot",     # Framework
    "dps-usage-lot",              # Dynamic Purchasing System
    "reserved-procurement-lot",    # Reserved tender
    "innovative-acquisition-lot",  # Innovation
    "social-objective-lot",       # Social goals
    
    # === URLs & DOCUMENTS (3 fields) ===
    "document-url-lot",            # Tender documents
    "submission-url-lot",          # Bid submission portal
    "buyer-profile",               # Buyer information
    
    # === AWARD CRITERIA (4 fields) ===
    "award-criterion-type-lot",    # QUALITY/COST/PRICE
    "award-criterion-name-lot",    # Criterion name
    "award-criterion-description-lot",  # Details
    "award-criterion-number-weight-lot", # Weighting
    
    # === REQUIREMENTS & BARRIERS (12 fields) ===
    "security-clearance-lot",      # Security clearance required
    "guarantee-required-lot",      # Financial guarantee needed
    "guarantee-required-description-lot",  # Guarantee details
    "subcontracting-obligation-lot",  # Must subcontract
    "subcontracting-allowed-lot",  # Subcontracting allowed
    "electronic-submission-lot",   # E-submission required
    "submission-language",         # Accepted languages
    "electronic-auction-lot",      # E-auction
    "electronic-invoicing-lot",    # E-invoicing required
    "variant-allowed-lot",         # Variants allowed
    "multiple-tender-lot",         # Multiple bids allowed
    "accessibility-lot",           # Accessibility requirements
    
    # === FRAMEWORK & DPS DETAILS (6 fields) ===
    "framework-duration-justification-lot",  # Why this duration
    "framework-maximum-participants-number-lot",  # Max participants
    "framework-estimated-value",   # Total framework value
    "dps-termination-lot",        # DPS can be terminated
    "following-contract-lot",     # Follow-on contracts
    "recurrence-lot",             # Will this repeat
    
    # === PROCEDURE DETAILS (8 fields) ===
    "procedure-accelerated",       # Accelerated procedure
    "minimum-candidate-lot",       # Min candidates for shortlist
    "maximum-candidates-lot",      # Max candidates
    "lots-max-allowed-proc",      # Max lots per bidder
    "lots-max-awarded-proc",      # Max lots can win
    "lots-all-required-proc",     # Must bid all lots
    "procedure-justification",    # Why this procedure
    "gpa-lot",                    # GPA covered
    
    # === CONTRACT DURATION (6 fields) ===
    "contract-duration-period-lot",      # Duration in months/days
    "contract-duration-start-date-lot",  # Start date
    "contract-duration-end-date-lot",    # End date
    "renewal-maximum-lot",         # Max renewals
    "renewal-description-lot",     # Renewal terms
    "term-performance-lot",       # Performance terms
    
    # === ADDITIONAL CLASSIFICATION ===
    "additional-classification-lot",  # Extra CPV codes
    
    # === ADDITIONAL INFO ===
    "additional-information-lot",  # Extra information
    
    # === GROUP OF LOTS (for multi-lot detection) ===
    "identifier-glo",             # Group Lot ID
]

CURRENCY_RATES = {
    "EUR": 1.0,
    "DKK": 0.134,
    "NOK": 0.084,
    "SEK": 0.089,
    "USD": 0.95,
    "GBP": 1.17,
    "PLN": 0.23,
    "CZK": 0.040,
    "HUF": 0.0025,
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_value(data: Any, default: Any = None) -> Any:
    """Extract value from TED API multilingual data structure."""
    if data is None:
        return default
    
    # Handle multilingual dictionary
    if isinstance(data, dict):
        # Priority language order
        for lang in ['eng', 'dan', 'deu', 'swe', 'nor', 'fra', 'spa', 'ita']:
            if lang in data:
                value = data[lang]
                if isinstance(value, list) and value:
                    return value[0]
                return value if value else default
        
        # Fallback to first available value
        if data:
            first_value = next(iter(data.values()), default)
            if isinstance(first_value, list) and first_value:
                return first_value[0]
            return first_value if first_value else default
    
    # Handle list
    if isinstance(data, list) and data:
        return data[0]
    
    return data if data else default


def parse_date(date_str: Any) -> Optional[str]:
    """Parse date to ISO format."""
    if date_str:
        try:
            date_str = get_value(date_str)
            if isinstance(date_str, str):
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return dt.isoformat()
        except Exception as e:
            pass
    return None


def calculate_days_until(deadline_iso: Optional[str]) -> Optional[int]:
    """Calculate days until deadline."""
    if deadline_iso:
        try:
            deadline = datetime.fromisoformat(deadline_iso)
            now = datetime.now(deadline.tzinfo or None)
            return (deadline - now).days
        except:
            pass
    return None


def parse_boolean(value: Any) -> bool:
    """Parse boolean value from TED API."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value = value.lower()
        return value not in ['false', 'none', '', 'no', 'not-allowed']
    return bool(value)


# =============================================================================
# TED API
# =============================================================================

def extract_lot_count_from_text(notice: Dict) -> Optional[int]:
    """
    Try to extract lot count from description/title text.
    
    Common patterns:
    - "divided into 5 lots"
    - "de fem kategorier" (Danish: the five categories)  
    - "LOT-0001, LOT-0002, LOT-0003..." in text
    - "Lot 1:..., Lot 2:..., Lot 3:..."
    """
    import re
    
    # Get all text fields
    texts = []
    for field in ["description-lot", "description-proc", "procedure-features", "title-lot", "notice-title"]:
        value = notice.get(field)
        if value:
            text = get_value(value)
            if text:
                texts.append(text.lower())
    
    full_text = " ".join(texts)
    
    # Pattern 1: "divided into X lots"  / "opdelt i X delaftaler"
    patterns = [
        r'divided into (\d+) lots',
        r'(\d+) separate lots',
        r'opdelt i (\d+) delaftaler',
        r'(\d+) delaftaler',
        r'de (\w+) kategorier',  # Danish: "the X categories"
    ]
    
    # Danish number words
    danish_numbers = {
        'to': 2, 'tre': 3, 'fire': 4, 'fem': 5, 'seks': 6, 
        'syv': 7, 'otte': 8, 'ni': 9, 'ti': 10
    }
    
    for pattern in patterns:
        match = re.search(pattern, full_text)
        if match:
            num_str = match.group(1)
            # Try numeric
            if num_str.isdigit():
                return int(num_str)
            # Try Danish word
            if num_str in danish_numbers:
                return danish_numbers[num_str]
    
    # Pattern 2: Count "LOT-" mentions
    lot_mentions = re.findall(r'LOT-(\d+)', full_text.upper())
    if len(lot_mentions) > 1:
        # Get highest lot number
        try:
            return max(int(n) for n in lot_mentions if int(n) > 0)
        except:
            pass
    
    return None


def fetch_notice_details(notice_id: str) -> Optional[Dict]:
    """
    Fetch full notice details including ALL lots.
    
    The TED API has a separate endpoint for fetching individual notices
    which returns complete data for all lots.
    """
    url = f"https://api.ted.europa.eu/v3/notices/{notice_id}"
    
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"Accept": "application/json"}
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[!] Failed to fetch notice {notice_id[:8]}...: {e}")
        return None


def fetch_tenders_page(query: str, page: int = 1) -> Dict[str, Any]:
    """Fetch one page from TED API."""
    payload = {
        "query": query,
        "fields": TENDER_FIELDS,
        "page": page,
        "limit": 100,
        "scope": "ACTIVE",
        "paginationMode": "PAGE_NUMBER",
        # Remove onlyLatestVersions to potentially get all lots
        # "onlyLatestVersions": True,
    }
    
    try:
        response = requests.post(
            TED_API_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[X] API Error: {e}")
        if hasattr(e, 'response') and e.response:
            error_text = e.response.text[:1000]
            print(f"   Response: {error_text}")
        return {}


def fetch_all_tenders(countries: List[str], days: int) -> List[Dict]:
    """Fetch ALL tenders with proper pagination."""
    print(f"\n[*] Fetching tenders from TED API...")
    print(f"   Countries: {', '.join(countries)}")
    print(f"   Published in last {days} days")
    print(f"   Fields requested: {len(TENDER_FIELDS)}")
    print("-" * 80)
    
    # Build query
    countries_str = ", ".join([f'"{c}"' for c in countries])
    query = (
        f"notice-type IN (cn-standard, cn-social, pin-cfc-standard, pin-cfc-social) "
        f"AND buyer-country IN ({countries_str}) "
        f"AND publication-date = (today(-{days}) <> today(0))"
    )
    
    print(f"   Query: {query}")
    print("-" * 80)
    
    all_notices = []
    page = 1
    total = None
    max_pages = 50
    
    while page <= max_pages:
        print(f"📄 Page {page}...", end=" ", flush=True)
        
        result = fetch_tenders_page(query, page)
        
        if not result:
            print("[X] Failed")
            break
        
        notices = result.get("notices", [])
        hits = result.get("hits", 0)
        
        if page == 1:
            total = hits
            print(f"[+] Total: {total} tender lots from API")
        else:
            print(f"[+] Got {len(notices)}")
        
        if not notices:
            break
        
        all_notices.extend(notices)
        
        if len(all_notices) >= total or len(notices) < 100:
            print(f"\n[+] Complete: Fetched {len(all_notices)} lot records")
            break
        
        page += 1
        time.sleep(0.5)  # Rate limiting
    
    return all_notices


# =============================================================================
# PARSING
# =============================================================================

def parse_tender(notice: Dict, lot_number: int = 1, total_lots: int = 1, lot_identifiers: List[str] = None) -> Dict:
    """Parse tender with comprehensive field handling."""
    
    # === CORE IDENTIFICATION ===
    notice_id = notice.get("notice-identifier")
    pub_number = get_value(notice.get("publication-number"))
    notice_type = get_value(notice.get("notice-type"))
    title = get_value(notice.get("notice-title")) or get_value(notice.get("title-lot")) or "No title"
    
    # === COMPREHENSIVE DESCRIPTION - Combine multiple sources ===
    description_parts = []
    
    # 1. Main lot description
    lot_desc = get_value(notice.get("description-lot"))
    if lot_desc:
        description_parts.append(lot_desc)
    
    # 2. Procedure description (often contains detailed scope)
    proc_desc = get_value(notice.get("description-proc"))
    if proc_desc and proc_desc != lot_desc:
        description_parts.append(proc_desc)
    
    # 3. Part description
    part_desc = get_value(notice.get("description-part"))
    if part_desc and part_desc not in [lot_desc, proc_desc]:
        description_parts.append(part_desc)
    
    # 4. Additional information
    additional_info = get_value(notice.get("additional-information-lot"))
    if additional_info:
        description_parts.append(f"Additional Info: {additional_info}")
    
    # 5. Additional procedure info
    additional_proc = get_value(notice.get("additional-info-proc"))
    if additional_proc:
        description_parts.append(f"Procedure Details: {additional_proc}")
    
    # 6. Contract conditions description
    contract_cond = get_value(notice.get("contract-conditions-description-lot"))
    if contract_cond:
        description_parts.append(f"Contract Conditions: {contract_cond}")
    
    # 7. Strategic procurement details
    strategic_desc = get_value(notice.get("strategic-procurement-description-lot"))
    if strategic_desc:
        description_parts.append(f"Strategic Procurement: {strategic_desc}")
    
    # 8. Procedure features (main characteristics)
    proc_features = get_value(notice.get("procedure-features"))
    if proc_features:
        description_parts.append(f"Procedure Features: {proc_features}")
    
    # Combine all parts with separator
    description = " || ".join(description_parts) if description_parts else "No description available"
    
    # === DATES ===
    pub_date = parse_date(notice.get("publication-date"))
    deadline_tender = parse_date(notice.get("deadline-receipt-tender-date-lot"))
    deadline_request = parse_date(notice.get("deadline-receipt-request-date-lot"))
    deadline_eoi = parse_date(notice.get("deadline-receipt-expressions-date-lot"))
    
    main_deadline = deadline_tender or deadline_request or deadline_eoi
    days_until = calculate_days_until(main_deadline)
    
    # Urgency calculation
    if days_until is not None:
        if days_until < 0:
            urgency = "EXPIRED"
        elif days_until <= 7:
            urgency = "CRITICAL"
        elif days_until <= 14:
            urgency = "MODERATE"
        else:
            urgency = "NORMAL"
    else:
        urgency = "UNKNOWN"
    
    # === BUYER ===
    buyer_name = (get_value(notice.get("organisation-name-buyer")) or 
                  get_value(notice.get("buyer-name")) or 
                  "Unknown Buyer")
    buyer_country = get_value(notice.get("buyer-country"))
    buyer_city = get_value(notice.get("buyer-city")) or get_value(notice.get("organisation-city-buyer"))
    buyer_email = get_value(notice.get("buyer-email"))
    buyer_profile = get_value(notice.get("buyer-profile"))
    buyer_legal = get_value(notice.get("buyer-legal-type"))
    
    # Regional cluster
    clusters = {
        'NORDIC': ['DNK', 'SWE', 'NOR', 'FIN', 'ISL'],
        'BALTIC': ['EST', 'LVA', 'LTU'],
        'WESTERN': ['DEU', 'FRA', 'AUT', 'BEL', 'NLD', 'LUX'],
        'SOUTHERN': ['ITA', 'ESP', 'PRT', 'GRC', 'MLT', 'CYP'],
        'EASTERN': ['POL', 'CZE', 'HUN', 'SVK', 'SVN', 'ROU', 'BGR'],
        'BRITISH': ['GBR', 'IRL'],
    }
    
    cluster = None
    if buyer_country:
        for name, countries in clusters.items():
            if buyer_country in countries:
                cluster = name
                break
    
    # === FINANCIAL ===
    value_eur = None
    value_original = None
    currency = None
    
    # Try estimated-value-cur-lot first
    value_cur_data = notice.get("estimated-value-cur-lot")
    if value_cur_data:
        try:
            if isinstance(value_cur_data, list) and value_cur_data:
                value_cur_data = value_cur_data[0]
            
            if isinstance(value_cur_data, dict):
                amount = value_cur_data.get("amount")
                currency = value_cur_data.get("currency", "EUR")
                if amount:
                    value_original = float(amount)
                    rate = CURRENCY_RATES.get(currency.upper(), 1.0)
                    value_eur = value_original * rate
        except:
            pass
    
    # Fallback to estimated-value-lot
    if value_eur is None:
        value_lot_data = notice.get("estimated-value-lot")
        if value_lot_data:
            try:
                if isinstance(value_lot_data, list) and value_lot_data:
                    value_lot_data = value_lot_data[0]
                
                if isinstance(value_lot_data, dict):
                    amount = value_lot_data.get("amount") or value_lot_data.get("value")
                    currency = value_lot_data.get("currency", "EUR")
                    if amount:
                        value_original = float(amount)
                        rate = CURRENCY_RATES.get(currency.upper(), 1.0)
                        value_eur = value_original * rate
                elif isinstance(value_lot_data, (int, float)):
                    value_eur = float(value_lot_data)
                    value_original = value_eur
                    currency = "EUR"
            except:
                pass
    
    # Value category
    category = None
    if value_eur:
        if value_eur < 50000:
            category = "MICRO"
        elif value_eur < 500000:
            category = "SMALL"
        elif value_eur < 5000000:
            category = "MEDIUM"
        elif value_eur < 50000000:
            category = "LARGE"
        else:
            category = "MEGA"
    
    # === CLASSIFICATION ===
    cpv_data = notice.get("classification-cpv", [])
    if not isinstance(cpv_data, list):
        cpv_data = [cpv_data] if cpv_data else []
    
    cpv_code = cpv_data[0] if cpv_data else None
    cpv_codes_additional = cpv_data[1:] if len(cpv_data) > 1 else []
    
    additional_cpv_raw = notice.get("additional-classification-lot", [])
    if additional_cpv_raw:
        if not isinstance(additional_cpv_raw, list):
            additional_cpv_raw = [additional_cpv_raw]
        cpv_codes_additional.extend(additional_cpv_raw)
    
    cpv_codes_additional = list(set([cpv for cpv in cpv_codes_additional if cpv]))
    
    contract_nature = get_value(notice.get("contract-nature"))
    procedure_type = get_value(notice.get("procedure-type"))
    
    # === LOCATION ===
    perf_country = get_value(notice.get("place-of-performance-country-lot"))
    perf_city = get_value(notice.get("place-of-performance-city-lot"))
    perf_desc = get_value(notice.get("place-of-performance"))
    
    # === LOT STRUCTURE - FIXED MULTI-LOT DETECTION ===
    lot_id = get_value(notice.get("identifier-lot")) or "LOT-0000"
    
    # Multi-lot detection based on LOT-XXXX pattern
    # LOT-0000 = single contract (no lots)
    # LOT-0001, LOT-0002, etc. = multiple lots
    is_multi_lot = False
    if lot_identifiers:
        # Check if we have multiple different LOT-XXXX identifiers
        unique_lots = set([lid for lid in lot_identifiers if lid and lid != "LOT-0000"])
        is_multi_lot = len(unique_lots) > 1 or (len(unique_lots) == 1 and total_lots > 1)
    else:
        # Fallback: check if lot_id suggests multi-lot
        is_multi_lot = (lot_id != "LOT-0000" and total_lots > 1)
    
    # === STRATEGIC FLAGS ===
    is_sme = parse_boolean(get_value(notice.get("sme-lot")))
    is_framework = parse_boolean(get_value(notice.get("framework-agreement-lot")))
    is_dps = parse_boolean(get_value(notice.get("dps-usage-lot")))
    is_innovative = parse_boolean(get_value(notice.get("innovative-acquisition-lot")))
    is_social = parse_boolean(get_value(notice.get("social-objective-lot")))
    is_reserved = parse_boolean(get_value(notice.get("reserved-procurement-lot")))
    
    # === REQUIREMENTS ===
    security_clearance = parse_boolean(get_value(notice.get("security-clearance-lot")))
    guarantee_required = parse_boolean(get_value(notice.get("guarantee-required-lot")))
    guarantee_desc = get_value(notice.get("guarantee-required-description-lot"))
    electronic_submission = get_value(notice.get("electronic-submission-lot"))
    subcontracting_allowed = parse_boolean(get_value(notice.get("subcontracting-allowed-lot")))
    subcontracting_obligatory = parse_boolean(get_value(notice.get("subcontracting-obligation-lot")))
    
    # Complexity calculation
    complexity = 0
    if security_clearance:
        complexity += 20
    if guarantee_required:
        complexity += 10
    if procedure_type in ["restricted", "comp-dial", "negotiated"]:
        complexity += 20
    if subcontracting_obligatory:
        complexity += 15
    
    complexity_level = "COMPLEX" if complexity >= 30 else "MODERATE" if complexity >= 15 else "SIMPLE"
    
    # === URLS ===
    submission_url = get_value(notice.get("submission-url-lot"))
    document_url = get_value(notice.get("document-url-lot"))
    ted_url = f"https://ted.europa.eu/en/notice/-/detail/{pub_number}" if pub_number else None
    ted_pdf = f"https://ted.europa.eu/en/notice/{pub_number}/pdf" if pub_number else None
    
    # === AWARD CRITERIA ===
    award_type = get_value(notice.get("award-criterion-type-lot"))
    award_name = get_value(notice.get("award-criterion-name-lot"))
    award_desc = get_value(notice.get("award-criterion-description-lot"))
    
    # === CONTRACT DURATION ===
    duration = get_value(notice.get("contract-duration-period-lot"))
    start_date = parse_date(notice.get("contract-duration-start-date-lot"))
    end_date = parse_date(notice.get("contract-duration-end-date-lot"))
    
    # === PROCEDURE ===
    is_accelerated = parse_boolean(get_value(notice.get("procedure-accelerated")))
    variant_allowed = parse_boolean(get_value(notice.get("variant-allowed-lot")))
    electronic_auction = parse_boolean(get_value(notice.get("electronic-auction-lot")))
    is_recurrent = parse_boolean(get_value(notice.get("recurrence-lot")))
    min_candidates = get_value(notice.get("minimum-candidate-lot"))
    max_candidates = get_value(notice.get("maximum-candidates-lot"))
    
    # === GPA ===
    gpa_covered = parse_boolean(get_value(notice.get("gpa-lot")))
    
    # === ADDITIONAL INFO ===
    additional_info = get_value(notice.get("additional-information-lot"))
    
    # Cross-border detection
    is_cross_border = False
    if perf_country and buyer_country and perf_country != buyer_country:
        is_cross_border = True
    
    return {
        "notice_identifier": notice_id,
        "publication_number": pub_number,
        "notice_type": notice_type,
        "title": title,
        "description": description,
        
        "dates": {
            "publication_date": pub_date,
            "deadline_tender": deadline_tender,
            "deadline_request": deadline_request,
            "deadline_eoi": deadline_eoi,
            "deadline_main": main_deadline,
            "days_until_deadline": days_until,
            "urgency_level": urgency,
            "is_expired": urgency == "EXPIRED",
            "is_expiring_soon": urgency in ["CRITICAL", "MODERATE"],
        },
        
        "buyer": {
            "name": buyer_name,
            "country": buyer_country,
            "city": buyer_city,
            "email": buyer_email,
            "profile_url": buyer_profile,
            "legal_type": buyer_legal,
        },
        
        "financial": {
            "value_original": value_original,
            "currency": currency,
            "value_eur": value_eur,
            "value_category": category,
        },
        
        "classification": {
            "cpv_code": cpv_code,
            "cpv_codes_additional": cpv_codes_additional,
            "contract_nature": contract_nature,
            "procedure_type": procedure_type,
        },
        
        "location": {
            "performance_country": perf_country,
            "performance_city": perf_city,
            "performance_description": perf_desc,
            "is_cross_border": is_cross_border,
            "regional_cluster": cluster,
        },
        
        "strategic": {
            "is_sme": is_sme,
            "is_sme_accessible": is_sme,
            "is_framework": is_framework,
            "is_dps": is_dps,
            "is_innovative": is_innovative,
            "is_social": is_social,
            "is_reserved": is_reserved,
            "is_multi_lot": is_multi_lot,
            "lot_identifier": lot_id,
            "lot_number": lot_number,
            "total_lots": total_lots,
        },
        
        "requirements": {
            "security_clearance": security_clearance,
            "guarantee_required": guarantee_required,
            "guarantee_description": guarantee_desc,
            "electronic_submission": electronic_submission,
            "subcontracting_allowed": subcontracting_allowed,
            "subcontracting_obligatory": subcontracting_obligatory,
            "complexity_score": complexity,
            "complexity_level": complexity_level,
        },
        
        "award_criteria": {
            "type": award_type,
            "name": award_name,
            "description": award_desc,
        },
        
        "contract": {
            "duration": duration,
            "start_date": start_date,
            "end_date": end_date,
            "renewal_max": get_value(notice.get("renewal-maximum-lot")),
            "renewal_description": get_value(notice.get("renewal-description-lot")),
        },
        
        "procedure": {
            "is_accelerated": is_accelerated,
            "variant_allowed": variant_allowed,
            "electronic_auction": electronic_auction,
            "is_recurrent": is_recurrent,
            "minimum_candidates": min_candidates,
            "maximum_candidates": max_candidates,
        },
        
        "urls": {
            "submission_url": submission_url,
            "document_url": document_url,
            "ted_notice_url": ted_url,
            "ted_pdf_url": ted_pdf,
        },
        
        "additional": {
            "gpa_covered": gpa_covered,
            "additional_info": additional_info,
        },
        
        "metadata": {
            "fetched_at": datetime.now().isoformat(),
            "api_version": "v3",
            "fields_count": len(TENDER_FIELDS),
        }
    }


# =============================================================================
# MULTI-LOT DETECTION & PROCESSING - FIXED VERSION
# =============================================================================

def detect_and_process_multilot(notices: List[Dict]) -> List[Dict]:
    """
    FIXED: Detect multi-lot tenders using identifier-lot array.
    
    Multi-lot detection logic:
    - identifier-lot is an ARRAY of LOT identifiers per notice
    - If identifier-lot has multiple items (LOT-0001, LOT-0002, etc.) = multi-lot
    - Count the unique LOT-XXXX values (excluding LOT-0000)
    - LOT-0000 = Single contract (no subdivisions)
    - LOT-0001, LOT-0002, etc. = Multi-lot tender
    
    Example from API:
    "identifier-lot": ["LOT-0001", "LOT-0002", "LOT-0003", "LOT-0004"] = 4 lots
    "identifier-lot": ["LOT-0000"] = 1 lot (single contract)
    """
    print(f"\n🔄 Processing multi-lot tenders (IDENTIFIER-LOT ARRAY DETECTION)...")
    print(f"   Total lot records from API: {len(notices)}")
    
    # Group by notice identifier
    notice_groups = defaultdict(list)
    for notice in notices:
        notice_id = notice.get("notice-identifier")
        
        # Get identifier-lot - it's an ARRAY
        lot_ids_raw = notice.get("identifier-lot")
        
        # Ensure it's a list
        if lot_ids_raw:
            if not isinstance(lot_ids_raw, list):
                lot_ids_raw = [lot_ids_raw]
        else:
            lot_ids_raw = []
        
        if notice_id:
            notice_groups[notice_id].append({
                "notice": notice,
                "lot_ids": lot_ids_raw  # Store the FULL array
            })
    
    print(f"   Unique tenders (by notice_identifier): {len(notice_groups)}")
    
    # Analyze multi-lot patterns
    single_lot_count = 0
    multi_lot_count = 0
    lot_pattern_stats = defaultdict(int)
    
    parsed_tenders = []
    
    for notice_id, lot_data in notice_groups.items():
        # Get the first notice's identifier-lot array
        first_notice = lot_data[0]["notice"]
        lot_ids_raw = first_notice.get("identifier-lot", [])
        
        # Ensure it's a list
        if not isinstance(lot_ids_raw, list):
            lot_ids_raw = [lot_ids_raw] if lot_ids_raw else []
        
        # Clean up lot identifiers - remove None, empty strings, and LOT-0000
        lot_identifiers = [lid for lid in lot_ids_raw if lid and lid != "LOT-0000"]
        
        # Count unique lots
        unique_lots = set(lot_identifiers)
        display_total_lots = len(unique_lots)
        
        # Determine if multi-lot
        if display_total_lots == 0:
            # No valid lot IDs or all LOT-0000 = single contract
            is_multi_lot = False
            display_total_lots = 1
            single_lot_count += 1
            lot_pattern_stats["LOT-0000 (single)"] += 1
        elif display_total_lots == 1:
            # Single LOT-0001 or similar = could be multi-lot but only one returned
            # Check if we can extract more info from description
            text_lot_count = extract_lot_count_from_text(first_notice)
            
            if text_lot_count and text_lot_count > 1:
                is_multi_lot = True
                display_total_lots = text_lot_count
                multi_lot_count += 1
                print(f"   [+] Notice {notice_id[:8]}...: Found {display_total_lots} lots from text")
                lot_pattern_stats[f"Single LOT ID, {display_total_lots} lots (from text)"] += 1
            else:
                # Treat as single
                is_multi_lot = False
                display_total_lots = 1
                single_lot_count += 1
                lot_pattern_stats["Single LOT-XXXX (treated as single)"] += 1
        else:
            # Multiple unique LOT-XXXX identifiers = definitely multi-lot
            is_multi_lot = True
            multi_lot_count += 1
            print(f"   [+] Notice {notice_id[:8]}...: {display_total_lots} lots from identifier-lot array: {sorted(unique_lots)}")
            lot_pattern_stats[f"{display_total_lots} lots (from array)"] += 1
        
        # Parse the tender
        tender = parse_tender(
            first_notice,
            lot_number=1,
            total_lots=display_total_lots,
            lot_identifiers=list(unique_lots)
        )
        
        # Set multi-lot properties
        tender["strategic"]["is_multi_lot"] = is_multi_lot
        tender["strategic"]["total_lots"] = display_total_lots
        
        # Add multi-lot metadata if applicable
        if is_multi_lot and len(unique_lots) > 0:
            tender["strategic"]["lot_identifiers"] = sorted(unique_lots)
            
            # Try to get lot titles from title-lot field
            lot_titles_raw = first_notice.get("title-lot")
            if lot_titles_raw:
                if isinstance(lot_titles_raw, dict):
                    # Get from language (prefer eng, fallback to first available)
                    lot_titles = get_value(lot_titles_raw)
                    if isinstance(lot_titles, list):
                        tender["strategic"]["lot_titles"] = lot_titles
                    else:
                        tender["strategic"]["lot_titles"] = [lot_titles] if lot_titles else []
                elif isinstance(lot_titles_raw, list):
                    tender["strategic"]["lot_titles"] = [get_value(title) for title in lot_titles_raw]
            
            # Store lot descriptions if available
            lot_descriptions_raw = first_notice.get("description-lot")
            if lot_descriptions_raw and isinstance(lot_descriptions_raw, (dict, list)):
                lot_descriptions = get_value(lot_descriptions_raw)
                if isinstance(lot_descriptions, list):
                    tender["strategic"]["lot_descriptions"] = lot_descriptions[:display_total_lots]
        
        parsed_tenders.append(tender)
    
    print(f"\n[*] Multi-Lot Detection Results:")
    print(f"   Single-lot tenders: {single_lot_count}")
    print(f"   Multi-lot tenders: {multi_lot_count}")
    print(f"   Total unique tenders: {len(parsed_tenders)}")
    
    if lot_pattern_stats:
        print(f"\n   Lot Pattern Distribution:")
        for pattern, count in sorted(lot_pattern_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"     {pattern}: {count}")
    
    return parsed_tenders


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*80)
    print("=== TED API TENDER FETCHER - FIXED MULTI-LOT DETECTION ===")
    print("="*80)
    print("\nVersion 7.0 - identifier-lot ARRAY Based Multi-Lot Detection")
    print(f"Fields: {len(TENDER_FIELDS)} comprehensive fields")
    print("\nFix: Multi-lot detection now based on identifier-lot ARRAY")
    print("     identifier-lot: [LOT-0000] = Single contract")
    print("     identifier-lot: [LOT-0001, LOT-0002, ...] = Multi-lot tender")
    print("     Counts unique LOT-XXXX values from the array")
    
    # Configuration
    COUNTRIES = ["DNK"]  # Denmark
    DAYS = 15
    OUTPUT = "tenders_enhanced.json"
    
    # Fetch raw notices
    notices = fetch_all_tenders(COUNTRIES, DAYS)
    
    if not notices:
        print("\n[!] No tenders found")
        return
    
    # Process multi-lot tenders with FIXED detection
    tenders = detect_and_process_multilot(notices)
    
    # Filter expired
    print(f"\n🗓️  Filtering expired tenders...")
    active_tenders = [
        t for t in tenders 
        if t["dates"]["days_until_deadline"] is None or t["dates"]["days_until_deadline"] >= 0
    ]
    expired_count = len(tenders) - len(active_tenders)
    print(f"   Removed {expired_count} expired tenders")
    print(f"   Kept {len(active_tenders)} active tenders")
    
    tenders = active_tenders
    
    # Calculate statistics - FIXED TO COUNT CORRECTLY
    print(f"\n[*] Calculating statistics...")
    
    urgency_stats = defaultdict(int)
    value_stats = defaultdict(int)
    sme_count = 0
    innovative_count = 0
    framework_count = 0
    multi_lot_count = 0  # FIXED: Count from is_multi_lot flag
    with_email = 0
    with_barriers = 0
    
    for tender in tenders:
        urgency = tender["dates"]["urgency_level"]
        if urgency != "EXPIRED":
            urgency_stats[urgency] += 1
        
        category = tender["financial"].get("value_category")
        if category:
            value_stats[category] += 1
        
        if tender["strategic"]["is_sme_accessible"]:
            sme_count += 1
        
        if tender["strategic"]["is_innovative"]:
            innovative_count += 1
        
        if tender["strategic"]["is_framework"]:
            framework_count += 1
        
        # FIXED: Count multi-lot properly
        if tender["strategic"]["is_multi_lot"]:
            multi_lot_count += 1
        
        if tender["buyer"]["email"]:
            with_email += 1
        
        if tender["requirements"]["security_clearance"] or tender["requirements"]["guarantee_required"]:
            with_barriers += 1
    
    # Build metadata
    metadata = {
        "fetched_at": datetime.now().isoformat(),
        "total": len(tenders),
        "fields": len(TENDER_FIELDS),
        "enhanced_features": True,
        "multi_lot_detection": True,
        "multi_lot_detection_method": "LOT-XXXX identifier pattern analysis",
        "stats": {
            "urgency": dict(urgency_stats),
            "value": dict(value_stats),
            "sme": sme_count,
            "innovative": innovative_count,
            "framework": framework_count,
            "multi_lot": multi_lot_count,  # FIXED: Now counts correctly
            "with_email": with_email,
            "with_barriers": with_barriers,
        }
    }
    
    # Save to JSON
    output_data = {
        "metadata": metadata,
        "tenders": tenders
    }
    
    print(f"\n[*] Saving to {OUTPUT}...")
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n[+] SUCCESS!")
    print(f"   File: {OUTPUT}")
    print(f"   Size: {len(json.dumps(output_data))} bytes")
    print(f"   Tenders: {len(tenders)}")
    print(f"   Multi-lot: {multi_lot_count}")
    print(f"\n" + "="*80)


if __name__ == "__main__":
    main()