#!/usr/bin/env python3
"""
TED API Tender Fetcher - Enhanced for Full UI Support
Incrementally adds fields needed for complete UI functionality
Version: 4.1 - Production Enhanced
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import time

# =============================================================================
# CONFIGURATION
# =============================================================================

TED_API_URL = "https://api.ted.europa.eu/v3/notices/search"
REQUEST_TIMEOUT = 30

# ENHANCED FIELD SET - Testing additional fields incrementally
# Core 24 fields that definitely work + additional UI-critical fields
TENDER_FIELDS = [
    # === CORE 24 (PROVEN TO WORK) ===
    "notice-identifier",
    "publication-number",
    "notice-type",
    "notice-title",
    "title-lot",
    "description-lot",
    "publication-date",
    "deadline-receipt-tender-date-lot",
    "deadline-receipt-request-date-lot",
    "deadline-receipt-expressions-date-lot",
    "classification-cpv",
    "contract-nature",
    "procedure-type",
    "buyer-name",
    "buyer-country",
    "buyer-city",
    "estimated-value-lot",
    "estimated-value-cur-lot",
    "place-of-performance-country-lot",
    "place-of-performance-city-lot",
    "identifier-lot",
    "sme-lot",
    "framework-agreement-lot",
    "submission-url-lot",
    
    # === ADDITIONAL UI-CRITICAL FIELDS (Testing) ===
    # Contact & Details
    "buyer-email",
    "buyer-profile",
    "buyer-legal-type",
    
    # Strategic flags
    "dps-usage-lot",
    "innovative-acquisition-lot",
    "social-objective-lot",
    "reserved-procurement-lot",
    
    # Requirements (barriers to entry)
    "security-clearance-lot",
    "guarantee-required-lot",
    "guarantee-required-description-lot",
    "electronic-submission-lot",
    
    # Award criteria
    "award-criterion-type-lot",
    "award-criterion-name-lot",
    "award-criterion-description-lot",
    
    # URLs & Documents
    "document-url-lot",
    
    # Contract details
    "contract-duration-period-lot",
    "contract-duration-start-date-lot",
    "contract-duration-end-date-lot",
    
    # Additional classification
    "additional-classification-lot",
    "main-classification-lot",
    
    # Procedure details
    "variant-allowed-lot",
    "electronic-auction-lot",
    "recurrence-lot",
    
    # Two-stage procedures
    "minimum-candidate-lot",
    "maximum-candidates-lot",
    
    # Framework details
    "framework-maximum-participants-number-lot",
    
    # Additional info
    "gpa-lot",
    "additional-information-lot",
]

CURRENCY_RATES = {"EUR": 1.0, "DKK": 0.134, "NOK": 0.084, "SEK": 0.089, "USD": 0.95, "GBP": 1.17}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_value(data: Any, default: Any = None) -> Any:
    """Extract value from TED API data."""
    if data is None:
        return default
    
    if isinstance(data, dict):
        for lang in ['eng', 'dan', 'deu', 'swe', 'nor', 'fra']:
            if lang in data:
                value = data[lang]
                if isinstance(value, list) and value:
                    return value[0]
                return value if value else default
        
        if data:
            first_value = next(iter(data.values()), default)
            if isinstance(first_value, list) and first_value:
                return first_value[0]
            return first_value if first_value else default
    
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
        except:
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


# =============================================================================
# TED API
# =============================================================================

def fetch_tenders_page(query: str, page: int = 1) -> Dict[str, Any]:
    """Fetch one page."""
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
        print(f"❌ Error: {e}")
        if hasattr(e, 'response') and e.response:
            error_text = e.response.text[:1000]
            print(f"   Response: {error_text}")
            
            # Try to identify problematic field
            if "unsupported value" in error_text.lower():
                print("\n⚠️  Some fields are not supported")
                print("   Falling back to minimal field set...")
                return {"fallback_needed": True}
        return {}


def fetch_all_tenders(countries: List[str], days: int) -> List[Dict]:
    """Fetch ALL tenders with proper pagination."""
    print(f"\n🔍 Fetching tenders...")
    print(f"   Countries: {', '.join(countries)}")
    print(f"   Last {days} days")
    print(f"   Fields: {len(TENDER_FIELDS)} (24 core + {len(TENDER_FIELDS)-24} enhanced)")
    print("-" * 80)
    
    # Build query - Try WITHOUT deadline filter first
    countries_str = ", ".join([f'"{c}"' for c in countries])
    
    # Query WITHOUT deadline filter (more results)
    query = (
        f"notice-type IN (cn-standard, cn-social, pin-cfc-standard, pin-cfc-social) "
        f"AND buyer-country IN ({countries_str}) "
        f"AND publication-date = (today(-{days}) <> today(0))"
    )
    
    print(f"   Query: {query}")
    print(f"   Note: Using publication date filter only (no deadline filter)")
    print(f"   Reason: More inclusive - will filter expired tenders after fetching")
    print("-" * 80)
    
    all_notices = []
    page = 1
    total = None
    max_pages = 50  # Safety limit (50 pages × 100 = 5000 max)
    
    while page <= max_pages:
        print(f"📄 Page {page}...", end=" ", flush=True)
        
        result = fetch_tenders_page(query, page)
        
        if result.get("fallback_needed"):
            print("⚠️  Enhanced fields not supported")
            return []
        
        if not result:
            print("❌")
            break
        
        notices = result.get("notices", [])
        hits = result.get("hits", 0)
        
        if page == 1:
            total = hits
            print(f"✅ Total available: {total}")
            
            # Debug: Show what we got
            if total == 0:
                print(f"\n⚠️  API returned 0 hits")
                print(f"   Full response: {json.dumps(result, indent=2)[:500]}...")
                
                # This might be a field issue, not a query issue
                # Let's continue to see if notices exist despite hits=0
                if not notices:
                    print(f"   No notices in response - query returned nothing")
                    return []
                else:
                    print(f"   But got {len(notices)} notices - continuing...")
        else:
            print(f"✅ Got {len(notices)}")
        
        if not notices:
            # No more results
            break
        
        all_notices.extend(notices)
        
        # Check if we got everything
        if len(all_notices) >= total:
            print(f"\n✅ Complete: Fetched all {len(all_notices)} tenders")
            break
        
        # Check if API returned less than limit (means no more pages)
        if len(notices) < 100:
            print(f"\n✅ Complete: Got all available tenders ({len(all_notices)} total)")
            break
        
        page += 1
        time.sleep(0.5)  # Rate limiting
    
    if page >= max_pages:
        print(f"\n⚠️  Reached page limit. Fetched {len(all_notices)} of {total} total")
    
    return all_notices


# =============================================================================
# PARSING
# =============================================================================

def parse_tender(notice: Dict) -> Dict:
    """Parse tender with enhanced fields."""
    
    # Core
    notice_id = notice.get("notice-identifier")
    pub_number = get_value(notice.get("publication-number"))
    title = get_value(notice.get("notice-title")) or get_value(notice.get("title-lot")) or "No title"
    description = get_value(notice.get("description-lot")) or ""
    
    # Dates
    pub_date = parse_date(notice.get("publication-date"))
    deadline_tender = parse_date(notice.get("deadline-receipt-tender-date-lot"))
    deadline_request = parse_date(notice.get("deadline-receipt-request-date-lot"))
    deadline_eoi = parse_date(notice.get("deadline-receipt-expressions-date-lot"))
    
    main_deadline = deadline_tender or deadline_request or deadline_eoi
    days_until = calculate_days_until(main_deadline)
    
    if days_until is not None:
        if days_until < 0:
            urgency = "EXPIRED"
        elif days_until <= 3:
            urgency = "CRITICAL"
        elif days_until <= 7:
            urgency = "URGENT"
        elif days_until <= 14:
            urgency = "MODERATE"
        else:
            urgency = "NORMAL"
    else:
        urgency = None
    
    # Buyer
    buyer_name = get_value(notice.get("buyer-name")) or "Unknown"
    buyer_country = get_value(notice.get("buyer-country"))
    buyer_city = get_value(notice.get("buyer-city"))
    buyer_email = get_value(notice.get("buyer-email"))
    buyer_profile = get_value(notice.get("buyer-profile"))
    
    # Regional cluster
    clusters = {
        'NORDIC': ['DNK', 'SWE', 'NOR', 'FIN', 'ISL'],
        'BALTIC': ['EST', 'LVA', 'LTU'],
        'WESTERN': ['DEU', 'FRA', 'AUT'],
        'SOUTHERN': ['ITA', 'ESP', 'PRT'],
        'EASTERN': ['POL', 'CZE', 'HUN'],
    }
    
    cluster = None
    if buyer_country:
        for name, countries in clusters.items():
            if buyer_country in countries:
                cluster = name
                break
    
    # Financial
    value_eur = None
    value_original = None
    currency = None
    category = None
    
    # Debug: Check what we're getting
    value_cur_data = notice.get("estimated-value-cur-lot")
    value_lot_data = notice.get("estimated-value-lot")
    
    # Try estimated-value-cur-lot first (has currency info)
    if value_cur_data:
        try:
            # Handle list
            if isinstance(value_cur_data, list) and value_cur_data:
                value_cur_data = value_cur_data[0]
            
            # Handle dict with amount and currency
            if isinstance(value_cur_data, dict):
                amount = value_cur_data.get("amount")
                currency = value_cur_data.get("currency", "EUR")
                
                if amount:
                    value_original = float(amount)
                    rate = CURRENCY_RATES.get(currency.upper(), 1.0)
                    value_eur = value_original * rate
            # Handle direct number
            elif isinstance(value_cur_data, (int, float)):
                value_original = float(value_cur_data)
                value_eur = value_original
                currency = "EUR"
        except Exception as e:
            # Debug print
            print(f"   ⚠️ Error parsing estimated-value-cur-lot: {e}")
            pass
    
    # Fallback to estimated-value-lot
    if value_eur is None and value_lot_data:
        try:
            # Handle list
            if isinstance(value_lot_data, list) and value_lot_data:
                value_lot_data = value_lot_data[0]
            
            # Handle dict
            if isinstance(value_lot_data, dict):
                amount = value_lot_data.get("amount") or value_lot_data.get("value")
                currency = value_lot_data.get("currency", "EUR")
                if amount:
                    value_original = float(amount)
                    rate = CURRENCY_RATES.get(currency.upper(), 1.0)
                    value_eur = value_original * rate
            # Handle direct number
            elif isinstance(value_lot_data, (int, float)):
                value_eur = float(value_lot_data)
                value_original = value_eur
                currency = "EUR"
            # Handle string number
            elif isinstance(value_lot_data, str):
                value_eur = float(value_lot_data.replace(',', ''))
                value_original = value_eur
                currency = "EUR"
        except Exception as e:
            # Debug print
            print(f"   ⚠️ Error parsing estimated-value-lot: {e}")
            pass
    
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
    
    # Classification
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
    
    # Location
    perf_country = get_value(notice.get("place-of-performance-country-lot"))
    perf_city = get_value(notice.get("place-of-performance-city-lot"))
    
    # Flags - handle "none" string values
    is_sme_raw = get_value(notice.get("sme-lot"), False)
    is_sme = is_sme_raw if isinstance(is_sme_raw, bool) else (is_sme_raw not in ["none", None, ""])
    
    is_framework_raw = get_value(notice.get("framework-agreement-lot"), False)
    is_framework = is_framework_raw if isinstance(is_framework_raw, bool) else (is_framework_raw not in ["none", None, ""])
    
    is_dps_raw = get_value(notice.get("dps-usage-lot"), False)
    is_dps = is_dps_raw if isinstance(is_dps_raw, bool) else (is_dps_raw not in ["none", None, ""])
    
    is_innovative_raw = get_value(notice.get("innovative-acquisition-lot"), False)
    is_innovative = is_innovative_raw if isinstance(is_innovative_raw, bool) else (is_innovative_raw not in ["none", None, ""])
    
    is_social_raw = get_value(notice.get("social-objective-lot"), False)
    is_social = is_social_raw if isinstance(is_social_raw, bool) else (is_social_raw not in ["none", None, ""])
    
    # Lot info
    lot_id = get_value(notice.get("identifier-lot"))
    
    # Multi-lot detection - Check if multiple lots exist in the tender
    # Note: We can't reliably detect multi-lot from a single lot's data
    # The API returns one record per lot, so a tender with 3 lots = 3 records
    # For now, we'll mark as unknown unless we group by notice-identifier
    is_multi_lot = False  # Will be calculated later if needed
    
    # Requirements
    security_clearance = get_value(notice.get("security-clearance-lot"), False)
    guarantee_required = get_value(notice.get("guarantee-required-lot"), False)
    electronic_submission = get_value(notice.get("electronic-submission-lot"), False)
    
    # Calculate complexity score
    complexity = 0
    if security_clearance:
        complexity += 20
    if guarantee_required:
        complexity += 10
    if get_value(notice.get("procedure-type")) in ["restricted", "comp-dial"]:
        complexity += 20
    
    complexity_level = "COMPLEX" if complexity >= 30 else "MODERATE" if complexity >= 15 else "SIMPLE"
    
    # URLs
    submission_url = get_value(notice.get("submission-url-lot"))
    document_url = get_value(notice.get("document-url-lot"))
    ted_url = f"https://ted.europa.eu/en/notice/-/detail/{pub_number}" if pub_number else None
    
    # Award criteria
    award_type = get_value(notice.get("award-criterion-type-lot"))
    award_name = get_value(notice.get("award-criterion-name-lot"))
    
    # Contract duration - handle nested structure
    duration_raw = notice.get("contract-duration-period-lot")
    duration = None
    if duration_raw:
        try:
            if isinstance(duration_raw, dict):
                # Structure like {"unit": "YEAR", "value": "10"}
                duration = duration_raw
            elif isinstance(duration_raw, list) and duration_raw:
                duration = duration_raw[0] if isinstance(duration_raw[0], dict) else None
        except:
            pass
    
    return {
        "notice_identifier": notice_id,
        "publication_number": pub_number,
        "notice_type": get_value(notice.get("notice-type")),
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
            "legal_type": get_value(notice.get("buyer-legal-type")),
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
            "contract_nature": get_value(notice.get("contract-nature")),
            "procedure_type": get_value(notice.get("procedure-type")),
        },
        
        "location": {
            "performance_country": perf_country,
            "performance_city": perf_city,
            "is_cross_border": buyer_country and perf_country and buyer_country != perf_country,
            "regional_cluster": cluster,
        },
        
        "strategic": {
            "is_sme": is_sme,
            "is_sme_accessible": is_sme or (value_eur and value_eur < 500000),
            "is_framework": is_framework,
            "is_dps": is_dps,
            "is_innovative": is_innovative,
            "is_social": is_social,
            "is_multi_lot": is_multi_lot,
            "lot_identifier": lot_id,
        },
        
        "requirements": {
            "security_clearance": security_clearance,
            "guarantee_required": guarantee_required,
            "guarantee_description": get_value(notice.get("guarantee-required-description-lot")),
            "electronic_submission": electronic_submission,
            "complexity_score": complexity,
            "complexity_level": complexity_level,
        },
        
        "award_criteria": {
            "type": award_type,
            "name": award_name,
            "description": get_value(notice.get("award-criterion-description-lot")),
        },
        
        "contract": {
            "duration": duration,
            "start_date": parse_date(notice.get("contract-duration-start-date-lot")),
            "end_date": parse_date(notice.get("contract-duration-end-date-lot")),
        },
        
        "procedure": {
            "variant_allowed": get_value(notice.get("variant-allowed-lot"), False),
            "electronic_auction": get_value(notice.get("electronic-auction-lot"), False),
            "is_recurrent": get_value(notice.get("recurrence-lot"), False),
            "minimum_candidates": get_value(notice.get("minimum-candidate-lot")),
            "maximum_candidates": get_value(notice.get("maximum-candidates-lot")),
        },
        
        "urls": {
            "submission_url": submission_url,
            "document_url": document_url,
            "ted_notice_url": ted_url,
            "ted_pdf_url": f"https://ted.europa.eu/en/notice/{pub_number}/pdf" if pub_number else None,
        },
        
        "additional": {
            "gpa_covered": get_value(notice.get("gpa-lot"), False),
            "additional_info": get_value(notice.get("additional-information-lot")),
        },
        
        "metadata": {
            "fetched_at": datetime.now().isoformat(),
            "api_version": "v3",
            "fields_count": len(TENDER_FIELDS),
        }
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*80)
    print("🇪🇺 TED API TENDER FETCHER - ENHANCED")
    print("="*80)
    print("\nVersion 4.1 - Full UI Support")
    print(f"Testing {len(TENDER_FIELDS)} fields for complete UI functionality")
    
    # Config
    COUNTRIES = ["DNK"]
    DAYS = 15
    OUTPUT = "tenders_enhanced.json"
    
    # Fetch
    notices = fetch_all_tenders(COUNTRIES, DAYS)
    
    if not notices:
        print("\n⚠️  Enhanced fields not supported or no tenders found")
        print("   Falling back to minimal field set recommended")
        return
    
    # Parse
    print(f"\n📝 Parsing...")
    tenders = [parse_tender(n) for n in notices]
    print(f"   {len(tenders)} ✅")
    
    # Post-process: Detect multi-lot tenders
    print(f"\n🔄 Detecting multi-lot tenders...")
    notice_id_counts = {}
    for t in tenders:
        nid = t["notice_identifier"]
        if nid:
            notice_id_counts[nid] = notice_id_counts.get(nid, 0) + 1
    
    # Mark tenders that appear multiple times as multi-lot
    multi_lot_count = 0
    for t in tenders:
        nid = t["notice_identifier"]
        if nid and notice_id_counts[nid] > 1:
            t["strategic"]["is_multi_lot"] = True
            multi_lot_count += 1
    
    print(f"   Found {len([c for c in notice_id_counts.values() if c > 1])} multi-lot tenders ({multi_lot_count} lot records)")
    
    # Filter out expired tenders (deadline in the past)
    print(f"\n🗓️  Filtering expired tenders...")
    original_count = len(tenders)
    active_tenders = []
    for t in tenders:
        days = t["dates"]["days_until_deadline"]
        if days is None or days >= 0:
            active_tenders.append(t)
    
    expired_count = original_count - len(active_tenders)
    print(f"   Removed {expired_count} expired tenders")
    print(f"   Kept {len(active_tenders)} active tenders")
    tenders = active_tenders
    
    # Deduplicate: Keep only first lot of multi-lot tenders for cleaner display
    # Users can see all lots by clicking through to TED
    print(f"\n🧹 Deduplicating multi-lot tenders...")
    seen_notices = set()
    deduplicated = []
    for t in tenders:
        nid = t["notice_identifier"]
        if nid not in seen_notices:
            deduplicated.append(t)
            seen_notices.add(nid)
    
    print(f"   Kept {len(deduplicated)} unique tenders (removed {len(tenders) - len(deduplicated)} duplicate lots)")
    tenders = deduplicated
    
    # Stats
    urgency = {}
    for t in tenders:
        u = t["dates"]["urgency_level"]
        urgency[u] = urgency.get(u, 0) + 1
    
    value_cats = {}
    for t in tenders:
        c = t["financial"]["value_category"]
        if c:
            value_cats[c] = value_cats.get(c, 0) + 1
    
    sme = sum(1 for t in tenders if t["strategic"]["is_sme_accessible"])
    innovative = sum(1 for t in tenders if t["strategic"]["is_innovative"])
    with_email = sum(1 for t in tenders if t["buyer"]["email"])
    with_barriers = sum(1 for t in tenders if t["requirements"]["security_clearance"] or t["requirements"]["guarantee_required"])
    
    print(f"\n📊 Stats:")
    print(f"   Total: {len(tenders)}")
    print(f"   Urgency: {urgency}")
    print(f"   Value: {value_cats}")
    print(f"   SME: {sme}")
    print(f"   Innovation: {innovative}")
    print(f"   With Email: {with_email}")
    print(f"   With Barriers: {with_barriers}")
    
    # Save
    print(f"\n💾 Saving...")
    output = {
        "metadata": {
            "fetched_at": datetime.now().isoformat(),
            "total": len(tenders),
            "fields": len(TENDER_FIELDS),
            "enhanced_features": True,
            "stats": {
                "urgency": urgency,
                "value": value_cats,
                "sme": sme,
                "innovative": innovative,
                "with_email": with_email,
                "with_barriers": with_barriers,
            }
        },
        "tenders": tenders
    }
    
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"✅ Saved to {OUTPUT}")
    
    # Sample
    if tenders:
        s = tenders[0]
        print(f"\n{'='*80}")
        print(f"SAMPLE TENDER (Full UI Data)")
        print(f"{'='*80}")
        print(f"Title: {s['title'][:70]}...")
        print(f"Buyer: {s['buyer']['name']} ({s['buyer']['country']})")
        if s['buyer']['email']:
            print(f"Email: {s['buyer']['email']}")
        print(f"Deadline: {s['dates']['deadline_main']} ({s['dates']['urgency_level']})")
        if s['financial']['value_eur']:
            val = s['financial']
            if val['currency'] and val['value_original']:
                print(f"Value: {val['value_original']:,.0f} {val['currency']} = €{val['value_eur']:,.0f} ({val['value_category']})")
        print(f"CPV: {s['classification']['cpv_code']}")
        
        # Strategic tags
        tags = []
        if s['strategic']['is_sme_accessible']: tags.append("SME")
        if s['strategic']['is_framework']: tags.append("Framework")
        if s['strategic']['is_innovative']: tags.append("Innovation")
        if s['strategic']['is_social']: tags.append("Social")
        if tags:
            print(f"Tags: {', '.join(tags)}")
        
        # Requirements
        if s['requirements']['security_clearance']:
            print(f"⚠️  Security clearance required")
        if s['requirements']['guarantee_required']:
            print(f"⚠️  Financial guarantee required")
        
        print(f"Complexity: {s['requirements']['complexity_level']}")
        
        if s['award_criteria']['type']:
            print(f"Award: {s['award_criteria']['type']}")
        
        if s['contract']['duration']:
            print(f"Duration: {s['contract']['duration']}")
        
        print(f"\nURLs:")
        if s['urls']['document_url']:
            print(f"  Docs: {s['urls']['document_url'][:60]}...")
        if s['urls']['submission_url']:
            print(f"  Submit: {s['urls']['submission_url'][:60]}...")
        print(f"  TED: {s['urls']['ted_notice_url']}")
    
    print(f"\n{'='*80}")
    print(f"✅ SUCCESS! Full UI data available")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()