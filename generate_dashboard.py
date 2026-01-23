#!/usr/bin/env python3
"""
Payments Intelligence Dashboard Generator
==========================================
Microsoft Ecosystem Version

Uses:
- Azure OpenAI (GPT-4o) for analysis
- Semantic Kernel compatible structure
- Microsoft identity/authentication patterns

Usage:
    python generate_dashboard.py

Requirements:
    pip install -r requirements.txt

Environment Variables (Azure):
    AZURE_OPENAI_ENDPOINT     = "https://your-resource.openai.azure.com/"
    AZURE_OPENAI_API_KEY      = "your-api-key"
    AZURE_OPENAI_DEPLOYMENT   = "gpt-4o"  (your deployment name)
    AZURE_OPENAI_API_VERSION  = "2024-02-15-preview"  (optional)
"""

import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from dateutil.tz import tzutc

# Azure OpenAI via openai SDK
try:
    from openai import AzureOpenAI
    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    AZURE_OPENAI_AVAILABLE = False
    print("[!] openai package not installed. Install with: pip install openai")

# Optional: Semantic Kernel integration
try:
    import semantic_kernel as sk
    from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
    SEMANTIC_KERNEL_AVAILABLE = True
except ImportError:
    SEMANTIC_KERNEL_AVAILABLE = False


# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
OUTPUT_FILE = SCRIPT_DIR / "payments_dashboard.html"
PROMPT_DOC = SCRIPT_DIR / "Prompt Claude.docx"
URL_DOC = SCRIPT_DIR / "URL.docx"

# =============================================================================
# AZURE OPENAI CONFIGURATION
# =============================================================================
# Option 1: Enter your credentials directly here (easiest)
# Option 2: Or set environment variables (more secure for shared code)
# =============================================================================

AZURE_OPENAI_ENDPOINT = ""      # e.g., "https://yourcompany.openai.azure.com/"
AZURE_OPENAI_API_KEY = ""       # e.g., "abc123xyz..."
AZURE_OPENAI_DEPLOYMENT = ""    # e.g., "gpt-4o" or "gpt-4"

# =============================================================================
# Don't edit below this line - it uses your values above (or env variables)
# =============================================================================
AZURE_CONFIG = {
    "endpoint": AZURE_OPENAI_ENDPOINT or os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
    "api_key": AZURE_OPENAI_API_KEY or os.environ.get("AZURE_OPENAI_API_KEY", ""),
    "deployment": AZURE_OPENAI_DEPLOYMENT or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
    "api_version": os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
}

# Rolling Lookback Configuration
NEWS_LOOKBACK_DAYS = int(os.environ.get("NEWS_LOOKBACK_DAYS", "90"))

# News Sources (Tier-1) - with RSS feeds where available for better date filtering
NEWS_SOURCES = [
    {
        "name": "Federal Reserve",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases.htm",
        "rss": "https://www.federalreserve.gov/feeds/press_all.xml",
        "category": "fed"
    },
    {
        "name": "Treasury",
        "url": "https://home.treasury.gov/news/press-releases",
        "rss": None,
        "category": "macro"
    },
    {
        "name": "Visa Newsroom",
        "url": "https://usa.visa.com/about-visa/newsroom/press-releases.html",
        "rss": None,
        "category": "payment_network"
    },
    {
        "name": "CFPB",
        "url": "https://www.consumerfinance.gov/about-us/newsroom/",
        "rss": "https://www.consumerfinance.gov/about-us/newsroom/feed/",
        "category": "regulation"
    },
    {
        "name": "Payments Dive",
        "url": "https://www.paymentsdive.com",
        "rss": "https://www.paymentsdive.com/feeds/news/",
        "category": "competitive"
    },
    {
        "name": "PYMNTS",
        "url": "https://www.pymnts.com",
        "rss": "https://www.pymnts.com/feed/",
        "category": "competitive"
    },
    {
        "name": "Grocery Dive",
        "url": "https://www.grocerydive.com",
        "rss": "https://www.grocerydive.com/feeds/news/",
        "category": "merchant"
    },
]


# =============================================================================
# DOCUMENT EXTRACTION
# =============================================================================

def extract_text_from_docx(docx_path: Path) -> str:
    """Extract text content from a .docx file."""
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
        print(f"  [!] Error reading {docx_path}: {e}")
        return ""


# =============================================================================
# NEWS FETCHING (Rolling 90-day lookback with RSS support)
# =============================================================================

def get_cutoff_date() -> datetime:
    """Get the cutoff date based on lookback period."""
    return datetime.now() - timedelta(days=NEWS_LOOKBACK_DAYS)


