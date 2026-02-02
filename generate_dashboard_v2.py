#!/usr/bin/env python3
"""
Payments Intelligence Dashboard Generator v2
=============================================
STANDALONE VERSION - No pip installs required!
Uses only Python standard library.

Features:
- Reads all URLs from URL.docx
- 30-day rolling lookback (configurable)
- JSON storage with deduplication
- NAICS code + description columns
- Region/state column
- Collapsible rows by NAICS
- Search/filter functionality
- Progress indicator
- Retry logic for failed URLs

Usage:
    python3 generate_dashboard_v2.py
"""

import os
import re
import json
import zipfile
import ssl
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from html.parser import HTMLParser
import time

# =============================================================================
# CONFIGURATION - EDIT THESE VALUES
# =============================================================================

AZURE_OPENAI_ENDPOINT = "https://az-n-df-dcs-openai.azure.com/"
AZURE_OPENAI_API_KEY = ""       # <-- ENTER YOUR API KEY HERE
AZURE_OPENAI_DEPLOYMENT = "az-n-df-dcs-dev-gpt5-ds-model"
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"

NEWS_LOOKBACK_DAYS = 1          # Show last 1 day in dashboard (testing)
STORAGE_RETENTION_DAYS = 365    # Keep articles in JSON for 1 year
REQUEST_DELAY = 0.5             # Seconds between requests (rate limiting)
REQUEST_TIMEOUT = 30            # Seconds before timeout
MAX_RETRIES = 2                 # Retry failed URLs this many times

# =============================================================================
# FILE PATHS
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
OUTPUT_FILE = SCRIPT_DIR / "payments_dashboard.html"
STORAGE_FILE = SCRIPT_DIR / "news_storage.json"
PROMPT_DOC = SCRIPT_DIR / "Prompt Claude.docx"
URL_DOC = SCRIPT_DIR / "URL.docx"

# =============================================================================
# NAICS CODE MAPPING
# =============================================================================

NAICS_DESCRIPTIONS = {
    "UNC": "Unclassified (Needs AI Tagging)",
    "111": "Crop Production",
    "112": "Animal Production",
    "113": "Forestry and Logging",
    "114": "Fishing, Hunting, Trapping",
    "115": "Agriculture Support",
    "211": "Oil and Gas Extraction",
    "212": "Mining (except Oil/Gas)",
    "213": "Mining Support",
    "221": "Utilities",
    "236": "Construction of Buildings",
    "237": "Heavy and Civil Engineering",
    "238": "Specialty Trade Contractors",
    "311": "Food Manufacturing",
    "312": "Beverage and Tobacco",
    "313": "Textile Mills",
    "314": "Textile Product Mills",
    "315": "Apparel Manufacturing",
    "316": "Leather Products",
    "321": "Wood Products",
    "322": "Paper Manufacturing",
    "323": "Printing",
    "324": "Petroleum and Coal Products",
    "325": "Chemical Manufacturing",
    "326": "Plastics and Rubber",
    "327": "Nonmetallic Minerals",
    "331": "Primary Metals",
    "332": "Fabricated Metal Products",
    "333": "Machinery Manufacturing",
    "334": "Computer and Electronics",
    "335": "Electrical Equipment",
    "336": "Transportation Equipment",
    "337": "Furniture Manufacturing",
    "339": "Miscellaneous Manufacturing",
    "423": "Merchant Wholesalers - Durables",
    "424": "Merchant Wholesalers - Nondurables",
    "425": "Electronic Markets and Agents",
    "441": "Motor Vehicle Dealers",
    "442": "Furniture Stores",
    "443": "Electronics Stores",
    "444": "Building Materials Stores",
    "445": "Food and Beverage Stores",
    "446": "Health and Personal Care Stores",
    "447": "Gasoline Stations",
    "448": "Clothing Stores",
    "449": "Furniture and Home Furnishing Retail",
    "451": "Sporting Goods and Hobby Stores",
    "452": "General Merchandise Stores",
    "453": "Miscellaneous Retailers",
    "454": "Nonstore Retailers",
    "455": "General Merchandise Retail",
    "456": "Health and Personal Care Retail",
    "457": "Gasoline Stations and Fuel Dealers",
    "458": "Clothing and Accessories Retail",
    "459": "Sporting Goods and Hobby Retail",
    "481": "Air Transportation",
    "482": "Rail Transportation",
    "483": "Water Transportation",
    "484": "Truck Transportation",
    "485": "Transit and Ground Passenger",
    "486": "Pipeline Transportation",
    "487": "Scenic and Sightseeing",
    "488": "Transportation Support",
    "491": "Postal Service",
    "492": "Couriers and Messengers",
    "493": "Warehousing and Storage",
    "511": "Publishing Industries",
    "512": "Motion Picture and Sound",
    "513": "Broadcasting and Content",
    "516": "Internet Publishing",
    "517": "Telecommunications",
    "518": "Computing Infrastructure",
    "519": "Web Search and Data Processing",
    "521": "Monetary Authorities",
    "522": "Credit Intermediation",
    "523": "Securities and Investments",
    "524": "Insurance Carriers",
    "525": "Funds, Trusts, Financial",
    "531": "Real Estate",
    "532": "Rental and Leasing",
    "533": "Intellectual Property Lessors",
    "541": "Professional and Technical Services",
    "551": "Management of Companies",
    "561": "Administrative Services",
    "562": "Waste Management",
    "611": "Educational Services",
    "621": "Ambulatory Health Care",
    "622": "Hospitals",
    "623": "Nursing and Residential Care",
    "624": "Social Assistance",
    "711": "Performing Arts and Sports",
    "712": "Museums and Historical Sites",
    "713": "Amusement and Recreation",
    "721": "Accommodation",
    "722": "Food Services and Drinking",
    "811": "Repair and Maintenance",
    "812": "Personal and Laundry Services",
    "813": "Religious and Civic Organizations",
    "814": "Private Households",
    "921": "Executive and Legislative",
    "922": "Justice and Public Safety",
    "923": "Administration of Human Resources",
    "924": "Administration of Environmental",
    "925": "Community and Housing Programs",
    "926": "Administration of Economic Programs",
    "927": "Space Research",
    "928": "National Security",
}

