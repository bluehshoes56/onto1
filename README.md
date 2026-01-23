# Payments Intelligence Dashboard Generator

Generates a CXO-ready HTML dashboard from live news sources using GPT analysis.

## Quick Start (Mac)

### 1. Install Python dependencies
```bash
cd /path/to/news
pip3 install -r requirements.txt
```

### 2. Set your OpenAI API key
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

Or add to `~/.zshrc` for persistence:
```bash
echo 'export OPENAI_API_KEY="sk-your-key-here"' >> ~/.zshrc
source ~/.zshrc
```

### 3. Run the generator
```bash
python3 generate_dashboard.py
```

### 4. Open the dashboard
```bash
open payments_dashboard.html
```

## Files

| File | Purpose |
|------|---------|
| `generate_dashboard.py` | Main script |
| `requirements.txt` | Python dependencies |
| `Prompt Claude.docx` | Tagging framework instructions |
| `URL.docx` | News source URLs |
| `payments_dashboard.html` | Generated output |

## Features

- Fetches live news from 7+ tier-1 sources
- Uses GPT-4o for intelligent tagging
- Generates executive-ready HTML dashboard
- Includes source links for each event
- Works offline with sample data (if no API key)

## Customization

Edit `NEWS_SOURCES` in `generate_dashboard.py` to add/remove sources:

```python
NEWS_SOURCES = [
    {"name": "Source Name", "url": "https://...", "category": "macro"},
    ...
]
```

## Troubleshooting

**"OPENAI_API_KEY not set"**
- Run: `export OPENAI_API_KEY="sk-..."`

**Connection errors**
- Check internet connection
- Some sites may block automated requests

**Missing dependencies**
- Run: `pip3 install -r requirements.txt`