def parse_date_safe(date_str: str) -> Optional[datetime]:
    """Safely parse a date string, returning None if unparseable."""
    if not date_str:
        return None
    try:
        parsed = date_parser.parse(date_str, fuzzy=True)
        # Remove timezone info for comparison
        if parsed.tzinfo:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except:
        return None


def fetch_rss_feed(rss_url: str, source_name: str, category: str, cutoff_date: datetime) -> List[Dict]:
    """Fetch and parse RSS feed, filtering by date."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    articles = []

    try:
        response = requests.get(rss_url, headers=headers, timeout=15)
        response.raise_for_status()

        # Parse RSS XML
        root = ET.fromstring(response.content)

        # Handle different RSS formats (RSS 2.0 and Atom)
        items = root.findall('.//item')  # RSS 2.0
        if not items:
            # Try Atom format
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            items = root.findall('.//atom:entry', ns)

        for item in items:
            # Extract title
            title_elem = item.find('title')
            if title_elem is None:
                title_elem = item.find('{http://www.w3.org/2005/Atom}title')
            title = title_elem.text if title_elem is not None else ""

            # Extract link
            link_elem = item.find('link')
            if link_elem is None:
                link_elem = item.find('{http://www.w3.org/2005/Atom}link')
                link = link_elem.get('href', '') if link_elem is not None else ""
            else:
                link = link_elem.text if link_elem.text else ""

            # Extract date (try multiple fields)
            date_str = None
            for date_field in ['pubDate', 'published', 'updated', 'dc:date',
                              '{http://www.w3.org/2005/Atom}published',
                              '{http://www.w3.org/2005/Atom}updated']:
                date_elem = item.find(date_field)
                if date_elem is not None and date_elem.text:
                    date_str = date_elem.text
                    break

            pub_date = parse_date_safe(date_str)

            # Extract description/summary
            desc_elem = item.find('description')
            if desc_elem is None:
                desc_elem = item.find('{http://www.w3.org/2005/Atom}summary')
            if desc_elem is None:
                desc_elem = item.find('{http://www.w3.org/2005/Atom}content')
            description = desc_elem.text if desc_elem is not None else ""

            # Clean HTML from description
            if description:
                soup = BeautifulSoup(description, 'lxml')
                description = soup.get_text(separator=' ', strip=True)

            # Filter by date (include if within lookback period or date unknown)
            if pub_date is None or pub_date >= cutoff_date:
                articles.append({
                    "title": title,
                    "url": link,
                    "published_at": pub_date.isoformat() if pub_date else None,
                    "description": description[:1000] if description else "",
                    "source": source_name,
                    "category": category
                })

    except Exception as e:
        print(f"      [!] RSS error for {source_name}: {e}")

    return articles


def fetch_webpage_with_dates(url: str, source_name: str, category: str, cutoff_date: datetime) -> Dict:
    """Fetch webpage content and extract articles with dates."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        articles = []

        # Try to find article elements with dates
        # Common patterns: <article>, <div class="article">, <li> with dates
        article_containers = soup.find_all(['article', 'div', 'li'],
                                           class_=re.compile(r'article|post|news|release|item', re.I))

        for container in article_containers[:50]:  # Limit to 50 items
            # Find title (usually in h2, h3, or a tags)
            title_elem = container.find(['h2', 'h3', 'h4', 'a'])
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Find link
            link_elem = container.find('a', href=True)
            link = link_elem['href'] if link_elem else ""
            if link and link.startswith('/'):
                from urllib.parse import urljoin
                link = urljoin(url, link)

            # Find date (look for time tags, date classes, or date patterns)
            date_str = None

            # Try <time> element
            time_elem = container.find('time')
            if time_elem:
                date_str = time_elem.get('datetime') or time_elem.get_text(strip=True)

            # Try elements with date-related classes
            if not date_str:
                date_elem = container.find(class_=re.compile(r'date|time|published', re.I))
                if date_elem:
                    date_str = date_elem.get_text(strip=True)

            # Try to find date pattern in text
            if not date_str:
                text = container.get_text()
                date_patterns = [
                    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}',
                    r'\d{1,2}/\d{1,2}/\d{4}',
                    r'\d{4}-\d{2}-\d{2}'
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, text, re.I)
                    if match:
                        date_str = match.group()
                        break

            pub_date = parse_date_safe(date_str)

            # Get description
            desc_elem = container.find(['p', 'div'], class_=re.compile(r'desc|summary|excerpt|teaser', re.I))
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            if title and len(title) > 10:
                # Filter by date
                if pub_date is None or pub_date >= cutoff_date:
                    articles.append({
                        "title": title[:200],
                        "url": link,
                        "published_at": pub_date.isoformat() if pub_date else None,
                        "description": description[:500],
                        "source": source_name,
                        "category": category
                    })

        # Also get full page text as fallback
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        full_text = soup.get_text(separator=' ', strip=True)
        full_text = re.sub(r'\s+', ' ', full_text)

        return {
            "articles": articles,
            "full_text": full_text[:8000],
            "source": source_name,
            "category": category
        }

    except Exception as e:
        print(f"      [!] Error fetching {url}: {e}")
        return {"articles": [], "full_text": "", "source": source_name, "category": category}


