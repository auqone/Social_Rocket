# Social Rocket 🚀

Multi-platform social media automation tool with AI-powered content generation. Built for FSBOz real estate marketing but works for any content strategy.

## Features

### Platform Support
- ✅ **X (Twitter)** - Full implementation
- ✅ **LinkedIn** - Full implementation (great for B2B/real estate professionals)
- ✅ **Facebook** - Full implementation (largest real estate audience)
- ⏳ **Threads, Instagram, TikTok, Reddit, Quora** - Coming soon

### AI-Powered Content
- **Multi-provider AI** with automatic fallback (Anthropic Claude → OpenAI GPT-4 → Google Gemini)
- **FSBOz-specific presets** for real estate content:
  - FSBOz General (platform promotion)
  - Property Search (165+ filters feature)
  - Seller Tips (educational content)
  - Success Stories (social proof)
  - Market Updates (timely content)
- **Generic preset** for non-real estate content
- AI analyzes your images and generates:
  - Viral-worthy captions
  - Trending hashtags
  - SEO keywords

### Content Management
- **Creative Library** - Upload media once, reuse across posts
- **Visual Calendar** - See your content schedule at a glance
- **Queue System** - Schedule posts with optimal timing per platform
- **Post History** - Track what you posted with performance notes
- **Drag & Drop** - Easy media management

### Security & Credentials
Three options (in order of security):
1. **1Password CLI Integration** (most secure) - Auto-fetch from vault
2. **Environment Variables** (secure) - Use `.env` file
3. **Config file** (convenient) - Stored in `config.json`

### Safety Features
- **Dry Run Mode** (default) - Test without posting
- **Live Mode** - Real posting (clear warnings)
- **Undo Protection** - Confirmation before live posts

## Installation

```bash
# Clone/download this repository
cd social_rocket

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Configure credentials (choose one method):

# Option 1: 1Password CLI (recommended)
# - Install 1Password CLI
# - Enable "Connect with 1Password CLI" in 1Password settings
# - Store credentials in items named: "X (Twitter)", "LinkedIn", "Facebook"

# Option 2: Environment Variables
cp .env.example .env
# Edit .env with your credentials

# Option 3: Use the Settings dialog in the app (stores in config.json)
```

## Usage

```bash
python social_rocket.py
```

### Quick Start

1. **Add API Key** - Settings → AI tab → Add your Anthropic/OpenAI/Gemini key
2. **Add Creative** - Click "+ Add Creative" → Upload image
3. **Select Content Type** - Choose FSBOz preset or Generic
4. **AI Generate** - Content auto-generates from your image
5. **Choose Platforms** - Check X, LinkedIn, Facebook, etc.
6. **Schedule or Post** - Queue for later or post immediately

### Content Presets

Switch between presets to get optimized AI prompts:

- **FSBOz - General**: Platform promotion, commission savings angle
- **FSBOz - Property Search**: 165+ filters feature, buyer empowerment
- **FSBOz - Seller Tips**: Educational content, position as expert
- **FSBOz - Success Story**: Social proof, create FOMO
- **FSBOz - Market Update**: Timely market commentary with CTA
- **Generic**: Standard social media content

### Scheduling Best Times

Each platform has research-backed optimal posting times:
- **LinkedIn**: 7:30 AM, 12:00 PM, 5:00 PM (business hours)
- **Facebook**: 9:00 AM, 1:00 PM, 4:00 PM (mid-morning to afternoon)
- **X**: 9:00 AM, 12:00 PM, 5:00 PM (engagement peaks)

Customize in Settings → Best Times tab.

### Post History

Click "📊 History" to:
- Review all past posts
- See which platforms succeeded/failed
- Add performance notes (engagement, what worked)
- Track content patterns over time

## Security Best Practices

1. **Never commit `config.json`** - Already in `.gitignore`
2. **Use environment variables** for production
3. **Use 1Password CLI** for team environments
4. **Rotate API keys** if accidentally exposed
5. **Enable 2FA** on social accounts (may require manual login first)

## For FSBOz Marketing

This tool is optimized for FSBOz's real estate marketing strategy:

- **LinkedIn** targets real estate professionals, investors, and B2B audience
- **Facebook** reaches largest FSBO seller/buyer audience
- **X** for thought leadership and quick updates
- **Content presets** designed around FSBOz's value props:
  - Save commissions (6% = $15k on $250k home)
  - 165+ property search filters
  - Empowerment (sell/buy without agent pressure)
  - Educational content (position as expert)

### Recommended Posting Strategy

1. **3x per day minimum** across platforms
2. **Mix content types**:
   - 40% Seller Tips (educational)
   - 30% Property Search features
   - 20% Success Stories (social proof)
   - 10% Market Updates
3. **LinkedIn**: Focus on B2B, professional audience
4. **Facebook**: Direct to sellers/buyers, emotional triggers
5. **X**: Quick tips, market stats, engagement-focused

## Troubleshooting

### "LinkedIn security challenge detected"
- Log into LinkedIn manually in your browser first
- This verifies your device/IP for automation

### "Facebook 2FA required"
- Disable 2FA temporarily or log in manually first
- Facebook may need device verification

### "No API key configured"
- Add at least one AI provider key in Settings → AI tab
- Anthropic (Claude) is recommended for best results

### "1Password not available"
- Install 1Password CLI: `brew install --cask 1password-cli`
- Enable "Connect with 1Password CLI" in 1Password settings
- Ensure 1Password desktop app is running

## Development

Built with:
- **PyQt6** - Modern UI framework
- **Playwright** - Headless browser automation
- **Anthropic/OpenAI/Gemini** - AI content generation
- **Python 3.10+** - Core language

## License

Built for FSBOz by Nicholas Hanks with enhancements by Claude (Anthropic).

---

**Note**: This tool automates posting to social platforms. Use responsibly and comply with each platform's terms of service. Some platforms may restrict or ban accounts that use automation tools.