def get_naics_description(code):
    """Get NAICS description from code."""
    if not code:
        return "Unknown"
    code = str(code).strip()[:3]
    return NAICS_DESCRIPTIONS.get(code, f"Industry {code}")

# =============================================================================
# HTML PARSER
# =============================================================================

class SimpleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.links = []
        self.current_link = None
        self.current_link_text = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.in_script = True
        elif tag == 'style':
            self.in_style = True
        elif tag == 'a':
            attrs_dict = dict(attrs)
            if 'href' in attrs_dict:
                self.current_link = attrs_dict['href']
                self.current_link_text = []

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_script = False
        elif tag == 'style':
            self.in_style = False
        elif tag == 'a' and self.current_link:
            text = ' '.join(self.current_link_text).strip()
            if text and len(text) > 10:
                self.links.append({"text": text[:150], "url": self.current_link})
            self.current_link = None
            self.current_link_text = []

    def handle_data(self, data):
        if not self.in_script and not self.in_style:
            text = data.strip()
            if text:
                self.text_parts.append(text)
                if self.current_link:
                    self.current_link_text.append(text)

    def get_text(self):
        return ' '.join(self.text_parts)

    def get_links(self):
        return self.links

# =============================================================================
# HTTP UTILITIES
# =============================================================================

def create_ssl_context():
    """Create SSL context for HTTPS requests."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def fetch_url(url, timeout=REQUEST_TIMEOUT, retries=MAX_RETRIES):
    """Fetch URL with retry logic."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    ctx = create_ssl_context()

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                content = response.read()
                try:
                    return content.decode('utf-8')
                except:
                    return content.decode('latin-1', errors='ignore')
        except Exception as e:
            if attempt < retries:
                time.sleep(1)  # Wait before retry
                continue
            return ""
    return ""

# =============================================================================
# DATE PARSING
# =============================================================================

def parse_date(date_str):
    """Parse date string to datetime."""
    if not date_str:
        return None

    # Clean string
    date_str = re.sub(r'\+\d{2}:\d{2}', '', str(date_str))
    date_str = re.sub(r'T', ' ', date_str)
    date_str = re.sub(r'\.\d+', '', date_str)
    date_str = re.sub(r'Z$', '', date_str)
    date_str = date_str.strip()

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%m/%d/%Y",
        "%a, %d %b %Y %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %Z",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue

    # Try regex extraction
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except:
            pass

    return None