def fetch_all_news(sources: list) -> list:
    """Fetch news from all configured sources with 90-day rolling lookback."""
    cutoff_date = get_cutoff_date()

    print(f"\n[2/5] Fetching news (rolling {NEWS_LOOKBACK_DAYS}-day lookback)...")
    print(f"      Cutoff date: {cutoff_date.strftime('%Y-%m-%d')}")

    all_articles = []
    source_summaries = []

    for source in sources:
        print(f"    > {source['name']}...")

        articles = []

        # Try RSS feed first (more reliable for dates)
        if source.get('rss'):
            rss_articles = fetch_rss_feed(
                source['rss'],
                source['name'],
                source['category'],
                cutoff_date
            )
            if rss_articles:
                articles.extend(rss_articles)
                print(f"      RSS: {len(rss_articles)} articles within {NEWS_LOOKBACK_DAYS} days")

        # Also fetch webpage for additional context
        webpage_data = fetch_webpage_with_dates(
            source['url'],
            source['name'],
            source['category'],
            cutoff_date
        )

        if webpage_data['articles']:
            # Add webpage articles not already in RSS
            existing_urls = {a['url'] for a in articles}
            new_articles = [a for a in webpage_data['articles'] if a['url'] not in existing_urls]
            articles.extend(new_articles)
            print(f"      Web: {len(new_articles)} additional articles")

        # Create source summary
        if articles or webpage_data['full_text']:
            source_summaries.append({
                "source": source['name'],
                "url": source['url'],
                "category": source['category'],
                "articles": articles,
                "content": webpage_data['full_text'],
                "article_count": len(articles),
                "fetched_at": datetime.now().isoformat()
            })

        all_articles.extend(articles)

    # Summary
    total_articles = len(all_articles)
    dated_articles = len([a for a in all_articles if a.get('published_at')])

    print(f"\n      Summary: {total_articles} articles from {len(source_summaries)} sources")
    print(f"      With dates: {dated_articles} | Without dates: {total_articles - dated_articles}")

    return source_summaries


# =============================================================================
# AZURE OPENAI ANALYSIS
# =============================================================================

def create_analysis_prompt(news_items: list, instructions: str) -> str:
    """Create the prompt for Azure OpenAI analysis."""
    # Build news text from sources and their articles
    news_sections = []
    for item in news_items:
        section = f"SOURCE: {item['source']}\nCATEGORY: {item['category']}\n"

        # Add individual articles with dates
        if item.get('articles'):
            section += "ARTICLES:\n"
            for article in item['articles'][:10]:  # Limit to 10 articles per source
                date_str = article.get('published_at', 'Unknown date')
                section += f"  - [{date_str}] {article['title']}\n"
                section += f"    URL: {article['url']}\n"
                if article.get('description'):
                    section += f"    Summary: {article['description'][:200]}\n"

        # Add full text content as context
        if item.get('content'):
            section += f"\nFULL CONTENT:\n{item['content'][:2000]}"

        news_sections.append(section)

    news_text = "\n\n---\n\n".join(news_sections)

    return f"""You are a payments intelligence analyst. Analyze the following news and return a JSON object.

INSTRUCTIONS FROM FRAMEWORK:
{instructions[:4000]}

TODAY'S NEWS:
{news_text}

Return a JSON object with this exact structure:
{{
    "kpis": [
        {{"value": "+4.2%", "label": "Holiday Spend YoY", "type": "positive|negative|neutral|warning"}}
    ],
    "executive_summary": [
        {{"title": "...", "description": "...", "impact": "high|medium|positive|info", "badge": "...", "badge_type": "negative|positive|mixed|watch"}}
    ],
    "events": [
        {{
            "date": "Jan 19",
            "category": "regulation|macro|competitive|payment_network|merchant|geopolitics",
            "naics3": "522",
            "product": "...",
            "merchant": "...",
            "network": "...",
            "event_type": "...",
            "summary": "...",
            "impact": "positive|negative|mixed|unclear",
            "confidence": 0.85,
            "source_url": "https://..."
        }}
    ],
    "notes": [
        {{"title": "...", "description": "..."}}
    ]
}}

IMPORTANT: For each event, include source_url with the actual news article URL.
Focus on payments-relevant insights: spend, transaction volume, average ticket impacts.
Return ONLY valid JSON, no other text."""


