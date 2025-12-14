#!/usr/bin/env python3
"""
TED API Tender Fetcher - Production Grade with Multi-Lot Detection
Version: 5.0 - Complete UI Support with Proper Multi-Lot Handling
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
    
    # === LOT STRUCTURE (4 fields) ===
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
    "lots-max-allowed-proc",      # Max lots per bidder
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

def fetch_tenders_page(query: str, page: int = 1) -> Dict[str, Any]:
    """Fetch one page from TED API."""
    payload = {
        "query": query,
        "fields": TENDER_FIELDS,
        "page": page,
        "limit": 100,
        "scope": "ACTIVE",
        "paginationMode": "PAGE_NUMBER",
        "onlyLatestVersions": True,
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
        print(f"❌ API Error: {e}")
        if hasattr(e, 'response') and e.response:
            error_text = e.response.text[:1000]
            print(f"   Response: {error_text}")
        return {}


def fetch_all_tenders(countries: List[str], days: int) -> List[Dict]:
    """Fetch ALL tenders with proper pagination."""
    print(f"\n🔍 Fetching tenders from TED API...")
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
            print("❌ Failed")
            break
        
        notices = result.get("notices", [])
        hits = result.get("hits", 0)
        
        if page == 1:
            total = hits
            print(f"✅ Total: {total} tenders")
        else:
            print(f"✅ Got {len(notices)}")
        
        if not notices:
            break
        
        all_notices.extend(notices)
        
        if len(all_notices) >= total or len(notices) < 100:
            print(f"\n✅ Complete: Fetched {len(all_notices)} tender lots")
            break
        
        page += 1
        time.sleep(0.5)  # Rate limiting
    
    return all_notices


# =============================================================================
# PARSING
# =============================================================================

def parse_tender(notice: Dict, lot_number: int = 1, total_lots: int = 1) -> Dict:
    """Parse tender with comprehensive field handling."""
    
    # === CORE IDENTIFICATION ===
    notice_id = notice.get("notice-identifier")
    pub_number = get_value(notice.get("publication-number"))
    notice_type = get_value(notice.get("notice-type"))
    title = get_value(notice.get("notice-title")) or get_value(notice.get("title-lot")) or "No title"
    description = get_value(notice.get("description-lot")) or ""
    
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
    
    # === LOT STRUCTURE ===
    lot_id = get_value(notice.get("identifier-lot"))
    is_multi_lot = total_lots > 1
    
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
    duration_raw = notice.get("contract-duration-period-lot")
    duration = None
    if duration_raw:
        try:
            if isinstance(duration_raw, dict):
                duration = duration_raw
            elif isinstance(duration_raw, list) and duration_raw:
                duration = duration_raw[0] if isinstance(duration_raw[0], dict) else None
        except:
            pass
    
    start_date = parse_date(notice.get("contract-duration-start-date-lot"))
    end_date = parse_date(notice.get("contract-duration-end-date-lot"))
    
    # === PROCEDURE DETAILS ===
    is_accelerated = parse_boolean(get_value(notice.get("procedure-accelerated")))
    variant_allowed = get_value(notice.get("variant-allowed-lot"))
    electronic_auction = parse_boolean(get_value(notice.get("electronic-auction-lot")))
    is_recurrent = parse_boolean(get_value(notice.get("recurrence-lot")))
    min_candidates = get_value(notice.get("minimum-candidate-lot"))
    max_candidates = get_value(notice.get("maximum-candidates-lot"))
    
    # === ADDITIONAL ===
    gpa_covered = parse_boolean(get_value(notice.get("gpa-lot")))
    additional_info = get_value(notice.get("additional-information-lot"))
    
    return {
        "notice_identifier": notice_id,
        "publication_number": pub_number,
        "notice_type": notice_type,
        "title": str(title),
        "description": str(description),
        
        "dates": {
            "publication_date": pub_date,
            "deadline_tender": deadline_tender,
            "deadline_request": deadline_request,
            "deadline_eoi": deadline_eoi,
            "deadline_main": main_deadline,
            "days_until_deadline": days_until,
            "urgency_level": urgency,
            "is_expired": days_until is not None and days_until < 0,
            "is_expiring_soon": days_until is not None and 0 <= days_until <= 14,
        },
        
        "buyer": {
            "name": str(buyer_name),
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
            "is_cross_border": buyer_country and perf_country and buyer_country != perf_country,
            "regional_cluster": cluster,
        },
        
        "strategic": {
            "is_sme": is_sme,
            "is_sme_accessible": is_sme or (value_eur and value_eur < 500000) or is_multi_lot,
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
# MULTI-LOT DETECTION & PROCESSING
# =============================================================================

def detect_and_process_multilot(notices: List[Dict]) -> List[Dict]:
    """
    Detect multi-lot tenders and properly process them.
    
    Multi-lot detection logic:
    - Group notices by notice_identifier
    - If multiple lots exist, mark as multi-lot
    - Keep only the first lot for main display
    - Store lot count information
    """
    print(f"\n🔄 Processing multi-lot tenders...")
    
    # Group by notice identifier
    notice_groups = defaultdict(list)
    for notice in notices:
        notice_id = notice.get("notice-identifier")
        if notice_id:
            notice_groups[notice_id].append(notice)
    
    print(f"   Found {len(notice_groups)} unique tenders")
    
    # Detect multi-lot
    multi_lot_tenders = {
        nid: lots for nid, lots in notice_groups.items() if len(lots) > 1
    }
    
    print(f"   Multi-lot tenders: {len(multi_lot_tenders)}")
    
    # Parse tenders
    parsed_tenders = []
    
    for notice_id, lots in notice_groups.items():
        total_lots = len(lots)
        is_multi = total_lots > 1
        
        # Parse first lot (or only lot)
        first_lot = lots[0]
        tender = parse_tender(first_lot, lot_number=1, total_lots=total_lots)
        
        # Add multi-lot metadata
        if is_multi:
            tender["strategic"]["lot_titles"] = [
                get_value(lot.get("title-lot")) or f"Lot {i+1}"
                for i, lot in enumerate(lots)
            ]
        
        parsed_tenders.append(tender)
    
    print(f"   Parsed {len(parsed_tenders)} unique tenders")
    
    return parsed_tenders


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*80)
    print("🇪🇺 TED API TENDER FETCHER - PRODUCTION GRADE")
    print("="*80)
    print("\nVersion 5.0 - Complete with Multi-Lot Detection")
    print(f"Fields: {len(TENDER_FIELDS)} comprehensive fields")
    
    # Configuration
    COUNTRIES = ["DNK"]  # Denmark
    DAYS = 15
    OUTPUT = "tenders_enhanced.json"
    
    # Fetch raw notices
    notices = fetch_all_tenders(COUNTRIES, DAYS)
    
    if not notices:
        print("\n⚠️  No tenders found")
        return
    
    # Process multi-lot tenders
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
    
    # Calculate statistics
    print(f"\n📊 Calculating statistics...")
    
    urgency_stats = defaultdict(int)
    value_stats = defaultdict(int)
    
    for t in tenders:
        urgency_stats[t["dates"]["urgency_level"]] += 1
        if t["financial"]["value_category"]:
            value_stats[t["financial"]["value_category"]] += 1
    
    sme_count = sum(1 for t in tenders if t["strategic"]["is_sme_accessible"])
    innovative_count = sum(1 for t in tenders if t["strategic"]["is_innovative"])
    framework_count = sum(1 for t in tenders if t["strategic"]["is_framework"])
    multi_lot_count = sum(1 for t in tenders if t["strategic"]["is_multi_lot"])
    with_email = sum(1 for t in tenders if t["buyer"]["email"])
    with_barriers = sum(1 for t in tenders if t["requirements"]["security_clearance"] or t["requirements"]["guarantee_required"])
    
    stats = {
        "urgency": dict(urgency_stats),
        "value": dict(value_stats),
        "sme": sme_count,
        "innovative": innovative_count,
        "framework": framework_count,
        "multi_lot": multi_lot_count,
        "with_email": with_email,
        "with_barriers": with_barriers,
    }
    
    print(f"   Total: {len(tenders)}")
    print(f"   Urgency: {dict(urgency_stats)}")
    print(f"   Value: {dict(value_stats)}")
    print(f"   SME Accessible: {sme_count}")
    print(f"   Innovation: {innovative_count}")
    print(f"   Framework: {framework_count}")
    print(f"   Multi-Lot: {multi_lot_count}")
    print(f"   With Email: {with_email}")
    print(f"   With Barriers: {with_barriers}")
    
    # Save
    print(f"\n💾 Saving to {OUTPUT}...")
    output = {
        "metadata": {
            "fetched_at": datetime.now().isoformat(),
            "total": len(tenders),
            "fields": len(TENDER_FIELDS),
            "enhanced_features": True,
            "multi_lot_detection": True,
            "stats": stats
        },
        "tenders": tenders
    }
    
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"✅ Saved successfully!")
    
    # Show sample
    if tenders:
        s = tenders[0]
        print(f"\n{'='*80}")
        print(f"SAMPLE TENDER")
        print(f"{'='*80}")
        print(f"Title: {s['title'][:70]}...")
        print(f"ID: {s['publication_number']}")
        print(f"Buyer: {s['buyer']['name']} ({s['buyer']['country']})")
        if s['buyer']['email']:
            print(f"Email: {s['buyer']['email']}")
        print(f"Deadline: {s['dates']['deadline_main']} ({s['dates']['urgency_level']}, {s['dates']['days_until_deadline']} days)")
        
        if s['financial']['value_eur']:
            val = s['financial']
            print(f"Value: €{val['value_eur']:,.0f} ({val['value_category']})")
        
        print(f"CPV: {s['classification']['cpv_code']}")
        print(f"Type: {s['classification']['contract_nature']} / {s['classification']['procedure_type']}")
        
        # Strategic
        tags = []
        if s['strategic']['is_sme_accessible']: tags.append("SME")
        if s['strategic']['is_framework']: tags.append("Framework")
        if s['strategic']['is_multi_lot']: tags.append(f"Multi-Lot ({s['strategic']['total_lots']} lots)")
        if s['strategic']['is_innovative']: tags.append("Innovation")
        if tags:
            print(f"Tags: {', '.join(tags)}")
        
        # Requirements
        if s['requirements']['security_clearance']:
            print(f"⚠️  Security clearance required")
        if s['requirements']['guarantee_required']:
            print(f"⚠️  Financial guarantee required")
        print(f"Complexity: {s['requirements']['complexity_level']} ({s['requirements']['complexity_score']}/100)")
        
        print(f"\nURLs:")
        print(f"  TED: {s['urls']['ted_notice_url']}")
        if s['urls']['document_url']:
            print(f"  Docs: {s['urls']['document_url'][:60]}...")
    
    print(f"\n{'='*80}")
    print(f"✅ SUCCESS! Enhanced JSON ready for UI")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()