# =============================================================================
# DOCUMENT EXTRACTION
# =============================================================================

def extract_text_from_docx(docx_path):
    """Extract text from .docx file."""
    try:
        with zipfile.ZipFile(docx_path, 'r') as zip_ref:
            xml_content = zip_ref.read('word/document.xml')
        root = ET.fromstring(xml_content)
        texts = []
        for elem in root.iter():
            if elem.tag.endswith('}t') and elem.text:
                texts.append(elem.text)
        return ' '.join(texts)
    except Exception as e:
        print(f"    [!] Error reading {docx_path}: {e}")
        return ""

def extract_urls_from_docx(docx_path):
    """Extract all URLs from URL.docx file."""
    text = extract_text_from_docx(docx_path)
    # Find all URLs
    url_pattern = r'https?://[^\s<>"\')\]}>]+'
    urls = re.findall(url_pattern, text)
    # Clean and dedupe
    clean_urls = []
    seen = set()
    for url in urls:
        url = url.rstrip('.,;:')
        if url not in seen and len(url) > 15:
            seen.add(url)
            clean_urls.append(url)
    return clean_urls

# =============================================================================
# JSON STORAGE
# =============================================================================

def load_storage():
    """Load existing JSON storage."""
    if STORAGE_FILE.exists():
        try:
            with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"articles": [], "last_updated": None}

def save_storage(data):
    """Save to JSON storage."""
    data["last_updated"] = datetime.now().isoformat()
    with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def add_articles_to_storage(new_articles, storage):
    """Add new articles to storage, deduplicate, and prune old ones."""
    existing_urls = {a.get('url') for a in storage.get('articles', [])}

    added = 0
    for article in new_articles:
        if article.get('url') and article['url'] not in existing_urls:
            storage['articles'].append(article)
            existing_urls.add(article['url'])
            added += 1

    # Prune articles older than retention period
    cutoff = datetime.now() - timedelta(days=STORAGE_RETENTION_DAYS)
    original_count = len(storage['articles'])
    storage['articles'] = [
        a for a in storage['articles']
        if not a.get('date') or parse_date(a['date']) is None or parse_date(a['date']) >= cutoff
    ]
    pruned = original_count - len(storage['articles'])

    return added, pruned

# =============================================================================
# NEWS FETCHING
# =============================================================================

def categorize_url(url):
    """Categorize URL by type."""
    url_lower = url.lower()
    if any(x in url_lower for x in ['fed', 'treasury', 'bls.gov', 'bea.gov']):
        return 'fed'
    elif any(x in url_lower for x in ['visa', 'mastercard', 'amex', 'discover', 'nacha']):
        return 'payment_network'
    elif any(x in url_lower for x in ['cfpb', 'ftc.gov', 'occ.gov', 'fdic.gov']):
        return 'regulation'
    elif any(x in url_lower for x in ['walmart', 'target', 'costco', 'kroger', 'amazon']):
        return 'merchant'
    elif any(x in url_lower for x in ['grocery', 'retail', 'restaurant', 'food']):
        return 'merchant'
    elif any(x in url_lower for x in ['payment', 'fintech', 'pymnts']):
        return 'competitive'
    else:
        return 'macro'