def analyze_with_azure_openai(news_items: list, instructions: str) -> dict:
    """Use Azure OpenAI to analyze news items."""
    if not AZURE_OPENAI_AVAILABLE:
        print("[!] Azure OpenAI SDK not available. Using sample data.")
        return get_sample_analysis()

    endpoint = AZURE_CONFIG["endpoint"]
    api_key = AZURE_CONFIG["api_key"]
    deployment = AZURE_CONFIG["deployment"]

    if not endpoint or not api_key:
        print("[!] Azure OpenAI not configured. Using sample data.")
        print("    Set environment variables:")
        print("      AZURE_OPENAI_ENDPOINT")
        print("      AZURE_OPENAI_API_KEY")
        print("      AZURE_OPENAI_DEPLOYMENT")
        return get_sample_analysis()

    print(f"[3/5] Analyzing news with Azure OpenAI ({deployment})...")

    try:
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=AZURE_CONFIG["api_version"]
        )

        prompt = create_analysis_prompt(news_items, instructions)

        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "You are a senior payments data analyst. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4096
        )

        response_text = response.choices[0].message.content

        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            analysis = json.loads(json_match.group())
            print("    > Analysis complete")
            return analysis

    except Exception as e:
        print(f"    [!] Error in Azure OpenAI analysis: {e}")

    return get_sample_analysis()


def analyze_with_semantic_kernel(news_items: list, instructions: str) -> dict:
    """
    Alternative: Use Semantic Kernel for analysis.
    This provides a more structured approach compatible with Microsoft Agent Framework.
    """
    if not SEMANTIC_KERNEL_AVAILABLE:
        print("[!] Semantic Kernel not available. Falling back to direct Azure OpenAI.")
        return analyze_with_azure_openai(news_items, instructions)

    endpoint = AZURE_CONFIG["endpoint"]
    api_key = AZURE_CONFIG["api_key"]
    deployment = AZURE_CONFIG["deployment"]

    if not endpoint or not api_key:
        print("[!] Azure OpenAI not configured for Semantic Kernel.")
        return get_sample_analysis()

    print(f"[3/5] Analyzing news with Semantic Kernel + Azure OpenAI...")

    try:
        # Initialize Semantic Kernel
        kernel = sk.Kernel()

        # Add Azure OpenAI chat service
        kernel.add_service(
            AzureChatCompletion(
                deployment_name=deployment,
                endpoint=endpoint,
                api_key=api_key,
            )
        )

        prompt = create_analysis_prompt(news_items, instructions)

        # Execute prompt
        result = kernel.invoke_prompt(prompt)
        response_text = str(result)

        # Extract JSON
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            analysis = json.loads(json_match.group())
            print("    > Semantic Kernel analysis complete")
            return analysis

    except Exception as e:
        print(f"    [!] Semantic Kernel error: {e}")
        print("    [!] Falling back to direct Azure OpenAI...")
        return analyze_with_azure_openai(news_items, instructions)

    return get_sample_analysis()


# =============================================================================
# SAMPLE DATA (Fallback when no API configured)
# =============================================================================