def get_source_name(url):
    """Extract source name from URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        # Get main domain name
        parts = domain.split('.')
        if len(parts) >= 2:
            return parts[-2].title()
        return domain.title()
    except:
        return "Unknown"

def fetch_rss(url, source_name, category):
    """Fetch and parse RSS feed."""
    articles = []
    content = fetch_url(url)
    if not content:
        return articles

    try:
        root = ET.fromstring(content)

        # Try RSS 2.0 format
        items = root.findall('.//item')

        # Try Atom format if no items
        if not items:
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            items = root.findall('.//atom:entry', ns)

        for item in items[:30]:  # Limit per source
            # Get title
            title_elem = item.find('title')
            if title_elem is None:
                title_elem = item.find('{http://www.w3.org/2005/Atom}title')
            title = title_elem.text if title_elem is not None and title_elem.text else ""

            # Get link
            link_elem = item.find('link')
            if link_elem is None:
                link_elem = item.find('{http://www.w3.org/2005/Atom}link')
                link = link_elem.get('href', '') if link_elem is not None else ""
            else:
                link = link_elem.text if link_elem.text else ""

            # Get date
            date_str = None
            for tag in ['pubDate', 'published', 'updated', '{http://www.w3.org/2005/Atom}published', '{http://www.w3.org/2005/Atom}updated']:
                date_elem = item.find(tag)
                if date_elem is not None and date_elem.text:
                    date_str = date_elem.text
                    break

            # Get description
            desc_elem = item.find('description')
            if desc_elem is None:
                desc_elem = item.find('{http://www.w3.org/2005/Atom}summary')
            description = ""
            if desc_elem is not None and desc_elem.text:
                description = re.sub(r'<[^>]+>', '', desc_elem.text)[:500]

            pub_date = parse_date(date_str)

            # Apply same title filtering as webpage scraper
            if title and link and is_valid_news_title(title):
                articles.append({
                    "title": title.strip()[:200],
                    "url": link.strip(),
                    "date": pub_date.strftime("%Y-%m-%d") if pub_date else None,
                    "description": description.strip(),
                    "source": source_name,
                    "category": category,
                    "fetched_at": datetime.now().isoformat()
                })
    except Exception as e:
        pass

    return articles

def is_valid_news_title(title):
    """Filter out non-news content like process steps, navigation, FAQs."""
    if not title or len(title) < 20:
        return False

    title_lower = title.lower().strip()

    # Filter out process steps (Step 1, Step 2, etc.)
    if re.match(r'^step\s*\d', title_lower):
        return False

    # Filter out numbered lists that aren't news
    if re.match(r'^\d+\.\s*(how|what|why|when|where|who|get|apply|register|submit|complete|fill)', title_lower):
        return False

    # Filter out FAQ-style content
    faq_patterns = [
        r'^how (do|to|can|does)',
        r'^what (is|are|do|does|should)',
        r'^why (do|does|is|are|should)',
        r'^when (do|does|is|are|should|can)',
        r'^frequently asked',
        r'^faq',
        r'^q\s*:',
        r'^a\s*:',
    ]
    for pattern in faq_patterns:
        if re.match(pattern, title_lower):
            return False

    # Filter out navigation/UI elements
    nav_keywords = [
        'click here', 'read more', 'learn more', 'view all', 'see more',
        'subscribe', 'sign up', 'log in', 'login', 'register now',
        'contact us', 'about us', 'privacy policy', 'terms of',
        'cookie policy', 'disclaimer', 'copyright', 'all rights reserved',
        'skip to', 'jump to', 'back to', 'return to', 'go to',
        'menu', 'navigation', 'search', 'home page', 'main page',
        'apply now', 'apply online', 'submit application', 'fill out',
        'download form', 'upload', 'attachment', 'required documents',
    ]
    for keyword in nav_keywords:
        if keyword in title_lower:
            return False

    # Filter out instruction/how-to content
    instruction_patterns = [
        r'^\d+\s+ways\s+to',
        r'^how to (apply|get|file|submit|register|complete|fill)',
        r'^(apply|get|file|submit|register) (for|your|the)',
        r'^(complete|fill|submit) (your|the|this)',
        r'^(required|necessary|needed) (documents|information|forms)',
        r'^eligibility',
        r'^requirements',
        r'^instructions',
        r'^checklist',
        r'^tips for',
        r'^guide to',
    ]
    for pattern in instruction_patterns:
        if re.match(pattern, title_lower):
            return False

    # Filter out generic/boilerplate
    boilerplate = [
        'welcome to', 'thank you for', 'please note', 'important notice',
        'site map', 'accessibility', 'help center', 'customer service',
        'technical support', 'feedback', 'survey', 'newsletter',
    ]
    for text in boilerplate:
        if text in title_lower:
            return False

    # Must have at least some alphabetic content (not just numbers/symbols)
    if not re.search(r'[a-zA-Z]{3,}', title):
        return False

    return True

def fetch_webpage(url, source_name, category):
    """Fetch webpage and extract articles."""
    articles = []
    content = fetch_url(url)
    if not content:
        return articles

    parser = SimpleHTMLParser()
    try:
        parser.feed(content)
    except:
        pass

    links = parser.get_links()

    for link in links[:50]:  # Check more links since we filter
        article_url = link['url']
        title = link['text'].strip()

        # Skip if not valid news title
        if not is_valid_news_title(title):
            continue

        if article_url.startswith('/'):
            article_url = urllib.parse.urljoin(url, article_url)

        if article_url.startswith('http'):
            articles.append({
                "title": title[:200],
                "url": article_url,
                "date": None,
                "description": "",
                "source": source_name,
                "category": category,
                "fetched_at": datetime.now().isoformat()
            })

        # Limit to 25 valid articles per source
        if len(articles) >= 25:
            break

    return articles

def fetch_all_news(urls):
    """Fetch news from all URLs."""
    print(f"\n[2/5] Fetching news from {len(urls)} sources...")
    print(f"      This may take several minutes...")

    all_articles = []

    for i, url in enumerate(urls):
        source_name = get_source_name(url)
        category = categorize_url(url)

        # Progress indicator
        progress = f"[{i+1}/{len(urls)}]"
        print(f"    {progress} {source_name}...", end=" ", flush=True)

        articles = []

        # Try as RSS first
        if any(x in url.lower() for x in ['feed', 'rss', 'xml', 'atom']):
            articles = fetch_rss(url, source_name, category)

        # If no RSS results, try webpage
        if not articles:
            articles = fetch_webpage(url, source_name, category)

        all_articles.extend(articles)
        print(f"{len(articles)} articles")

        # Rate limiting
        time.sleep(REQUEST_DELAY)

    print(f"\n      Total: {len(all_articles)} articles fetched")
    return all_articles

# =============================================================================
# AZURE OPENAI API
# =============================================================================

def call_azure_openai(prompt):
    """Call Azure OpenAI API."""
    if not AZURE_OPENAI_API_KEY:
        print("    [!] Azure OpenAI API key not set.")
        return None

    url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"

    headers = {
        'Content-Type': 'application/json',
        'api-key': AZURE_OPENAI_API_KEY
    }

    payload = {
        "messages": [
            {"role": "system", "content": "You are a senior payments data analyst. Analyze news articles and return ONLY valid JSON. Tag each article with NAICS code, impact, confidence, and region/state."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4096
    }

    try:
        data = json.dumps(payload).encode('utf-8')
        ctx = create_ssl_context()
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')

        with urllib.request.urlopen(req, timeout=120, context=ctx) as response:
            result = json.loads(response.read().decode('utf-8'))
            content = result['choices'][0]['message']['content']

            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
    except Exception as e:
        print(f"    [!] Azure OpenAI error: {e}")

    return None

def create_tagging_prompt(articles):
    """Create prompt for AI tagging."""
    articles_text = ""
    for i, a in enumerate(articles[:50]):  # Limit to 50 for API
        articles_text += f"\n{i+1}. [{a.get('date', 'Unknown')}] {a['title']}\n   Source: {a['source']}\n   URL: {a['url']}\n"

    return f"""Analyze these payment/finance news articles and return a JSON object.

ARTICLES:
{articles_text}

For each article, determine:
1. naics3: 3-digit NAICS code (e.g., "522" for Credit Intermediation, "445" for Food Stores, "721" for Hotels)
2. impact: "positive", "negative", "mixed", or "unclear" (effect on spend/transactions)
3. confidence: 0.0 to 1.0 (how certain you are)
4. region: US state abbreviation(s) or "National" or region name
   - Single state: "CA"
   - Multiple states: "FL, GA, SC"
   - Region: "Southwest" or "Northeast"
   - National/unclear: "National"

Return JSON in this exact format:
{{
    "tagged_articles": [
        {{
            "index": 1,
            "naics3": "522",
            "impact": "positive",
            "confidence": 0.85,
            "region": "National"
        }},
        ...
    ]
}}

Return ONLY the JSON object, no other text."""

def tag_articles_with_ai(articles):
    """Tag articles using Azure OpenAI."""
    if not articles:
        return articles

    print(f"[3/5] Tagging {len(articles)} articles with AI...")

    # Process in batches
    batch_size = 50
    all_tags = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i+batch_size]
        print(f"      Processing batch {i//batch_size + 1}...")

        prompt = create_tagging_prompt(batch)
        result = call_azure_openai(prompt)

        if result and 'tagged_articles' in result:
            all_tags.extend(result['tagged_articles'])
        else:
            # Mark as unclassified if API fails (requires API key)
            for j, _ in enumerate(batch):
                all_tags.append({
                    "index": i + j + 1,
                    "naics3": "UNC",
                    "impact": "unclassified",
                    "confidence": 0.0,
                    "region": "Unknown"
                })

    # Apply tags to articles
    for tag in all_tags:
        idx = tag.get('index', 0) - 1
        if 0 <= idx < len(articles):
            articles[idx]['naics3'] = tag.get('naics3', '')
            articles[idx]['naics_desc'] = get_naics_description(tag.get('naics3', ''))
            articles[idx]['impact'] = tag.get('impact', 'unclear')
            articles[idx]['confidence'] = tag.get('confidence', 0.5)
            articles[idx]['region'] = tag.get('region', 'National')

    print(f"      Tagged {len(articles)} articles")
    return articles

# =============================================================================
# HTML DASHBOARD GENERATION
# =============================================================================

def generate_dashboard(articles, date_str):
    """Generate HTML dashboard with collapsible NAICS groups and search."""

    # Filter to lookback period
    cutoff = datetime.now() - timedelta(days=NEWS_LOOKBACK_DAYS)
    filtered = []
    for a in articles:
        if a.get('date'):
            article_date = parse_date(a['date'])
            if article_date and article_date >= cutoff:
                filtered.append(a)
        else:
            filtered.append(a)  # Include articles without dates

    # Sort by NAICS, then date
    filtered.sort(key=lambda x: (x.get('naics3', 'ZZZ'), x.get('date', '0000-00-00')), reverse=True)

    # Group by NAICS
    naics_groups = {}
    for a in filtered:
        code = a.get('naics3', 'Other')
        if code not in naics_groups:
            naics_groups[code] = []
        naics_groups[code].append(a)

    # Build table rows with groups
    rows_html = ""
    for naics_code in sorted(naics_groups.keys()):
        articles_in_group = naics_groups[naics_code]
        desc = get_naics_description(naics_code)
        count = len(articles_in_group)

        # Group header row (clickable)
        rows_html += f'''<tr class="group-header" data-naics="{naics_code}" onclick="toggleGroup('{naics_code}')">
            <td colspan="9" class="group-cell">
                <span class="toggle-icon" id="icon-{naics_code}">+</span>
                <strong>{naics_code}</strong> - {desc} ({count} articles)
            </td>
        </tr>'''

        # Article rows (hidden by default)
        for a in articles_in_group:
            conf = a.get('confidence', 0.5)
            conf_class = "conf-high" if conf >= 0.8 else "conf-med" if conf >= 0.65 else "conf-low"
            impact = a.get('impact', 'unclear')

            rows_html += f'''<tr class="article-row naics-{naics_code}" style="display:none;">
                <td>{a.get('naics3', '')}</td>
                <td>{a.get('naics_desc', '')}</td>
                <td>{a.get('date', 'N/A')}</td>
                <td>{a.get('region', 'National')}</td>
                <td class="title-cell">{a.get('title', '')[:80]}...</td>
                <td>{a.get('source', '')}</td>
                <td class="impact-{impact}">{impact.title()}</td>
                <td><span class="conf-bar {conf_class}"><span style="width:{int(conf*100)}%"></span></span>{conf:.2f}</td>
                <td><a href="{a.get('url', '#')}" target="_blank">Link</a></td>
            </tr>'''

    # Summary stats
    total_articles = len(filtered)
    positive = len([a for a in filtered if a.get('impact') == 'positive'])
    negative = len([a for a in filtered if a.get('impact') == 'negative'])
    unique_naics = len(naics_groups)

    html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Payments Intelligence Dashboard | {date_str}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: linear-gradient(135deg, #0a1628, #1a2744); min-height: 100vh; color: #e4e9f0; padding: 20px; }}
.container {{ max-width: 1600px; margin: 0 auto; }}
h1 {{ font-size: 2rem; font-weight: 300; color: #fff; text-align: center; margin-bottom: 5px; }}
.subtitle {{ color: #64b5f6; text-align: center; font-size: 0.9rem; margin-bottom: 20px; }}

/* Stats */
.stats {{ display: flex; gap: 15px; justify-content: center; margin-bottom: 20px; flex-wrap: wrap; }}
.stat {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 15px 25px; text-align: center; }}
.stat-value {{ font-size: 1.8rem; font-weight: 600; }}
.stat-label {{ font-size: 0.75rem; color: #90a4ae; text-transform: uppercase; }}
.stat.positive .stat-value {{ color: #4caf50; }}
.stat.negative .stat-value {{ color: #f44336; }}
.stat.neutral .stat-value {{ color: #64b5f6; }}

/* Search */
.search-box {{ margin-bottom: 20px; text-align: center; }}
.search-box input {{ width: 100%; max-width: 500px; padding: 12px 20px; font-size: 1rem; border: 1px solid rgba(255,255,255,0.2); border-radius: 25px; background: rgba(255,255,255,0.05); color: #fff; }}
.search-box input::placeholder {{ color: #90a4ae; }}
.search-box input:focus {{ outline: none; border-color: #64b5f6; }}

/* Table */
.table-container {{ background: rgba(255,255,255,0.03); border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.08); }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
th {{ background: rgba(100,181,246,0.15); color: #64b5f6; font-weight: 600; text-transform: uppercase; font-size: 0.7rem; padding: 12px 8px; text-align: left; position: sticky; top: 0; }}
td {{ padding: 10px 8px; border-bottom: 1px solid rgba(255,255,255,0.05); color: #cfd8dc; }}
.title-cell {{ max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

/* Group header */
.group-header {{ background: rgba(100,181,246,0.1); cursor: pointer; }}
.group-header:hover {{ background: rgba(100,181,246,0.2); }}
.group-cell {{ padding: 12px !important; font-size: 0.9rem; }}
.toggle-icon {{ display: inline-block; width: 20px; font-weight: bold; color: #64b5f6; }}

/* Impact colors */
.impact-positive {{ color: #4caf50; }}
.impact-negative {{ color: #f44336; }}
.impact-mixed {{ color: #ff9800; }}
.impact-unclear {{ color: #90a4ae; }}

/* Confidence bar */
.conf-bar {{ display: inline-block; width: 40px; height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; margin-right: 5px; vertical-align: middle; overflow: hidden; }}
.conf-bar span {{ display: block; height: 100%; border-radius: 2px; }}
.conf-high span {{ background: #4caf50; }}
.conf-med span {{ background: #ff9800; }}
.conf-low span {{ background: #f44336; }}

a {{ color: #64b5f6; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

.footer {{ text-align: center; color: #546e7a; font-size: 0.8rem; margin-top: 20px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.05); }}

/* Highlight search matches */
.highlight {{ background: yellow; color: black; padding: 0 2px; }}
</style>
</head>
<body>
<div class="container">
<h1>PAYMENTS INTELLIGENCE DASHBOARD</h1>
<div class="subtitle">{date_str} | Rolling {NEWS_LOOKBACK_DAYS} Days | {total_articles} Articles | Azure OpenAI</div>

<div class="stats">
    <div class="stat neutral"><div class="stat-value">{total_articles}</div><div class="stat-label">Total Articles</div></div>
    <div class="stat positive"><div class="stat-value">{positive}</div><div class="stat-label">Positive Impact</div></div>
    <div class="stat negative"><div class="stat-value">{negative}</div><div class="stat-label">Negative Impact</div></div>
    <div class="stat neutral"><div class="stat-value">{unique_naics}</div><div class="stat-label">NAICS Categories</div></div>
</div>

<div class="search-box">
    <input type="text" id="searchInput" placeholder="Search: NAICS code, impact, region, keyword..." onkeyup="searchTable()">
</div>

<div class="table-container">
<table id="newsTable">
<thead>
<tr>
    <th>NAICS</th>
    <th>Industry</th>
    <th>Date</th>
    <th>Region</th>
    <th>Title</th>
    <th>Source</th>
    <th>Impact</th>
    <th>Confidence</th>
    <th>Link</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>

<div class="footer">
    Generated {date_str} | Data stored in news_storage.json | Powered by Azure OpenAI
</div>
</div>

<script>
function toggleGroup(naicsCode) {{
    const rows = document.querySelectorAll('.naics-' + naicsCode);
    const icon = document.getElementById('icon-' + naicsCode);
    const isHidden = rows[0].style.display === 'none';

    rows.forEach(row => {{
        row.style.display = isHidden ? 'table-row' : 'none';
    }});

    icon.textContent = isHidden ? '-' : '+';
}}

function expandAll() {{
    document.querySelectorAll('.article-row').forEach(row => row.style.display = 'table-row');
    document.querySelectorAll('.toggle-icon').forEach(icon => icon.textContent = '-');
}}

function collapseAll() {{
    document.querySelectorAll('.article-row').forEach(row => row.style.display = 'none');
    document.querySelectorAll('.toggle-icon').forEach(icon => icon.textContent = '+');
}}

function searchTable() {{
    const input = document.getElementById('searchInput').value.toLowerCase();
    const rows = document.querySelectorAll('#newsTable tbody tr');

    if (input === '') {{
        // Reset to collapsed state
        collapseAll();
        document.querySelectorAll('.group-header').forEach(row => row.style.display = 'table-row');
        return;
    }}

    // Hide all group headers, show matching article rows
    document.querySelectorAll('.group-header').forEach(row => row.style.display = 'none');

    rows.forEach(row => {{
        if (row.classList.contains('article-row')) {{
            const text = row.textContent.toLowerCase();
            if (text.includes(input)) {{
                row.style.display = 'table-row';
            }} else {{
                row.style.display = 'none';
            }}
        }}
    }});
}}
</script>
</body>
</html>'''

    return html

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 65)
    print("  PAYMENTS INTELLIGENCE DASHBOARD v2")
    print("  Standalone Version - No pip required")
    print("=" * 65)

    date_str = datetime.now().strftime("%B %d, %Y")

    # Step 1: Load URLs from URL.docx
    print("\n[1/5] Loading URLs from URL.docx...")
    urls = []
    if URL_DOC.exists():
        urls = extract_urls_from_docx(URL_DOC)
        print(f"      Found {len(urls)} URLs")
    else:
        print(f"      [!] URL.docx not found at {URL_DOC}")
        print("      Using default sources...")
        urls = [
            "https://www.federalreserve.gov/feeds/press_all.xml",
            "https://www.consumerfinance.gov/about-us/newsroom/feed/",
            "https://www.pymnts.com/feed/",
            "https://www.paymentsdive.com/feeds/news/",
        ]

    # Load instructions
    instructions = ""
    if PROMPT_DOC.exists():
        instructions = extract_text_from_docx(PROMPT_DOC)
        print(f"      Loaded instructions: {len(instructions)} chars")

    # Step 2: Load existing storage
    storage = load_storage()
    print(f"      Existing storage: {len(storage.get('articles', []))} articles")

    # Step 3: Fetch new articles
    new_articles = fetch_all_news(urls)

    # Step 4: Add to storage (deduplicate)
    added, pruned = add_articles_to_storage(new_articles, storage)
    print(f"      Added {added} new articles, pruned {pruned} old articles")

    # Step 5: Tag articles with AI
    # Tag articles that don't have proper AI tags (including defaults like UNC, 522)
    def needs_tagging(article):
        naics = article.get('naics3', '')
        confidence = article.get('confidence', 0)
        impact = article.get('impact', '')
        # Needs tagging if: no naics, or default values, or unclassified
        if not naics:
            return True
        if naics in ['UNC', '522'] and confidence <= 0.5:
            return True
        if impact in ['unclassified', 'unclear'] and confidence <= 0.5:
            return True
        return False

    untagged = [a for a in storage['articles'] if needs_tagging(a)]
    if untagged:
        tagged = tag_articles_with_ai(untagged)
        # Update storage with tagged articles
        for article in storage['articles']:
            for tagged_article in tagged:
                if article.get('url') == tagged_article.get('url'):
                    article.update(tagged_article)
                    break
    else:
        print("[3/5] All articles already tagged")

    # Save storage
    save_storage(storage)
    print(f"      Storage saved: {len(storage['articles'])} total articles")

    # Step 6: Generate dashboard
    print("\n[4/5] Generating dashboard...")
    html = generate_dashboard(storage['articles'], date_str)

    # Step 7: Save HTML
    print("[5/5] Saving files...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"      Dashboard: {OUTPUT_FILE}")
    print(f"      Storage:   {STORAGE_FILE}")

    print("\n" + "=" * 65)
    print("  DONE!")
    print(f"  Open {OUTPUT_FILE.name} in your browser")
    print("=" * 65)

if __name__ == "__main__":
    main()