def get_sample_analysis() -> dict:
    """Return sample analysis data when API is unavailable."""
    return {
        "kpis": [
            {"value": "+4.2%", "label": "Holiday Spend YoY", "type": "positive"},
            {"value": "$52.9M", "label": "FTC Enforcement", "type": "negative"},
            {"value": "70%", "label": "Banks Fraud Spend", "type": "warning"},
            {"value": "16", "label": "News Events Tracked", "type": "neutral"}
        ],
        "executive_summary": [
            {"title": "FTC Enforcement Action", "description": "Cliq (fka CardFlex) ordered to pay $52.9M - signals continued regulatory scrutiny on payment processors.", "impact": "high", "badge": "High Impact", "badge_type": "negative"},
            {"title": "Geopolitical Sanctions", "description": "Treasury targeted Houthi, Iranian, and fraud networks. Cross-border payment volumes face increased friction.", "impact": "medium", "badge": "Monitor", "badge_type": "mixed"},
            {"title": "Card Networks vs. Merchants", "description": "Visa and Mastercard pushing back on merchant fee complaints. Watch for regulatory intervention.", "impact": "medium", "badge": "Developing", "badge_type": "mixed"},
            {"title": "Holiday Spend Strong", "description": "Visa data: U.S. holiday spending up 4.2% YoY. Consumer resilience continues.", "impact": "positive", "badge": "Positive", "badge_type": "positive"},
            {"title": "Fraud Spend Rising", "description": "70% of banks increasing fraud prevention budgets. Higher OpEx but reduced loss rates.", "impact": "medium", "badge": "Mixed", "badge_type": "mixed"},
            {"title": "Grocery Inflation Watch", "description": "Beef and coffee driving December grocery price increases. Higher average ticket but volume pressure.", "impact": "medium", "badge": "Pressure", "badge_type": "negative"},
            {"title": "Visa Earnings Preview", "description": "Q1 FY2026 results due Jan 29. Watch payment volume growth and cross-border trends.", "impact": "info", "badge": "Earnings Watch", "badge_type": "watch"},
            {"title": "Stablecoin Infrastructure", "description": "Visa's stablecoin settlement launch marks meaningful step toward crypto-fiat integration.", "impact": "info", "badge": "Emerging", "badge_type": "watch"}
        ],
        "events": [
            {"date": "Jan 19", "category": "regulation", "naics3": "522", "product": "Payment Processing", "merchant": "Cliq", "network": "Multiple", "event_type": "Fraud Enforcement", "summary": "FTC orders $52.9M consumer refund", "impact": "negative", "confidence": 0.85, "source_url": "https://www.paymentsdive.com"},
            {"date": "Jan 16", "category": "geopolitics", "naics3": "522", "product": "Cross-border", "merchant": "Multiple", "network": "SWIFT", "event_type": "Sanctions", "summary": "Treasury sanctions Houthi networks", "impact": "mixed", "confidence": 0.75, "source_url": "https://home.treasury.gov/news/press-releases"},
            {"date": "Jan 15", "category": "competitive", "naics3": "522", "product": "Card Payments", "merchant": "Visa", "network": "Visa", "event_type": "Earnings", "summary": "Q1 FY2026 results due Jan 29", "impact": "unclear", "confidence": 0.90, "source_url": "https://usa.visa.com/about-visa/newsroom/press-releases.html"},
            {"date": "Jan 13", "category": "macro", "naics3": "522", "product": "Card Payments", "merchant": "Visa", "network": "Visa", "event_type": "Outlook", "summary": "2026 outlook: AI and trade reshaping economy", "impact": "mixed", "confidence": 0.70, "source_url": "https://usa.visa.com/about-visa/newsroom/press-releases.html"},
            {"date": "Jan 12", "category": "regulation", "naics3": "522", "product": "Consumer Lending", "merchant": "Multiple", "network": "Multiple", "event_type": "Regulation", "summary": "CFPB/DOJ withdraw fair lending statement", "impact": "mixed", "confidence": 0.70, "source_url": "https://www.consumerfinance.gov/about-us/newsroom/"},
            {"date": "Jan 19", "category": "payment_network", "naics3": "522", "product": "Card Acceptance", "merchant": "V/MA", "network": "Visa/MC", "event_type": "Pricing", "summary": "Networks rebuff merchant fee complaints", "impact": "negative", "confidence": 0.75, "source_url": "https://www.paymentsdive.com"},
            {"date": "Jan 19", "category": "competitive", "naics3": "522", "product": "B2B Payments", "merchant": "MC", "network": "Mastercard", "event_type": "Product", "summary": "Embedded payments for commercial", "impact": "positive", "confidence": 0.70, "source_url": "https://www.pymnts.com"},
            {"date": "Jan 19", "category": "merchant", "naics3": "522", "product": "Fraud Prevention", "merchant": "Banks", "network": "Multiple", "event_type": "Expansion", "summary": "70% of banks increase fraud spend", "impact": "mixed", "confidence": 0.80, "source_url": "https://www.pymnts.com"},
            {"date": "Dec 23", "category": "macro", "naics3": "441-454", "product": "Holiday Retail", "merchant": "Multiple", "network": "Visa", "event_type": "Data", "summary": "U.S. holiday spending +4.2% YoY", "impact": "positive", "confidence": 0.90, "source_url": "https://usa.visa.com/about-visa/newsroom/press-releases.html"},
            {"date": "Dec 16", "category": "payment_network", "naics3": "522", "product": "Stablecoin", "merchant": "Visa", "network": "Visa", "event_type": "Product", "summary": "Visa launches stablecoin settlement", "impact": "positive", "confidence": 0.75, "source_url": "https://usa.visa.com/about-visa/newsroom/press-releases.html"},
            {"date": "Jan 19", "category": "macro", "naics3": "445", "product": "Fresh Food", "merchant": "Grocers", "network": "Multiple", "event_type": "Pricing", "summary": "Beef and coffee driving inflation", "impact": "negative", "confidence": 0.80, "source_url": "https://www.grocerydive.com"},
            {"date": "Jan 19", "category": "competitive", "naics3": "445", "product": "Grocery Retail", "merchant": "Walmart", "network": "Multiple", "event_type": "Expansion", "summary": "AI scaling from pilot to transformation", "impact": "mixed", "confidence": 0.75, "source_url": "https://www.grocerydive.com"},
            {"date": "Jan 19", "category": "competitive", "naics3": "445", "product": "Grocery Retail", "merchant": "Albertsons", "network": "Multiple", "event_type": "Earnings", "summary": "CEO pushes for higher valuation", "impact": "unclear", "confidence": 0.60, "source_url": "https://www.grocerydive.com"}
        ],
        "notes": [
            {"title": "FTC - Cliq Enforcement", "description": "Payment processor ordered to refund $52.9M. Affects NAICS 522. May cause merchant churn and processor consolidation."},
            {"title": "Treasury Sanctions", "description": "Multiple enforcement actions targeting Houthi, Iran, and domestic fraud networks. Impacts wire/SWIFT volumes."},
            {"title": "Visa Q1 Earnings", "description": "Results Jan 29. Prior holiday data (+4.2%) suggests resilient volumes. Watch cross-border commentary."},
            {"title": "Merchant Fee Dispute", "description": "Visa/Mastercard rejecting merchant complaints. Interchange economics remain contested."},
            {"title": "Grocery Inflation", "description": "NAICS 445 affected by beef/coffee prices. Average ticket rising; unit volume may decline."},
            {"title": "Bank Fraud Spending", "description": "70% of banks increasing fraud budgets. Positive for loss reduction."},
            {"title": "Stablecoin Settlement", "description": "Visa launched U.S. stablecoin settlement Dec 2025. New payment rail emerging."},
            {"title": "Confidence Scoring", "description": "0.9 = high (direct announcement), 0.7 = moderate (implied), 0.6 = low (uncertain)."}
        ]
    }


# =============================================================================
# HTML DASHBOARD GENERATION
# =============================================================================

def generate_html_dashboard(analysis: dict, generated_date: str) -> str:
    """Generate the HTML dashboard from analysis data."""

    # KPI cards
    kpi_html = ""
    for kpi in analysis.get("kpis", []):
        kpi_html += f'''
            <div class="kpi-card {kpi.get('type', 'neutral')}">
                <div class="value">{kpi['value']}</div>
                <div class="label">{kpi['label']}</div>
            </div>'''

    # Executive summary cards
    summary_html = ""
    impact_map = {"high": "high-impact", "medium": "medium-impact", "positive": "positive-impact", "info": "info"}
    for item in analysis.get("executive_summary", []):
        impact_class = impact_map.get(item.get('impact', 'info'), 'info')
        summary_html += f'''
                <div class="summary-card {impact_class}">
                    <h3>{item['title']}</h3>
                    <p>{item['description']}</p>
                    <span class="impact-badge {item.get('badge_type', 'watch')}">{item.get('badge', 'Info')}</span>
                </div>'''

    # Events table rows
    events_html = ""
    for event in analysis.get("events", []):
        impact_class = f"impact-{event.get('impact', 'unclear')}"
        impact_symbol = {"positive": "^", "negative": "v", "mixed": "*", "unclear": "o"}.get(event.get('impact'), 'o')
        conf = event.get('confidence', 0.5)
        conf_class = "confidence-high" if conf >= 0.8 else "confidence-med" if conf >= 0.65 else "confidence-low"
        source_url = event.get('source_url', '#')

        events_html += f'''
                            <tr>
                                <td>{event.get('date', '')}</td>
                                <td><span class="tag tag-category">{event.get('category', '').replace('_', ' ').title()}</span></td>
                                <td><span class="tag tag-naics">{event.get('naics3', '')}</span></td>
                                <td>{event.get('product', '')}</td>
                                <td><span class="tag tag-merchant">{event.get('merchant', '')}</span></td>
                                <td><span class="tag tag-network">{event.get('network', '')}</span></td>
                                <td>{event.get('event_type', '')}</td>
                                <td>{event.get('summary', '')}</td>
                                <td class="{impact_class}">{impact_symbol} {event.get('impact', 'unclear').title()}</td>
                                <td><div class="confidence-bar {conf_class}"><div class="confidence-fill" style="width:{int(conf*100)}%"></div></div>{conf:.2f}</td>
                                <td><a href="{source_url}" target="_blank" class="source-link">Source</a></td>
                            </tr>'''

    # Notes
    notes_html = ""
    for note in analysis.get("notes", []):
        notes_html += f'''
                <div class="note-item">
                    <h4>{note['title']}</h4>
                    <p>{note['description']}</p>
                </div>'''

    # Full HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payments Intelligence Dashboard | {generated_date}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #0a1628 0%, #1a2744 100%);
            min-height: 100vh;
            color: #e4e9f0;
            line-height: 1.6;
        }}
        .container {{ max-width: 1500px; margin: 0 auto; padding: 30px; }}
        .header {{
            text-align: center;
            padding: 40px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 40px;
        }}
        .header h1 {{ font-size: 2.5rem; font-weight: 300; color: #fff; letter-spacing: 2px; margin-bottom: 10px; }}
        .header .subtitle {{ color: #64b5f6; font-size: 1.1rem; font-weight: 400; }}
        .header .date {{ color: #90a4ae; font-size: 0.95rem; margin-top: 8px; }}
        .header .powered-by {{ color: #546e7a; font-size: 0.8rem; margin-top: 5px; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .kpi-card {{
            background: linear-gradient(145deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 25px;
            text-align: center;
            transition: transform 0.3s, box-shadow 0.3s;
        }}
        .kpi-card:hover {{ transform: translateY(-5px); box-shadow: 0 20px 40px rgba(0,0,0,0.3); }}
        .kpi-card .value {{ font-size: 2.2rem; font-weight: 600; margin-bottom: 8px; }}
        .kpi-card .label {{ color: #90a4ae; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; }}
        .kpi-card.positive .value {{ color: #4caf50; }}
        .kpi-card.negative .value {{ color: #f44336; }}
        .kpi-card.neutral .value {{ color: #64b5f6; }}
        .kpi-card.warning .value {{ color: #ff9800; }}
        .section {{ margin-bottom: 40px; }}
        .section-header {{ display: flex; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #64b5f6; }}
        .section-header h2 {{ font-size: 1.4rem; font-weight: 500; color: #fff; }}
        .section-header .icon {{
            width: 36px; height: 36px;
            background: linear-gradient(135deg, #64b5f6, #1976d2);
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            margin-right: 15px; font-size: 1rem; color: #fff;
        }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }}
        .summary-card {{
            background: linear-gradient(145deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 20px;
            position: relative;
            overflow: hidden;
        }}
        .summary-card::before {{ content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; }}
        .summary-card.high-impact::before {{ background: #f44336; }}
        .summary-card.medium-impact::before {{ background: #ff9800; }}
        .summary-card.positive-impact::before {{ background: #4caf50; }}
        .summary-card.info::before {{ background: #64b5f6; }}
        .summary-card h3 {{ font-size: 1rem; font-weight: 600; color: #fff; margin-bottom: 10px; }}
        .summary-card p {{ font-size: 0.9rem; color: #b0bec5; }}
        .impact-badge {{
            display: inline-block; padding: 3px 10px; border-radius: 20px;
            font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
            letter-spacing: 0.5px; margin-top: 12px;
        }}
        .impact-badge.negative {{ background: rgba(244,67,54,0.2); color: #f44336; }}
        .impact-badge.positive {{ background: rgba(76,175,80,0.2); color: #4caf50; }}
        .impact-badge.mixed {{ background: rgba(255,152,0,0.2); color: #ff9800; }}
        .impact-badge.watch {{ background: rgba(100,181,246,0.2); color: #64b5f6; }}
        .table-container {{
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.08);
        }}
        .table-scroll {{ overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
        th {{
            background: rgba(100,181,246,0.15);
            color: #64b5f6;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.5px;
            padding: 16px 12px;
            text-align: left;
            white-space: nowrap;
        }}
        td {{ padding: 14px 12px; border-bottom: 1px solid rgba(255,255,255,0.05); color: #cfd8dc; }}
        tr:hover td {{ background: rgba(255,255,255,0.03); }}
        .tag {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 500; margin: 2px; }}
        .tag-naics {{ background: rgba(156,39,176,0.2); color: #ce93d8; }}
        .tag-network {{ background: rgba(0,150,136,0.2); color: #80cbc4; }}
        .tag-merchant {{ background: rgba(255,193,7,0.2); color: #ffd54f; }}
        .tag-category {{ background: rgba(33,150,243,0.2); color: #64b5f6; }}
        .confidence-bar {{ width: 60px; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; display: inline-block; vertical-align: middle; margin-right: 8px; }}
        .confidence-fill {{ height: 100%; border-radius: 3px; }}
        .confidence-high .confidence-fill {{ background: #4caf50; }}
        .confidence-med .confidence-fill {{ background: #ff9800; }}
        .confidence-low .confidence-fill {{ background: #f44336; }}
        .impact-positive {{ color: #4caf50; }}
        .impact-negative {{ color: #f44336; }}
        .impact-mixed {{ color: #ff9800; }}
        .impact-unclear {{ color: #90a4ae; }}
        .source-link {{ color: #64b5f6; text-decoration: none; font-size: 0.8rem; padding: 4px 8px; border-radius: 4px; background: rgba(100,181,246,0.1); transition: background 0.2s; }}
        .source-link:hover {{ background: rgba(100,181,246,0.25); }}
        .footer {{ text-align: center; padding: 30px; color: #546e7a; font-size: 0.85rem; border-top: 1px solid rgba(255,255,255,0.05); margin-top: 40px; }}
        .notes-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px; }}
        .note-item {{ background: rgba(255,255,255,0.03); border-radius: 10px; padding: 15px; border-left: 3px solid #64b5f6; }}
        .note-item h4 {{ font-size: 0.9rem; color: #64b5f6; margin-bottom: 8px; }}
        .note-item p {{ font-size: 0.82rem; color: #90a4ae; }}
        @media print {{
            body {{ background: #fff; color: #333; }}
            .kpi-card, .summary-card, .table-container, .note-item {{ border: 1px solid #ddd; background: #f9f9f9; }}
            .section-header {{ border-color: #333; }}
            .source-link {{ color: #1976d2; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>PAYMENTS INTELLIGENCE</h1>
            <div class="subtitle">Macro, Competitive & Network Analytics</div>
            <div class="date">{generated_date} | Daily Briefing</div>
            <div class="powered-by">Powered by Azure OpenAI + Semantic Kernel</div>
        </header>
        <div class="kpi-grid">{kpi_html}
        </div>
        <section class="section">
            <div class="section-header">
                <div class="icon">S</div>
                <h2>Executive Summary</h2>
            </div>
            <div class="summary-grid">{summary_html}
            </div>
        </section>
        <section class="section">
            <div class="section-header">
                <div class="icon">T</div>
                <h2>Event Detail Table</h2>
            </div>
            <div class="table-container">
                <div class="table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Category</th>
                                <th>NAICS3</th>
                                <th>Product</th>
                                <th>Merchant</th>
                                <th>Network</th>
                                <th>Event</th>
                                <th>Summary</th>
                                <th>Impact</th>
                                <th>Confidence</th>
                                <th>Source</th>
                            </tr>
                        </thead>
                        <tbody>{events_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
        <section class="section">
            <div class="section-header">
                <div class="icon">N</div>
                <h2>Analyst Notes</h2>
            </div>
            <div class="notes-grid">{notes_html}
            </div>
        </section>
        <footer class="footer">
            <p>Payments Intelligence Dashboard | Data Sources: Federal Reserve, Treasury, CFPB, Visa, Payments Dive, PYMNTS, Grocery Dive</p>
            <p style="margin-top:8px;">Generated {generated_date} | Microsoft Azure OpenAI | For internal use only</p>
        </footer>
    </div>
</body>
</html>'''

    return html


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution function."""
    print("=" * 60)
    print("  PAYMENTS INTELLIGENCE DASHBOARD GENERATOR")
    print("  Microsoft Azure OpenAI Edition")
    print("=" * 60)

    generated_date = datetime.now().strftime("%B %d, %Y")

    # Step 1: Load instructions
    print("\n[1/5] Loading instructions...")
    instructions = ""
    if PROMPT_DOC.exists():
        instructions = extract_text_from_docx(PROMPT_DOC)
        print(f"    > Loaded {len(instructions)} chars from Prompt Claude.docx")
    else:
        print(f"    > {PROMPT_DOC} not found, using defaults")

    # Step 2: Fetch news
    news_items = fetch_all_news(NEWS_SOURCES)

    # Step 3: Analyze with Azure OpenAI (or Semantic Kernel if available)
    use_semantic_kernel = os.environ.get("USE_SEMANTIC_KERNEL", "false").lower() == "true"

    if use_semantic_kernel and SEMANTIC_KERNEL_AVAILABLE:
        analysis = analyze_with_semantic_kernel(news_items, instructions)
    else:
        analysis = analyze_with_azure_openai(news_items, instructions)

    # Step 4: Generate HTML
    print("\n[4/5] Generating HTML dashboard...")
    html_content = generate_html_dashboard(analysis, generated_date)

    # Step 5: Write output
    print("[5/5] Saving dashboard...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"    > Dashboard saved to: {OUTPUT_FILE}")
    print("\n" + "=" * 60)
    print("  DONE! Open the HTML file in your browser.")
    print("=" * 60 + "\n")

    return str(OUTPUT_FILE)


if __name__ == "__main__":
    main()
