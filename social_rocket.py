import os
import sys
import json
import re
import threading
import time
import base64
import uuid
import random
import shutil
import subprocess
from datetime import datetime, timedelta

# Load .env file if it exists (for secure credential management)
try:
    from dotenv import load_dotenv
    load_dotenv()  # Loads .env file into environment variables
except ImportError:
    pass  # python-dotenv not installed, will use config.json or env vars directly

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QPlainTextEdit, QLineEdit, QTextEdit,
    QCheckBox, QStatusBar, QDialog, QFormLayout, QScrollArea,
    QFrame, QSizePolicy, QMessageBox, QTabWidget, QGroupBox, QComboBox,
    QCalendarWidget, QDateTimeEdit, QGridLayout, QSpinBox, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QMimeData, QDate, QDateTime, QTime
from PyQt6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QImage, QTextCharFormat, QColor, QBrush, QIcon

import schedule
from playwright.sync_api import sync_playwright

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# --------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_DIR = os.path.join(BASE_DIR, "queue")
POSTED_DIR = os.path.join(BASE_DIR, "posted")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
HISTORY_FILE = os.path.join(BASE_DIR, "post_history.json")
PROJECTS_FILE = os.path.join(BASE_DIR, "projects.json")

# Times to post (24h format)
POST_TIMES = ["07:00", "12:00", "17:00"]

# Default best posting times per platform (research-based)
DEFAULT_BEST_TIMES = {
    'X': ['09:00', '12:00', '17:00'],           # Tue-Thu mornings, lunch, evening
    'Threads': ['07:00', '12:00', '19:00'],     # Early morning, lunch, evening
    'LinkedIn': ['07:30', '12:00', '17:00'],    # Business hours, Tue-Thu
    'Reddit': ['06:00', '08:00', '12:00'],      # Early morning for US visibility
    'Facebook': ['09:00', '13:00', '16:00'],    # Mid-morning to afternoon
    'Instagram': ['11:00', '14:00', '19:00'],   # Lunch, afternoon, evening
    'TikTok': ['07:00', '12:00', '19:00'],      # Morning, lunch, evening
    'Quora': ['09:00', '11:00', '14:00'],       # Business hours
}

# All supported platforms
ALL_PLATFORMS = ['X', 'Threads', 'LinkedIn', 'Reddit', 'Facebook', 'Instagram', 'TikTok', 'Quora']

# Default content type templates (used when no project-specific ones exist)
DEFAULT_CONTENT_TYPES = {
    'general': {
        'name': 'General',
        'caption_prompt': 'Write a compelling social media caption that highlights the key value proposition. Keep it punchy and engaging (100-150 chars).',
        'hashtag_prompt': 'Generate 8-12 relevant hashtags mixing industry-specific terms and trending tags.',
        'keyword_prompt': 'Generate SEO keywords relevant to the content and industry.'
    },
    'educational': {
        'name': 'Educational / Tips',
        'caption_prompt': 'Write an educational caption with a helpful tip or insight. Use curiosity hooks. Be helpful, not salesy.',
        'hashtag_prompt': 'Generate hashtags focused on education, tips, and how-to content.',
        'keyword_prompt': 'Generate keywords: tips, how to, advice, guide, tutorial, best practices.'
    },
    'success_story': {
        'name': 'Success Story / Social Proof',
        'caption_prompt': 'Write an inspiring caption about success or achievement. Use social proof language. Create FOMO and credibility.',
        'hashtag_prompt': 'Generate hashtags: success, achievement, testimonial, results-focused tags.',
        'keyword_prompt': 'Generate keywords: success stories, testimonials, case study, results, achievements.'
    },
    'announcement': {
        'name': 'Announcement / News',
        'caption_prompt': 'Write a timely announcement or news update. Create urgency and include a call-to-action.',
        'hashtag_prompt': 'Generate hashtags: news, update, announcement, trending, breaking tags.',
        'keyword_prompt': 'Generate keywords: news, update, announcement, latest, new release.'
    }
}

# Platform colors (brand colors)
PLATFORM_COLORS = {
    'X': '#000000',           # Black
    'Threads': '#6B6B6B',     # Grey
    'LinkedIn': '#0A66C2',    # LinkedIn Blue
    'Reddit': '#FF4500',      # Reddit Orange
    'Facebook': '#1877F2',    # Facebook Blue
    'Instagram': '#E4405F',   # Instagram Pink
    'TikTok': '#00F2EA',      # TikTok Cyan
    'Quora': '#B92B27',       # Quora Red
}

# Supported media extensions
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.webm')
WEB_EXTENSIONS = ('.html', '.htm')
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + WEB_EXTENSIONS

# --- CREDENTIALS / PER-PLATFORM SETTINGS ---
X_USERNAME_OR_EMAIL = ""
X_PASSWORD = ""

REDDIT_USERNAME = ""
REDDIT_PASSWORD = ""
REDDIT_SUBREDDIT = "yoursubreddit"

FACEBOOK_EMAIL = ""
FACEBOOK_PASSWORD = ""
FACEBOOK_TARGET_URL = "https://www.facebook.com/yourpageorGroupURL"

LINKEDIN_EMAIL = ""
LINKEDIN_PASSWORD = ""

THREADS_USERNAME_OR_EMAIL = ""
THREADS_PASSWORD = ""


# --------------------------------------------------------------------
# CONFIG MANAGEMENT
# --------------------------------------------------------------------

def load_config():
    """
    Load configuration from JSON file with environment variable fallback.

    Environment variables take precedence over config.json for security.
    Supported env vars:
    - ANTHROPIC_API_KEY
    - OPENAI_API_KEY
    - GEMINI_API_KEY
    - X_USERNAME, X_PASSWORD
    - LINKEDIN_EMAIL, LINKEDIN_PASSWORD
    - FACEBOOK_EMAIL, FACEBOOK_PASSWORD
    etc.
    """
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            pass

    # Override with environment variables if they exist (more secure)
    env_mappings = {
        'ANTHROPIC_API_KEY': 'anthropic_key',
        'OPENAI_API_KEY': 'openai_key',
        'GEMINI_API_KEY': 'gemini_key',
        'X_USERNAME': 'x_username',
        'X_PASSWORD': 'x_password',
        'LINKEDIN_EMAIL': 'linkedin_email',
        'LINKEDIN_PASSWORD': 'linkedin_password',
        'FACEBOOK_EMAIL': 'facebook_email',
        'FACEBOOK_PASSWORD': 'facebook_password',
        'FACEBOOK_URL': 'facebook_url',
        'THREADS_USERNAME': 'threads_username',
        'THREADS_PASSWORD': 'threads_password',
        'REDDIT_USERNAME': 'reddit_username',
        'REDDIT_PASSWORD': 'reddit_password',
        'INSTAGRAM_USERNAME': 'instagram_username',
        'INSTAGRAM_PASSWORD': 'instagram_password',
    }

    for env_var, config_key in env_mappings.items():
        value = os.environ.get(env_var)
        if value:
            config[config_key] = value

    return config


def save_config(config):
    """Save configuration to JSON file."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def load_post_history():
    """Load post history from JSON file."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_post_history(history):
    """Save post history to JSON file."""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)


def add_to_history(post_data, platforms, result_info):
    """Add a completed post to history."""
    history = load_post_history()

    history_entry = {
        'id': post_data.get('id', str(uuid.uuid4())[:8]),
        'posted_at': datetime.now().isoformat(),
        'scheduled_time': post_data.get('scheduled_time', ''),
        'caption': post_data.get('caption', ''),
        'hashtags': post_data.get('hashtags', ''),
        'keywords': post_data.get('keywords', ''),
        'platforms': platforms,
        'result': result_info,
        'media_filename': os.path.basename(post_data.get('media_path', '')) if post_data.get('media_path') else '',
        'notes': '',  # User can add performance notes later
        'engagement': {}  # Can be manually updated with likes, comments, shares, etc.
    }

    history.insert(0, history_entry)  # Most recent first

    # Keep only last 500 posts
    history = history[:500]

    save_post_history(history)
    return history_entry


def load_projects():
    """Load projects from JSON file."""
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_projects(projects):
    """Save projects to JSON file."""
    with open(PROJECTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(projects, f, indent=2)


def create_default_projects():
    """Create default projects including FSBOz."""
    return [
        {
            'id': 'fsboz',
            'name': 'FSBOz',
            'industry': 'Real Estate',
            'sub_industry': 'FSBO Marketplace',
            'content_types': {
                'general': {
                    'name': 'General',
                    'caption_prompt': 'Write a compelling caption for FSBOz (For Sale By Owner marketplace). Focus on empowering homeowners to sell without agents, saving thousands in commissions. Use emotional triggers around financial freedom and control. Keep it punchy (100-150 chars).',
                    'hashtag_prompt': 'Generate 8-12 hashtags mixing: FSBO terms (#FSBO #ForSaleByOwner #SellYourHome), real estate (#RealEstate #HomeSelling #PropertySale), and money-saving (#NoCommission #SaveMoney #HomeOwner). Include 2-3 trending tags.',
                    'keyword_prompt': 'Generate SEO keywords for FSBO real estate: sell home without agent, for sale by owner, save realtor commission, list home yourself, FSBO listing, home selling tips.'
                },
                'property_search': {
                    'name': 'Property Search',
                    'caption_prompt': 'Write a caption promoting FSBOz Property Search with 165+ filters. Emphasize finding the perfect home without agent pressure. Highlight buyer empowerment and comprehensive search tools. Keep it engaging (100-150 chars).',
                    'hashtag_prompt': 'Generate hashtags for property search: #HouseHunting #HomeBuyer #PropertySearch #FindYourHome #DreamHome #RealEstateSearch #HomeShopping #BuyerMarket plus trending real estate tags.',
                    'keyword_prompt': 'Generate SEO keywords: property search, home search filters, find homes for sale, buy home without agent, house hunting tools, advanced property search, real estate listings.'
                },
                'seller_tips': {
                    'name': 'Seller Tips',
                    'caption_prompt': 'Write an educational caption with a FSBO selling tip. Position FSBOz as the expert resource. Use curiosity hooks like "Most sellers don\'t know..." or "The #1 mistake FSBO sellers make...". Be helpful, not salesy.',
                    'hashtag_prompt': 'Generate hashtags: #FSBOTips #HomeSelling #RealEstateTips #SellingSmart #HomeSellerTips #PropertyTips #FSBOSuccess plus 3-4 engagement hashtags.',
                    'keyword_prompt': 'Generate keywords: FSBO tips, how to sell home yourself, for sale by owner advice, home selling mistakes, FSBO pricing, home staging tips, sell house fast.'
                },
                'success_story': {
                    'name': 'Success Story',
                    'caption_prompt': 'Write an inspiring caption about FSBO success. Use social proof language: "Another homeowner just saved $X" or "Meet [Name] who sold in X days". Create FOMO and credibility.',
                    'hashtag_prompt': 'Generate hashtags: #FSBOSuccess #SoldByOwner #HomeownerWin #RealEstateSuccess #SavedThousands #FSBOWorks #SuccessStory plus celebration/achievement hashtags.',
                    'keyword_prompt': 'Generate keywords: FSBO success stories, sold by owner, FSBO testimonials, save realtor fees, successful home sale, FSBO case study.'
                },
                'market_update': {
                    'name': 'Market Update',
                    'caption_prompt': 'Write a timely caption about real estate market conditions that positions selling FSBO as smart in the current market. Use urgency without being pushy. Include a call-to-action.',
                    'hashtag_prompt': 'Generate hashtags: #RealEstateMarket #HousingMarket #MarketUpdate #RealEstate2024 #HomePrices #SellerMarket #BuyerMarket plus location and trending tags.',
                    'keyword_prompt': 'Generate keywords: real estate market, housing market trends, home prices, seller market, buyer market, best time to sell, market conditions.'
                }
            }
        },
        {
            'id': 'social_rocket',
            'name': 'Social Rocket',
            'industry': 'SaaS',
            'sub_industry': 'Social Media Automation',
            'content_types': {
                'general': {
                    'name': 'General',
                    'caption_prompt': 'Write a caption for Social Rocket (social media automation tool). Emphasize time savings, consistency, and growth. Target busy entrepreneurs and marketers.',
                    'hashtag_prompt': 'Generate hashtags: #SocialMediaAutomation #ContentMarketing #DigitalMarketing #MarketingTools #SocialMediaStrategy #GrowthHacking',
                    'keyword_prompt': 'Generate keywords: social media automation, content scheduling, social media management, automated posting, marketing tools.'
                },
                'feature': {
                    'name': 'Feature Highlight',
                    'caption_prompt': 'Highlight a specific Social Rocket feature (AI content generation, multi-platform posting, scheduling). Show how it solves a pain point.',
                    'hashtag_prompt': 'Generate hashtags: #ProductFeatures #SocialMediaTools #Automation #AIContentGeneration #MarketingAutomation',
                    'keyword_prompt': 'Generate keywords: AI content generation, multi-platform posting, social media scheduler, automated content creation.'
                }
            }
        }
    ]


# --------------------------------------------------------------------
# 1PASSWORD INTEGRATION
# --------------------------------------------------------------------

class OnePasswordHelper:
    """Helper class for retrieving credentials from 1Password."""

    @staticmethod
    def is_available():
        """Check if 1Password CLI is installed and can access desktop app."""
        try:
            # First check if op command exists
            result = subprocess.run(['op', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False

            # Try to list accounts - this works even without explicit signin if desktop app is running
            result = subprocess.run(['op', 'account', 'list'], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def get_credential(item_name, field_name=None):
        """
        Retrieve a credential from 1Password.

        Args:
            item_name: Name of the 1Password item (e.g., "X (Twitter)")
            field_name: Specific field to retrieve (e.g., "username", "password")
                       If None, returns the password field by default

        Returns:
            The credential value or None if not found
        """
        try:
            if field_name:
                # Get specific field
                cmd = ['op', 'item', 'get', item_name, '--field', field_name]
            else:
                # Get default password field
                cmd = ['op', 'item', 'get', item_name, '--field', 'password']

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                print(f"1Password error for {item_name}/{field_name}: {result.stderr}")
                return None
        except Exception as e:
            print(f"1Password exception: {e}")
            return None

    @staticmethod
    def get_credentials_for_platform(platform_name):
        """
        Get username and password for a platform from 1Password.

        Args:
            platform_name: Platform name (e.g., "X", "LinkedIn", "Facebook")

        Returns:
            Tuple of (username, password) or (None, None) if not found
        """
        # Map platform names to 1Password item names
        item_mapping = {
            'X': 'X (Twitter)',
            'Twitter': 'X (Twitter)',
            'LinkedIn': 'LinkedIn',
            'Facebook': 'Facebook',
            'Instagram': 'Instagram',
            'Threads': 'Threads',
            'Reddit': 'Reddit',
            'TikTok': 'TikTok',
            'Quora': 'Quora',
        }

        item_name = item_mapping.get(platform_name, platform_name)

        # Try to get username (could be 'username', 'email', or other fields)
        username = (OnePasswordHelper.get_credential(item_name, 'username') or
                   OnePasswordHelper.get_credential(item_name, 'email') or
                   OnePasswordHelper.get_credential(item_name, 'user'))

        password = OnePasswordHelper.get_credential(item_name, 'password')

        return username, password


# --------------------------------------------------------------------
# AI SERVICE
# --------------------------------------------------------------------

class AIService:
    """Service for generating captions, hashtags, and keywords using multiple AI providers."""

    def __init__(self):
        self.config = load_config()

    def reload_config(self):
        """Reload configuration from file."""
        self.config = load_config()

    def _get_provider_order(self):
        """Get the order of providers to try (primary first, then others)."""
        primary = self.config.get('primary_provider', 'Anthropic')
        all_providers = ['Anthropic', 'OpenAI', 'Gemini']

        # Put primary first, then others
        order = [primary]
        for p in all_providers:
            if p != primary:
                order.append(p)
        return order

    def _build_prompt(self, caption_prompt="", hashtag_prompt="", keyword_prompt=""):
        """Build the combined prompt for all providers using JSON format."""
        default_caption_prompt = "Write a viral, engaging social media caption that drives engagement. Use emotional triggers, be compelling and benefit-focused. Keep it concise (100-150 characters)."
        default_hashtag_prompt = "Generate 8-12 trending, viral-worthy hashtags focusing on buyer intent and engagement. Mix popular and niche hashtags."
        default_keyword_prompt = "Generate 7-10 SEO-optimized longtail keywords focusing on search intent, trending terms, and specific content attributes."

        final_caption_prompt = caption_prompt if caption_prompt.strip() else default_caption_prompt
        final_hashtag_prompt = hashtag_prompt if hashtag_prompt.strip() else default_hashtag_prompt
        final_keyword_prompt = keyword_prompt if keyword_prompt.strip() else default_keyword_prompt

        return f"""You are an expert social media content strategist specializing in creating viral, conversion-focused posts.

Analyze this image and generate optimized social media content:

1. **Caption**: {final_caption_prompt}
2. **Hashtags**: {final_hashtag_prompt}
3. **Keywords**: {final_keyword_prompt}

Focus on:
- Emotional triggers and storytelling
- Benefit-driven language (not just features)
- Viral-worthy, shareable content
- Platform-optimized formatting
- Trending topics and search terms

Respond ONLY with valid JSON in this exact format:
{{
  "caption": "Your compelling caption here",
  "hashtags": "#hashtag1 #hashtag2 #hashtag3 ...",
  "keywords": "keyword1, keyword2, keyword3, ..."
}}"""

    def _parse_response(self, response_text):
        """Parse the AI response into structured data using JSON extraction."""
        result = {'caption': '', 'hashtags': '', 'keywords': ''}

        try:
            # Try to extract JSON from the response (handles cases with extra text)
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                parsed_data = json.loads(json_match.group(0))
                result['caption'] = parsed_data.get('caption', '')
                result['hashtags'] = parsed_data.get('hashtags', '')
                result['keywords'] = parsed_data.get('keywords', '')
            else:
                # Fallback to line-by-line parsing for backwards compatibility
                for line in response_text.split('\n'):
                    line = line.strip()
                    if line.upper().startswith('CAPTION:'):
                        result['caption'] = line[8:].strip()
                    elif line.upper().startswith('HASHTAGS:'):
                        result['hashtags'] = line[9:].strip()
                    elif line.upper().startswith('KEYWORDS:'):
                        result['keywords'] = line[9:].strip()
        except (json.JSONDecodeError, Exception) as e:
            # If JSON parsing fails, try fallback parsing
            for line in response_text.split('\n'):
                line = line.strip()
                if line.upper().startswith('CAPTION:'):
                    result['caption'] = line[8:].strip()
                elif line.upper().startswith('HASHTAGS:'):
                    result['hashtags'] = line[9:].strip()
                elif line.upper().startswith('KEYWORDS:'):
                    result['keywords'] = line[9:].strip()

        return result

    def _prepare_image(self, media_path):
        """Prepare image data for API calls."""
        ext = os.path.splitext(media_path)[1].lower()

        if ext not in IMAGE_EXTENSIONS or ext == '.svg':
            return None, None

        try:
            with open(media_path, 'rb') as f:
                image_bytes = f.read()
                media_data = base64.standard_b64encode(image_bytes).decode('utf-8')

            if ext == '.png':
                media_type = 'image/png'
            elif ext in ('.jpg', '.jpeg'):
                media_type = 'image/jpeg'
            elif ext == '.gif':
                media_type = 'image/gif'
            elif ext == '.webp':
                media_type = 'image/webp'
            else:
                return None, None

            return media_data, media_type
        except Exception:
            return None, None

    def _call_anthropic(self, media_path, prompt):
        """Call Anthropic Claude API."""
        api_key = self.config.get('anthropic_key', '')
        if not api_key or not ANTHROPIC_AVAILABLE:
            return None, "Anthropic API key not configured"

        try:
            client = anthropic.Anthropic(api_key=api_key)
            media_data, media_type = self._prepare_image(media_path)

            if media_data and media_type:
                message = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=2000,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": media_data
                                    }
                                },
                                {"type": "text", "text": prompt}
                            ]
                        }
                    ]
                )
            else:
                filename = os.path.basename(media_path)
                message = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=2000,
                    messages=[
                        {
                            "role": "user",
                            "content": f"Generate social media content for a file named '{filename}'.\n\n{prompt}"
                        }
                    ]
                )

            return message.content[0].text, None
        except Exception as e:
            return None, f"Anthropic error: {e}"

    def _call_openai(self, media_path, prompt):
        """Call OpenAI GPT-4 Vision API."""
        api_key = self.config.get('openai_key', '')
        if not api_key or not OPENAI_AVAILABLE:
            return None, "OpenAI API key not configured"

        try:
            client = openai.OpenAI(api_key=api_key)
            media_data, media_type = self._prepare_image(media_path)

            if media_data and media_type:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{media_data}"
                                    }
                                },
                                {"type": "text", "text": prompt}
                            ]
                        }
                    ]
                )
            else:
                filename = os.path.basename(media_path)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": f"Generate social media content for a file named '{filename}'.\n\n{prompt}"
                        }
                    ]
                )

            return response.choices[0].message.content, None
        except Exception as e:
            return None, f"OpenAI error: {e}"

    def _call_gemini(self, media_path, prompt):
        """Call Google Gemini API."""
        api_key = self.config.get('gemini_key', '')
        if not api_key or not GEMINI_AVAILABLE:
            return None, "Gemini API key not configured"

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            media_data, media_type = self._prepare_image(media_path)

            if media_data and media_type and PIL_AVAILABLE:
                # Load image for Gemini
                image = Image.open(media_path)
                response = model.generate_content([prompt, image])
            else:
                filename = os.path.basename(media_path)
                response = model.generate_content(
                    f"Generate social media content for a file named '{filename}'.\n\n{prompt}"
                )

            return response.text, None
        except Exception as e:
            return None, f"Gemini error: {e}"

    def analyze_media(self, media_path, caption_prompt="", hashtag_prompt="", keyword_prompt=""):
        """
        Analyze media and generate caption, hashtags, and keywords.
        Uses fallback chain: tries primary provider first, then others if it fails.
        Returns: dict with 'caption', 'hashtags', 'keywords' keys
        """
        self.reload_config()

        prompt = self._build_prompt(caption_prompt, hashtag_prompt, keyword_prompt)
        provider_order = self._get_provider_order()

        errors = []

        for provider in provider_order:
            if provider == 'Anthropic':
                response, error = self._call_anthropic(media_path, prompt)
            elif provider == 'OpenAI':
                response, error = self._call_openai(media_path, prompt)
            elif provider == 'Gemini':
                response, error = self._call_gemini(media_path, prompt)
            else:
                continue

            if response:
                result = self._parse_response(response)

                # Validate that we got actual content
                if not result.get('caption') and not result.get('hashtags') and not result.get('keywords'):
                    errors.append(f"{provider}: Failed to parse response - no content extracted")
                    print(f"DEBUG: Failed to parse {provider} response:", response[:200])
                    continue

                result['provider'] = provider
                print(f"SUCCESS: Generated content using {provider}")
                return result
            else:
                errors.append(f"{provider}: {error}")
                print(f"ERROR: {provider} failed - {error}")

        # All providers failed
        error_msg = "All providers failed: " + "; ".join(errors)
        print(f"CRITICAL ERROR: {error_msg}")
        return {
            'caption': '',
            'hashtags': '',
            'keywords': '',
            'error': error_msg
        }


# --------------------------------------------------------------------
# PLATFORM POSTING FUNCTIONS
# --------------------------------------------------------------------

def post_to_x(text, image_path=None):
    """Log in to X/Twitter via Playwright and create a post."""
    config = load_config()
    username = config.get('x_username', '')
    password = config.get('x_password', '')

    # Try 1Password if credentials not in config
    if (not username or not password) and OnePasswordHelper.is_available():
        print("DEBUG: Attempting to fetch X credentials from 1Password...")
        op_username, op_password = OnePasswordHelper.get_credentials_for_platform('X')
        if op_username and op_password:
            username = op_username
            password = op_password
            print("DEBUG: Successfully retrieved X credentials from 1Password")
        else:
            print("DEBUG: Could not retrieve X credentials from 1Password")

    if not username or not password:
        return False, "X credentials not configured. Please set them in Settings or 1Password."

    browser = None
    # Path to store persistent browser session
    session_dir = os.path.join(BASE_DIR, ".browser_sessions", "x_session")
    os.makedirs(os.path.dirname(session_dir), exist_ok=True)

    try:
        with sync_playwright() as p:
            # Launch with persistent context to save login session
            print("DEBUG: Launching browser with persistent session...")
            context = p.chromium.launch_persistent_context(
                session_dir,
                headless=False,  # Change to True once working
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.pages[0] if context.pages else context.new_page()

            # Check if already logged in
            print("DEBUG: Checking if already logged in...")
            page.goto("https://x.com/home", timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Check if we're on the home page (logged in)
            is_logged_in = page.query_selector('a[data-testid="SideNav_NewPost_Button"]') is not None

            if not is_logged_in:
                print("DEBUG: Not logged in, navigating to login page...")
                page.goto("https://x.com/login", timeout=60000)
                page.wait_for_timeout(3000)

                # Try multiple selector strategies for username field
                try:
                    print("DEBUG: Looking for username field...")
                    # Wait for page to stabilize
                    page.wait_for_load_state("domcontentloaded", timeout=30000)

                    # Try multiple selectors
                    username_selectors = [
                        'input[autocomplete="username"]',
                        'input[name="text"]',
                        'input[type="text"]',
                        '[data-testid="ocfEnterTextTextInput"]'
                    ]

                    username_box = None
                    for selector in username_selectors:
                        print(f"DEBUG: Trying selector: {selector}")
                        try:
                            page.wait_for_selector(selector, timeout=5000, state="visible")
                            username_box = page.query_selector(selector)
                            if username_box:
                                print(f"DEBUG: Found username field with selector: {selector}")
                                break
                        except:
                            continue

                    if not username_box:
                        return False, "X login: username field not found with any selector. Page may have changed."

                    username_box.fill(username)
                    page.wait_for_timeout(1000)
                    username_box.press("Enter")
                    print("DEBUG: Username entered, waiting for next screen...")

                    # Check if X is asking for phone/email verification instead of password
                    page.wait_for_timeout(3000)

                    # Look for verification text fields (phone number or email)
                    verification_field = page.query_selector('input[data-testid="ocfEnterTextTextInput"]')
                    if verification_field:
                        print("DEBUG: X is requesting additional verification (phone/email). This automation cannot handle this.")
                        return False, "X login: Additional verification required. Please log into X manually in a browser first to verify your identity, then try again."
                except Exception as e:
                    return False, f"X login: username field error: {e}"

                # Password field - may need to wait longer or handle verification
                try:
                    print("DEBUG: Waiting for password field...")
                    page.wait_for_timeout(2000)  # Give the page time to transition

                    # Try multiple selectors for password
                    password_selectors = [
                        'input[name="password"]',
                        'input[type="password"]',
                        'input[autocomplete="current-password"]'
                    ]

                    password_box = None
                    for selector in password_selectors:
                        print(f"DEBUG: Trying password selector: {selector}")
                        try:
                            page.wait_for_selector(selector, timeout=10000, state="visible")
                            password_box = page.query_selector(selector)
                            if password_box:
                                print(f"DEBUG: Found password field with selector: {selector}")
                                break
                        except:
                            continue

                    if not password_box:
                        # Check if we hit a verification screen (phone/email verification)
                        page_content = page.content()
                        if "verif" in page_content.lower() or "unusual" in page_content.lower():
                            return False, "X login: Account verification required. Please log in manually via browser first to verify your account."

                        # Save screenshot for debugging
                        try:
                            screenshot_path = os.path.join(BASE_DIR, "debug_x_login.png")
                            page.screenshot(path=screenshot_path)
                            print(f"DEBUG: Saved screenshot to {screenshot_path}")
                        except:
                            pass

                        return False, "X login: password field not found. X may have changed their login flow or account needs verification."

                    password_box.fill(password)
                    page.wait_for_timeout(1000)
                    password_box.press("Enter")
                    print("DEBUG: Password entered, waiting for home page...")
                except Exception as e:
                    return False, f"X login: password field error: {e}"

                # Wait for successful login
                try:
                    page.wait_for_url("https://x.com/home", timeout=60000)
                    print("DEBUG: Successfully logged in to X")
                except Exception:
                    print("DEBUG: Didn't reach home URL, checking for home page elements...")
                    page.wait_for_load_state("networkidle", timeout=60000)
                    # Check if we're actually logged in by looking for post button
                    if not page.query_selector('a[data-testid="SideNav_NewPost_Button"]'):
                        return False, "X login: Could not verify successful login. Check credentials or account status."
            else:
                print("DEBUG: Already logged in! Using existing session.")

            # Find and click post button
            try:
                print("DEBUG: Looking for post composer...")
                page.wait_for_timeout(2000)

                post_button = page.query_selector('a[data-testid="SideNav_NewPost_Button"]')
                if post_button:
                    post_button.click()
                    page.wait_for_timeout(2000)
                else:
                    # Try clicking directly on composer
                    composer = page.query_selector('div[data-testid="tweetTextarea_0"]')
                    if composer:
                        composer.click()
                        page.wait_for_timeout(1000)
                    else:
                        return False, "X: Could not find post button or composer"

                print("DEBUG: Composer opened")
            except Exception as e:
                return False, f"X: could not open composer: {e}"

            # Fill in post text
            try:
                print("DEBUG: Filling in post text...")
                textarea = page.query_selector('div[data-testid="tweetTextarea_0"]')
                if not textarea:
                    return False, "X: composer textarea not found."
                textarea.fill(text)
                page.wait_for_timeout(1000)
                print("DEBUG: Text filled")
            except Exception as e:
                return False, f"X: error filling text: {e}"

            # Attach image if provided
            if image_path and os.path.exists(image_path):
                try:
                    print("DEBUG: Attaching image...")
                    file_input = page.query_selector('input[data-testid="fileInput"]')
                    if not file_input:
                        file_input = page.query_selector('input[type="file"]')
                    if file_input:
                        file_input.set_input_files(image_path)
                        page.wait_for_timeout(5000)  # Wait for upload
                        print("DEBUG: Image attached")
                except Exception as e:
                    return False, f"X: error attaching image: {e}"

            # Click post button
            try:
                print("DEBUG: Clicking post button...")
                btn = page.query_selector('button[data-testid="tweetButtonInline"]')
                if not btn:
                    btn = page.query_selector('button[data-testid="tweetButton"]')
                if not btn:
                    return False, "X: tweet button not found."

                btn.click()
                page.wait_for_timeout(5000)  # Wait for post to complete
                print("DEBUG: Post button clicked, post should be live")
            except Exception as e:
                return False, f"X: error clicking tweet button: {e}"

            return True, "Posted to X"
    except Exception as e:
        return False, f"X Playwright error: {e}"
    finally:
        # Close context (persistent context doesn't need browser.close())
        try:
            if context:
                context.close()
        except Exception:
            pass


def post_to_reddit(text, image_path=None):
    return False, "Reddit posting not implemented yet."


def post_to_facebook(text, image_path=None):
    """Log in to Facebook via Playwright and create a post."""
    config = load_config()
    email = config.get('facebook_email', '')
    password = config.get('facebook_password', '')
    target_url = config.get('facebook_url', '')

    # Try 1Password if credentials not in config
    if (not email or not password) and OnePasswordHelper.is_available():
        print("DEBUG: Attempting to fetch Facebook credentials from 1Password...")
        op_email, op_password = OnePasswordHelper.get_credentials_for_platform('Facebook')
        if op_email and op_password:
            email = op_email
            password = op_password
            print("DEBUG: Successfully retrieved Facebook credentials from 1Password")

    if not email or not password:
        return False, "Facebook credentials not configured. Please set them in Settings or 1Password."

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # Navigate to Facebook login
            page.goto("https://www.facebook.com/login", timeout=60000)

            try:
                # Fill login form
                page.wait_for_selector('#email', timeout=15000)
                page.fill('#email', email)
                page.fill('#pass', password)
                page.click('button[name="login"]')
            except Exception as e:
                return False, f"Facebook login form error: {e}"

            # Wait for redirect
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass

            # Check for login errors or security challenges
            if "checkpoint" in page.url or "login" in page.url:
                # Check if it's a 2FA or security check
                if page.query_selector('input[name="approvals_code"]'):
                    return False, "Facebook 2FA required. Please log in manually first."
                if "login" in page.url:
                    return False, "Facebook login failed. Check credentials."

            # Navigate to target (page, group, or personal feed)
            if target_url:
                page.goto(target_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)

            # Click on "What's on your mind?" or similar to open composer
            try:
                composer_triggers = [
                    '[aria-label*="What\'s on your mind"]',
                    '[aria-label*="Create a post"]',
                    'div[role="button"]:has-text("What\'s on your mind")',
                    'span:has-text("What\'s on your mind")',
                    '[data-pagelet="FeedComposer"] div[role="button"]'
                ]

                clicked = False
                for selector in composer_triggers:
                    try:
                        btn = page.query_selector(selector)
                        if btn:
                            btn.click()
                            clicked = True
                            break
                    except:
                        continue

                if not clicked:
                    # Try clicking anywhere that might open the composer
                    page.click('text="What\'s on your mind"', timeout=5000)

                page.wait_for_timeout(2000)
            except Exception as e:
                return False, f"Facebook: could not open post composer: {e}"

            # Wait for and fill the post editor
            try:
                editor_selectors = [
                    'div[contenteditable="true"][role="textbox"]',
                    'div[aria-label*="What\'s on your mind"][contenteditable="true"]',
                    'div[data-lexical-editor="true"]',
                    'form div[contenteditable="true"]'
                ]

                editor = None
                for selector in editor_selectors:
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                        editor = page.query_selector(selector)
                        if editor:
                            break
                    except:
                        continue

                if not editor:
                    return False, "Facebook: post editor not found."

                # Click and type into editor
                editor.click()
                page.wait_for_timeout(500)
                page.keyboard.type(text, delay=15)
                page.wait_for_timeout(1000)
            except Exception as e:
                return False, f"Facebook: error filling text: {e}"

            # Upload image if provided
            if image_path and os.path.exists(image_path):
                try:
                    # Click the photo/video button
                    photo_btn_selectors = [
                        '[aria-label*="Photo/video"]',
                        '[aria-label*="Add Photos"]',
                        'div[role="button"]:has-text("Photo/video")',
                        'input[type="file"][accept*="image"]'
                    ]

                    # Try to find and click photo button
                    for selector in photo_btn_selectors:
                        try:
                            btn = page.query_selector(selector)
                            if btn:
                                if selector.startswith('input'):
                                    # Direct file input
                                    btn.set_input_files(image_path)
                                else:
                                    btn.click()
                                break
                        except:
                            continue

                    page.wait_for_timeout(1000)

                    # Find file input and upload
                    file_input = page.query_selector('input[type="file"][accept*="image"]')
                    if file_input:
                        file_input.set_input_files(image_path)
                        page.wait_for_timeout(5000)  # Wait for upload
                except Exception as e:
                    print(f"Facebook: Image upload warning (continuing): {e}")

            # Click Post button
            try:
                post_btn_selectors = [
                    '[aria-label="Post"]',
                    'div[role="button"]:has-text("Post")',
                    'span:has-text("Post")',
                    'form button[type="submit"]'
                ]

                for selector in post_btn_selectors:
                    try:
                        btns = page.query_selector_all(selector)
                        for btn in btns:
                            # Make sure it's the actual post button, not a menu item
                            if btn.is_visible() and btn.is_enabled():
                                btn.click()
                                break
                        break
                    except:
                        continue

                page.wait_for_timeout(5000)
            except Exception as e:
                return False, f"Facebook: error clicking post button: {e}"

            return True, "Posted to Facebook"
    except Exception as e:
        return False, f"Facebook Playwright error: {e}"
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass


def post_to_linkedin(text, image_path=None):
    """Log in to LinkedIn via Playwright and create a post."""
    config = load_config()
    email = config.get('linkedin_email', '')
    password = config.get('linkedin_password', '')

    # Try 1Password if credentials not in config
    if (not email or not password) and OnePasswordHelper.is_available():
        print("DEBUG: Attempting to fetch LinkedIn credentials from 1Password...")
        op_email, op_password = OnePasswordHelper.get_credentials_for_platform('LinkedIn')
        if op_email and op_password:
            email = op_email
            password = op_password
            print("DEBUG: Successfully retrieved LinkedIn credentials from 1Password")

    if not email or not password:
        return False, "LinkedIn credentials not configured. Please set them in Settings or 1Password."

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # Visible for debugging
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            print("DEBUG: LinkedIn - Browser launched")

            # Navigate to LinkedIn login
            print("DEBUG: LinkedIn - Navigating to login page")
            page.goto("https://www.linkedin.com/login", timeout=60000)
            page.wait_for_timeout(2000)

            try:
                # Fill login form
                print("DEBUG: LinkedIn - Looking for login form")
                page.wait_for_selector('#username', timeout=15000)
                print("DEBUG: LinkedIn - Filling credentials")
                page.fill('#username', email)
                page.fill('#password', password)
                page.wait_for_timeout(500)
                print("DEBUG: LinkedIn - Clicking submit")
                page.click('button[type="submit"]')
            except Exception as e:
                return False, f"LinkedIn login form error: {e}"

            # Wait for redirect to feed
            try:
                print("DEBUG: LinkedIn - Waiting for feed page")
                page.wait_for_url("**/feed/**", timeout=30000)
                print("DEBUG: LinkedIn - Successfully logged in")
            except Exception:
                # Check if we're on a security challenge page
                print(f"DEBUG: LinkedIn - Current URL: {page.url}")
                if "checkpoint" in page.url or "challenge" in page.url:
                    return False, "LinkedIn security challenge detected. Please log in manually first to verify your device."
                # Don't wait for networkidle - LinkedIn feed never stops loading
                # Just wait for domcontentloaded which is faster and more reliable
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    print("DEBUG: LinkedIn - Page loaded (domcontentloaded)")
                except:
                    print("DEBUG: LinkedIn - Continuing anyway after URL check")
                    pass

            # Click "Start a post" button
            try:
                print("DEBUG: LinkedIn - Looking for 'Start a post' button")
                page.wait_for_timeout(2000)  # Give page time to load

                # LinkedIn's post button - try multiple selectors
                start_post_selectors = [
                    'button.share-box-feed-entry__trigger',
                    'button[aria-label*="Start a post"]',
                    '.share-box-feed-entry__trigger',
                    'div.share-box-feed-entry__top-bar button',
                    'button[data-control-name="share_to_linkedin"]'
                ]

                clicked = False
                for selector in start_post_selectors:
                    print(f"DEBUG: LinkedIn - Trying start post selector: {selector}")
                    try:
                        btn = page.query_selector(selector)
                        if btn and btn.is_visible():
                            print(f"DEBUG: LinkedIn - Found and clicking: {selector}")
                            btn.click()
                            clicked = True
                            break
                    except Exception as e:
                        print(f"DEBUG: LinkedIn - Selector failed: {selector} - {e}")
                        continue

                if not clicked:
                    # Try clicking on the "Start a post" text area directly
                    print("DEBUG: LinkedIn - Trying text selector")
                    page.click('text="Start a post"', timeout=5000)
                    clicked = True

                if clicked:
                    print("DEBUG: LinkedIn - Composer should be opening...")
                    page.wait_for_timeout(3000)
                else:
                    return False, "LinkedIn: Could not find 'Start a post' button"
            except Exception as e:
                print(f"DEBUG: LinkedIn - Composer open error: {e}")
                return False, f"LinkedIn: could not open post composer: {e}"

            # Wait for and fill the post editor
            try:
                print("DEBUG: LinkedIn - Looking for post editor")
                editor_selectors = [
                    'div.ql-editor[data-placeholder="What do you want to talk about?"]',
                    'div.ql-editor',
                    'div[role="textbox"][aria-label*="Text editor"]',
                    'div[contenteditable="true"]'
                ]

                editor = None
                for selector in editor_selectors:
                    print(f"DEBUG: LinkedIn - Trying editor selector: {selector}")
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                        editor = page.query_selector(selector)
                        if editor:
                            print(f"DEBUG: LinkedIn - Found editor: {selector}")
                            break
                    except Exception as e:
                        print(f"DEBUG: LinkedIn - Editor selector failed: {selector} - {e}")
                        continue

                if not editor:
                    return False, "LinkedIn: post editor not found."

                # Click and type into editor
                print("DEBUG: LinkedIn - Typing post text")
                editor.click()
                page.wait_for_timeout(500)
                page.keyboard.type(text, delay=10)
                page.wait_for_timeout(1000)
                print("DEBUG: LinkedIn - Text entered successfully")
            except Exception as e:
                print(f"DEBUG: LinkedIn - Text fill error: {e}")
                return False, f"LinkedIn: error filling text: {e}"

            print(f"DEBUG: LinkedIn - Checking for image: {image_path if image_path else 'None'}")
            print(f"DEBUG: LinkedIn - Image exists: {os.path.exists(image_path) if image_path else False}")

            # Upload image if provided
            if image_path and os.path.exists(image_path):
                try:
                    print(f"DEBUG: LinkedIn - Uploading image: {os.path.basename(image_path)}")
                    # Click the image/media button
                    media_btn_selectors = [
                        'button[aria-label*="Add a photo"]',
                        'button[aria-label*="Add media"]',
                        'button.share-creation-state__image-preview-button',
                        'button[data-test-icon="image-medium"]',
                        'li[data-test-sharing-add-image] button'
                    ]

                    clicked = False
                    for selector in media_btn_selectors:
                        print(f"DEBUG: LinkedIn - Trying media button: {selector}")
                        try:
                            btn = page.query_selector(selector)
                            if btn and btn.is_visible():
                                print(f"DEBUG: LinkedIn - Found media button: {selector}")
                                btn.click()
                                clicked = True
                                break
                        except Exception as e:
                            print(f"DEBUG: LinkedIn - Media button failed: {selector} - {e}")
                            continue

                    if not clicked:
                        print("DEBUG: LinkedIn - No media button found, trying file input directly")

                    page.wait_for_timeout(1500)

                    # Find file input and upload
                    print("DEBUG: LinkedIn - Looking for file input")
                    file_input = page.query_selector('input[type="file"][accept*="image"]')
                    if not file_input:
                        file_input = page.query_selector('input[type="file"]')

                    if file_input:
                        print(f"DEBUG: LinkedIn - Setting file: {image_path}")
                        file_input.set_input_files(image_path)
                        print("DEBUG: LinkedIn - Waiting for image to upload...")
                        page.wait_for_timeout(7000)  # Wait longer for upload
                        print("DEBUG: LinkedIn - Image should be uploaded")
                    else:
                        print("DEBUG: LinkedIn - WARNING: File input not found, posting without image")
                except Exception as e:
                    print(f"DEBUG: LinkedIn - Image upload error: {e}")
                    print("DEBUG: LinkedIn - Continuing without image")

            # Click Post button - NUCLEAR OPTION: Pure JavaScript
            try:
                print("DEBUG: LinkedIn - Looking for Post button")
                # Wait for image to fully upload - give it more time
                print("DEBUG: LinkedIn - Waiting 8 seconds for image upload to complete...")
                page.wait_for_timeout(8000)

                # STRATEGY: Use JavaScript to find and click the button directly
                # This bypasses ALL Playwright/DOM restrictions
                print("DEBUG: LinkedIn - Using JavaScript to find and click Post button...")

                click_script = """
                () => {
                    // Find all buttons
                    const buttons = Array.from(document.querySelectorAll('button'));

                    // Collect ALL button texts for debugging
                    const allButtonTexts = buttons.map(btn => btn.textContent.trim()).filter(t => t);

                    // Look for Post button by EXACT text match (not "Start a post")
                    let postButton = buttons.find(btn => {
                        const text = btn.textContent.trim().toLowerCase();
                        // Must be exactly "post", not "start a post" or other variations
                        return text === 'post';
                    });

                    // If not found by exact text, try by class (primary action button)
                    if (!postButton) {
                        postButton = document.querySelector('button.share-actions__primary-action');
                    }

                    // If not found, try by aria-label
                    if (!postButton) {
                        postButton = document.querySelector('button[aria-label="Post"]');
                    }

                    // Last resort: find button in share-actions area
                    if (!postButton) {
                        const shareActions = document.querySelector('.share-actions');
                        if (shareActions) {
                            const btns = shareActions.querySelectorAll('button');
                            postButton = Array.from(btns).find(btn =>
                                btn.textContent.trim().toLowerCase() === 'post'
                            );
                        }
                    }

                    if (postButton) {
                        // Remove disabled attribute forcefully
                        postButton.removeAttribute('disabled');
                        postButton.removeAttribute('aria-disabled');

                        // Trigger click event
                        postButton.click();

                        return {success: true, text: postButton.textContent.trim(), allButtons: allButtonTexts.slice(0, 20)};
                    }

                    return {success: false, error: 'Button not found', allButtons: allButtonTexts.slice(0, 20)};
                }
                """

                # Try up to 10 times with 2 second intervals
                clicked = False
                for attempt in range(10):
                    print(f"DEBUG: LinkedIn - JavaScript attempt {attempt + 1}/10")

                    result = page.evaluate(click_script)

                    if result.get('success'):
                        print(f"DEBUG: LinkedIn - JavaScript click SUCCESS! Button text: '{result.get('text')}'")
                        clicked = True
                        break
                    else:
                        print(f"DEBUG: LinkedIn - Attempt {attempt + 1} failed: {result.get('error')}")
                        if attempt == 0:  # Print all buttons on first attempt
                            print(f"DEBUG: LinkedIn - Available buttons: {result.get('allButtons', [])}")
                        if attempt < 9:  # Don't wait on last attempt
                            page.wait_for_timeout(2000)

                if clicked:
                    print("DEBUG: LinkedIn - Post button clicked via JavaScript!")
                    page.wait_for_timeout(5000)  # Wait for post to complete
                    print("DEBUG: LinkedIn - Post should be live!")
                else:
                    # Last resort - keyboard shortcut
                    print("DEBUG: LinkedIn - All attempts failed, trying Ctrl+Enter keyboard shortcut...")
                    page.keyboard.press('Control+Enter')
                    page.wait_for_timeout(5000)
                    print("DEBUG: LinkedIn - Posted via keyboard shortcut")

            except Exception as e:
                print(f"DEBUG: LinkedIn - Post button error: {e}")
                return False, f"LinkedIn: error clicking post button: {e}"

            return True, "Posted to LinkedIn"
    except Exception as e:
        return False, f"LinkedIn Playwright error: {e}"
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass


def post_to_threads(text, image_path=None):
    return False, "Threads posting not implemented yet."


def post_to_instagram(text, image_path=None):
    return False, "Instagram posting not implemented yet."


def post_to_tiktok(text, image_path=None):
    return False, "TikTok posting not implemented yet."


def post_to_quora(text, image_path=None):
    return False, "Quora posting not implemented yet."


# --------------------------------------------------------------------
# HISTORY DIALOG
# --------------------------------------------------------------------

class HistoryDialog(QDialog):
    """Dialog showing post history with performance tracking."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Post History")
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel("📊 Post History - Track Your Content Performance")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #4CAF50; margin-bottom: 10px;")
        layout.addWidget(header)

        info = QLabel("Review past posts and track engagement. Click any post to add performance notes.")
        info.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 10px;")
        layout.addWidget(info)

        # Scroll area for history
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(10)

        # Load history
        history = load_post_history()

        if not history:
            empty_label = QLabel("No posts in history yet. Posts will appear here after they're published.")
            empty_label.setStyleSheet("color: #999; font-style: italic; padding: 40px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scroll_layout.addWidget(empty_label)
        else:
            for entry in history:
                card = self.create_history_card(entry)
                scroll_layout.addWidget(card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def create_history_card(self, entry):
        """Create a card widget for a history entry."""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 10px;
            }
        """)

        card_layout = QHBoxLayout(card)

        # Left: Post info
        info_layout = QVBoxLayout()

        # Date/time
        posted_at = entry.get('posted_at', '')
        if posted_at:
            try:
                dt = datetime.fromisoformat(posted_at)
                time_label = QLabel(dt.strftime("%b %d, %Y at %I:%M %p"))
                time_label.setStyleSheet("font-weight: bold; color: #4CAF50; font-size: 12px;")
                info_layout.addWidget(time_label)
            except:
                pass

        # Caption preview
        caption = entry.get('caption', '')[:120]
        if len(entry.get('caption', '')) > 120:
            caption += '...'
        caption_label = QLabel(caption or "(No caption)")
        caption_label.setWordWrap(True)
        caption_label.setStyleSheet("font-size: 12px; color: #333; margin: 5px 0;")
        info_layout.addWidget(caption_label)

        # Platforms
        platforms = entry.get('platforms', [])
        if platforms:
            plat_row = QHBoxLayout()
            plat_label = QLabel("Platforms:")
            plat_label.setStyleSheet("font-size: 10px; color: #666;")
            plat_row.addWidget(plat_label)

            for platform in platforms:
                color = PLATFORM_COLORS.get(platform, '#333333')
                dot = QLabel()
                dot.setFixedSize(12, 12)
                dot.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
                dot.setToolTip(platform)
                plat_row.addWidget(dot)

            plat_row.addStretch()
            info_layout.addLayout(plat_row)

        # Results
        results = entry.get('result', {})
        if results:
            results_text = " | ".join([f"{p}: {'✓' if 'success' in v.lower() else '✗'}" for p, v in results.items()])
            results_label = QLabel(results_text)
            results_label.setStyleSheet("font-size: 10px; color: #666; margin-top: 5px;")
            info_layout.addWidget(results_label)

        card_layout.addLayout(info_layout, stretch=3)

        # Right: Performance notes (editable)
        notes_layout = QVBoxLayout()

        notes_label = QLabel("Performance Notes:")
        notes_label.setStyleSheet("font-size: 10px; color: #666; font-weight: bold;")
        notes_layout.addWidget(notes_label)

        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText("Add notes about engagement, what worked, etc...")
        notes_edit.setText(entry.get('notes', ''))
        notes_edit.setMaximumHeight(80)
        notes_edit.setStyleSheet("""
            QTextEdit {
                font-size: 10px;
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 4px;
            }
        """)

        # Save notes on text change
        def save_notes():
            history = load_post_history()
            for i, h in enumerate(history):
                if h.get('id') == entry.get('id'):
                    history[i]['notes'] = notes_edit.toPlainText()
                    save_post_history(history)
                    break

        notes_edit.textChanged.connect(save_notes)
        notes_layout.addWidget(notes_edit)

        card_layout.addLayout(notes_layout, stretch=2)

        return card


# --------------------------------------------------------------------
# SETTINGS DIALOG
# --------------------------------------------------------------------

class SettingsDialog(QDialog):
    """Dialog for configuring API keys and platform credentials."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # Tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # General Tab (Mode Toggle)
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        mode_group = QGroupBox("Posting Mode")
        mode_layout = QVBoxLayout(mode_group)

        # Mode selector with clear warning
        self.dry_run_radio = QPushButton("🧪 TEST MODE (Dry Run)")
        self.dry_run_radio.setCheckable(True)
        self.dry_run_radio.setStyleSheet("""
            QPushButton {
                background-color: #FF8C00;
                color: white;
                font-weight: bold;
                padding: 15px;
                border-radius: 8px;
                text-align: left;
                font-size: 14px;
            }
            QPushButton:checked {
                background-color: #2E7D32;
                border: 3px solid #1B5E20;
            }
        """)
        mode_layout.addWidget(self.dry_run_radio)

        dry_run_info = QLabel("✓ Safe for testing\n✓ No posts will be published\n✓ Actions are only logged")
        dry_run_info.setStyleSheet("color: #666; margin-left: 20px; margin-bottom: 10px; font-size: 12px;")
        mode_layout.addWidget(dry_run_info)

        self.live_mode_radio = QPushButton("🚀 LIVE MODE (Real Posting)")
        self.live_mode_radio.setCheckable(True)
        self.live_mode_radio.setStyleSheet("""
            QPushButton {
                background-color: #666;
                color: white;
                font-weight: bold;
                padding: 15px;
                border-radius: 8px;
                text-align: left;
                font-size: 14px;
            }
            QPushButton:checked {
                background-color: #D32F2F;
                border: 3px solid #B71C1C;
            }
        """)
        mode_layout.addWidget(self.live_mode_radio)

        live_info = QLabel("⚠️ Posts WILL be published to platforms\n⚠️ Actions CANNOT be undone\n⚠️ Use with caution!")
        live_info.setStyleSheet("color: #D32F2F; margin-left: 20px; font-weight: bold; font-size: 12px;")
        mode_layout.addWidget(live_info)

        # Make radio buttons mutually exclusive
        self.dry_run_radio.clicked.connect(lambda: self.set_mode_selection(True))
        self.live_mode_radio.clicked.connect(lambda: self.set_mode_selection(False))

        mode_layout.addStretch()
        general_layout.addWidget(mode_group)

        # 1Password Integration Status
        onepass_group = QGroupBox("🔐 1Password Integration")
        onepass_layout = QVBoxLayout(onepass_group)

        self.onepass_status_label = QLabel()
        self.update_1password_status()
        onepass_layout.addWidget(self.onepass_status_label)

        onepass_info = QLabel(
            "When 1Password CLI is available, credentials will be automatically\n"
            "retrieved from your vault. Item names should match platform names\n"
            "(e.g., 'X (Twitter)', 'LinkedIn', 'Facebook')."
        )
        onepass_info.setStyleSheet("color: #666; font-size: 11px; margin-top: 5px;")
        onepass_info.setWordWrap(True)
        onepass_layout.addWidget(onepass_info)

        test_1pass_btn = QPushButton("Test 1Password Connection")
        test_1pass_btn.clicked.connect(self.test_1password_connection)
        onepass_layout.addWidget(test_1pass_btn)

        general_layout.addWidget(onepass_group)
        general_layout.addStretch()

        tabs.addTab(general_tab, "⚙️ General")

        # AI Tab
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)

        # Primary provider selector
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Primary Provider:"))
        self.primary_provider = QComboBox()
        self.primary_provider.addItems(["Anthropic", "OpenAI", "Gemini"])
        provider_layout.addWidget(self.primary_provider)
        provider_layout.addStretch()
        ai_layout.addLayout(provider_layout)

        fallback_info = QLabel("Fallback order: Primary → Others (if primary fails)")
        fallback_info.setStyleSheet("color: gray; font-size: 11px; margin-bottom: 10px;")
        ai_layout.addWidget(fallback_info)

        # API Keys
        ai_form = QFormLayout()

        # Anthropic
        self.anthropic_key = QLineEdit()
        self.anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key.setPlaceholderText("sk-ant-...")
        ai_form.addRow("Anthropic API Key:", self.anthropic_key)

        # OpenAI
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key.setPlaceholderText("sk-...")
        ai_form.addRow("OpenAI API Key:", self.openai_key)

        # Gemini
        self.gemini_key = QLineEdit()
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key.setPlaceholderText("AI...")
        ai_form.addRow("Gemini API Key:", self.gemini_key)

        ai_layout.addLayout(ai_form)

        # Show/Hide toggle
        self.show_keys_btn = QPushButton("Show Keys")
        self.show_keys_btn.clicked.connect(self.toggle_key_visibility)
        ai_layout.addWidget(self.show_keys_btn)

        info = QLabel("API keys are stored locally in config.json")
        info.setStyleSheet("color: gray; font-size: 11px;")
        ai_layout.addWidget(info)
        ai_layout.addStretch()

        tabs.addTab(ai_tab, "AI")

        # Platforms Tab
        platforms_tab = QWidget()
        platforms_layout = QVBoxLayout(platforms_tab)

        # Scroll area for platforms
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # X / Twitter
        x_group = QGroupBox("X / Twitter")
        x_layout = QFormLayout(x_group)
        self.x_username = QLineEdit()
        self.x_username.setPlaceholderText("username or email")
        self.x_password = QLineEdit()
        self.x_password.setEchoMode(QLineEdit.EchoMode.Password)
        x_layout.addRow("Username/Email:", self.x_username)
        x_layout.addRow("Password:", self.x_password)
        scroll_layout.addWidget(x_group)

        # Threads
        threads_group = QGroupBox("Threads")
        threads_layout = QFormLayout(threads_group)
        self.threads_username = QLineEdit()
        self.threads_username.setPlaceholderText("username or email")
        self.threads_password = QLineEdit()
        self.threads_password.setEchoMode(QLineEdit.EchoMode.Password)
        threads_layout.addRow("Username/Email:", self.threads_username)
        threads_layout.addRow("Password:", self.threads_password)
        scroll_layout.addWidget(threads_group)

        # LinkedIn
        linkedin_group = QGroupBox("LinkedIn")
        linkedin_layout = QFormLayout(linkedin_group)
        self.linkedin_email = QLineEdit()
        self.linkedin_email.setPlaceholderText("email@example.com")
        self.linkedin_password = QLineEdit()
        self.linkedin_password.setEchoMode(QLineEdit.EchoMode.Password)
        linkedin_layout.addRow("Email:", self.linkedin_email)
        linkedin_layout.addRow("Password:", self.linkedin_password)
        scroll_layout.addWidget(linkedin_group)

        # Reddit
        reddit_group = QGroupBox("Reddit")
        reddit_layout = QFormLayout(reddit_group)
        self.reddit_username = QLineEdit()
        self.reddit_username.setPlaceholderText("username")
        self.reddit_password = QLineEdit()
        self.reddit_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.reddit_subreddit = QLineEdit()
        self.reddit_subreddit.setPlaceholderText("subreddit name (without r/)")
        reddit_layout.addRow("Username:", self.reddit_username)
        reddit_layout.addRow("Password:", self.reddit_password)
        reddit_layout.addRow("Subreddit:", self.reddit_subreddit)
        scroll_layout.addWidget(reddit_group)

        # Facebook
        facebook_group = QGroupBox("Facebook")
        facebook_layout = QFormLayout(facebook_group)
        self.facebook_email = QLineEdit()
        self.facebook_email.setPlaceholderText("email@example.com")
        self.facebook_password = QLineEdit()
        self.facebook_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.facebook_url = QLineEdit()
        self.facebook_url.setPlaceholderText("https://www.facebook.com/yourpage")
        facebook_layout.addRow("Email:", self.facebook_email)
        facebook_layout.addRow("Password:", self.facebook_password)
        facebook_layout.addRow("Page/Group URL:", self.facebook_url)
        scroll_layout.addWidget(facebook_group)

        # Instagram
        instagram_group = QGroupBox("Instagram")
        instagram_layout = QFormLayout(instagram_group)
        self.instagram_username = QLineEdit()
        self.instagram_username.setPlaceholderText("username")
        self.instagram_password = QLineEdit()
        self.instagram_password.setEchoMode(QLineEdit.EchoMode.Password)
        instagram_layout.addRow("Username:", self.instagram_username)
        instagram_layout.addRow("Password:", self.instagram_password)
        scroll_layout.addWidget(instagram_group)

        # TikTok
        tiktok_group = QGroupBox("TikTok")
        tiktok_layout = QFormLayout(tiktok_group)
        self.tiktok_username = QLineEdit()
        self.tiktok_username.setPlaceholderText("username")
        self.tiktok_password = QLineEdit()
        self.tiktok_password.setEchoMode(QLineEdit.EchoMode.Password)
        tiktok_layout.addRow("Username:", self.tiktok_username)
        tiktok_layout.addRow("Password:", self.tiktok_password)
        scroll_layout.addWidget(tiktok_group)

        # Quora
        quora_group = QGroupBox("Quora")
        quora_layout = QFormLayout(quora_group)
        self.quora_email = QLineEdit()
        self.quora_email.setPlaceholderText("email@example.com")
        self.quora_password = QLineEdit()
        self.quora_password.setEchoMode(QLineEdit.EchoMode.Password)
        quora_layout.addRow("Email:", self.quora_email)
        quora_layout.addRow("Password:", self.quora_password)
        scroll_layout.addWidget(quora_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        platforms_layout.addWidget(scroll)

        tabs.addTab(platforms_tab, "Platforms")

        # Best Times Tab
        times_tab = QWidget()
        times_layout = QVBoxLayout(times_tab)

        times_info = QLabel("Configure optimal posting times for each platform.\nThese are used when scheduling with 'Best Times' option.")
        times_info.setStyleSheet("color: gray; font-size: 11px; margin-bottom: 10px;")
        times_layout.addWidget(times_info)

        times_scroll = QScrollArea()
        times_scroll.setWidgetResizable(True)
        times_scroll_widget = QWidget()
        times_scroll_layout = QVBoxLayout(times_scroll_widget)

        self.best_times_inputs = {}

        for platform in ALL_PLATFORMS:
            group = QGroupBox(platform)
            group_layout = QVBoxLayout(group)

            # Three time slots
            self.best_times_inputs[platform] = []
            for i in range(3):
                time_row = QHBoxLayout()
                time_row.addWidget(QLabel(f"Time {i+1}:"))

                time_edit = QLineEdit()
                time_edit.setPlaceholderText("HH:MM (24h)")
                time_edit.setMaximumWidth(80)
                self.best_times_inputs[platform].append(time_edit)
                time_row.addWidget(time_edit)
                time_row.addStretch()

                group_layout.addLayout(time_row)

            times_scroll_layout.addWidget(group)

        times_scroll_layout.addStretch()
        times_scroll.setWidget(times_scroll_widget)
        times_layout.addWidget(times_scroll)

        # Reset to defaults button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_best_times)
        times_layout.addWidget(reset_btn)

        tabs.addTab(times_tab, "Best Times")

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # Load existing config
        self.load_settings()

    def reset_best_times(self):
        """Reset best times to defaults."""
        for platform, times in DEFAULT_BEST_TIMES.items():
            if platform in self.best_times_inputs:
                for i, time_val in enumerate(times):
                    if i < len(self.best_times_inputs[platform]):
                        self.best_times_inputs[platform][i].setText(time_val)

    def load_settings(self):
        """Load all settings from config."""
        config = load_config()

        # Mode (default to dry_run=True for safety)
        dry_run = config.get('dry_run', True)
        self.set_mode_selection(dry_run)

        # AI Provider
        provider = config.get('primary_provider', 'Anthropic')
        index = self.primary_provider.findText(provider)
        if index >= 0:
            self.primary_provider.setCurrentIndex(index)

        # AI Keys
        self.anthropic_key.setText(config.get('anthropic_key', ''))
        self.openai_key.setText(config.get('openai_key', ''))
        self.gemini_key.setText(config.get('gemini_key', ''))

        # X
        self.x_username.setText(config.get('x_username', ''))
        self.x_password.setText(config.get('x_password', ''))

        # Threads
        self.threads_username.setText(config.get('threads_username', ''))
        self.threads_password.setText(config.get('threads_password', ''))

        # LinkedIn
        self.linkedin_email.setText(config.get('linkedin_email', ''))
        self.linkedin_password.setText(config.get('linkedin_password', ''))

        # Reddit
        self.reddit_username.setText(config.get('reddit_username', ''))
        self.reddit_password.setText(config.get('reddit_password', ''))
        self.reddit_subreddit.setText(config.get('reddit_subreddit', ''))

        # Facebook
        self.facebook_email.setText(config.get('facebook_email', ''))
        self.facebook_password.setText(config.get('facebook_password', ''))
        self.facebook_url.setText(config.get('facebook_url', ''))

        # Instagram
        self.instagram_username.setText(config.get('instagram_username', ''))
        self.instagram_password.setText(config.get('instagram_password', ''))

        # TikTok
        self.tiktok_username.setText(config.get('tiktok_username', ''))
        self.tiktok_password.setText(config.get('tiktok_password', ''))

        # Quora
        self.quora_email.setText(config.get('quora_email', ''))
        self.quora_password.setText(config.get('quora_password', ''))

        # Best Times
        best_times = config.get('best_times', DEFAULT_BEST_TIMES)
        for platform, times in best_times.items():
            if platform in self.best_times_inputs:
                for i, time_val in enumerate(times):
                    if i < len(self.best_times_inputs[platform]):
                        self.best_times_inputs[platform][i].setText(time_val)

    def get_settings(self):
        """Get all settings as a dict."""
        # Collect best times
        best_times = {}
        for platform, inputs in self.best_times_inputs.items():
            times = []
            for inp in inputs:
                t = inp.text().strip()
                if t:
                    times.append(t)
            if times:
                best_times[platform] = times

        return {
            'dry_run': self.dry_run_radio.isChecked(),
            'primary_provider': self.primary_provider.currentText(),
            'anthropic_key': self.anthropic_key.text().strip(),
            'openai_key': self.openai_key.text().strip(),
            'gemini_key': self.gemini_key.text().strip(),
            'x_username': self.x_username.text().strip(),
            'x_password': self.x_password.text(),
            'threads_username': self.threads_username.text().strip(),
            'threads_password': self.threads_password.text(),
            'linkedin_email': self.linkedin_email.text().strip(),
            'linkedin_password': self.linkedin_password.text(),
            'reddit_username': self.reddit_username.text().strip(),
            'reddit_password': self.reddit_password.text(),
            'reddit_subreddit': self.reddit_subreddit.text().strip(),
            'facebook_email': self.facebook_email.text().strip(),
            'facebook_password': self.facebook_password.text(),
            'facebook_url': self.facebook_url.text().strip(),
            'instagram_username': self.instagram_username.text().strip(),
            'instagram_password': self.instagram_password.text(),
            'tiktok_username': self.tiktok_username.text().strip(),
            'tiktok_password': self.tiktok_password.text(),
            'quora_email': self.quora_email.text().strip(),
            'quora_password': self.quora_password.text(),
            'best_times': best_times,
        }

    def set_mode_selection(self, dry_run):
        """Set mode selection (mutually exclusive buttons)."""
        self.dry_run_radio.setChecked(dry_run)
        self.live_mode_radio.setChecked(not dry_run)

    def update_1password_status(self):
        """Update the 1Password status label."""
        if OnePasswordHelper.is_available():
            self.onepass_status_label.setText("✅ 1Password CLI is available and ready")
            self.onepass_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.onepass_status_label.setText("❌ 1Password CLI not available or not signed in")
            self.onepass_status_label.setStyleSheet("color: orange; font-weight: bold;")

    def test_1password_connection(self):
        """Test 1Password connection by attempting to retrieve X credentials."""
        if not OnePasswordHelper.is_available():
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("1Password Not Available")
            msg.setText("1Password CLI is installed but not connected to your desktop app.")
            msg.setInformativeText(
                "To enable 1Password integration:\n\n"
                "1. Open 1Password desktop app (not the website)\n"
                "2. Go to Settings → Developer tab\n"
                "3. Enable 'Connect with 1Password CLI'\n"
                "4. Restart Social Rocket\n\n"
                "This allows Social Rocket to securely access\n"
                "your credentials using biometric unlock."
            )
            open_btn = msg.addButton("Open 1Password Settings", QMessageBox.ButtonRole.ActionRole)
            msg.addButton(QMessageBox.StandardButton.Ok)
            msg.exec()

            if msg.clickedButton() == open_btn:
                # Open 1Password app settings
                subprocess.run(['open', '-a', '1Password', '--args', '--settings'])
            return

        # Test by trying to get X credentials
        username, password = OnePasswordHelper.get_credentials_for_platform('X')

        if username and password:
            QMessageBox.information(
                self,
                "1Password Test Successful",
                f"✅ Successfully retrieved X (Twitter) credentials!\n\n"
                f"Username: {username[:3]}{'*' * (len(username) - 3)}\n"
                f"Password: {'*' * len(password)}\n\n"
                f"1Password integration is working correctly."
            )
        else:
            QMessageBox.warning(
                self,
                "1Password Test Failed",
                "Could not retrieve X (Twitter) credentials from 1Password.\n\n"
                "Make sure you have an item named 'X (Twitter)' in your vault\n"
                "with 'username' and 'password' fields populated."
            )

    def toggle_key_visibility(self):
        if self.anthropic_key.echoMode() == QLineEdit.EchoMode.Password:
            self.anthropic_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.openai_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.gemini_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_keys_btn.setText("Hide Keys")
        else:
            self.anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_keys_btn.setText("Show Keys")


# --------------------------------------------------------------------
# CONTENT CALENDAR
# --------------------------------------------------------------------

class ContentCalendar(QCalendarWidget):
    """Calendar widget that shows scheduled posts."""

    date_selected_for_view = pyqtSignal(QDate)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scheduled_dates = {}  # {date_str: count}
        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.clicked.connect(self.on_date_clicked)

        # Disable scroll wheel navigation - only use arrow buttons
        self.setNavigationBarVisible(True)

        # Install event filter to block wheel events on all child widgets
        self.installEventFilter(self)

        # Block wheel events on all child widgets (including internal table)
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)

        # Style for dates with posts
        self.post_format = QTextCharFormat()
        self.post_format.setBackground(QBrush(QColor("#4CAF50")))
        self.post_format.setForeground(QBrush(QColor("white")))

    def eventFilter(self, obj, event):
        """Filter out wheel events to prevent month scrolling."""
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.Wheel:
            # Block all wheel events
            return True
        return super().eventFilter(obj, event)

    def wheelEvent(self, event):
        """Override wheel event to disable scroll-based month navigation."""
        # Accept and do nothing to prevent month scrolling
        event.accept()
        return

    def showEvent(self, event):
        """Re-install event filters when widget is shown (catches lazy-loaded children)."""
        super().showEvent(event)
        # Install event filter on all children including lazy-loaded ones
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)

    def set_scheduled_dates(self, queue_data):
        """Update the calendar with scheduled post dates."""
        self.scheduled_dates.clear()

        for post in queue_data:
            scheduled_time = post.get('scheduled_time', '')
            if scheduled_time:
                try:
                    dt = datetime.fromisoformat(scheduled_time)
                    date_str = dt.strftime("%Y-%m-%d")
                    self.scheduled_dates[date_str] = self.scheduled_dates.get(date_str, 0) + 1
                except Exception:
                    pass

        self.updateCells()

    def paintCell(self, painter, rect, date):
        """Custom paint to highlight dates with posts."""
        super().paintCell(painter, rect, date)

        date_str = date.toString("yyyy-MM-dd")
        if date_str in self.scheduled_dates:
            count = self.scheduled_dates[date_str]

            # Draw indicator circle
            painter.save()
            painter.setBrush(QBrush(QColor("#4CAF50")))
            painter.setPen(Qt.PenStyle.NoPen)

            # Small circle in bottom-right
            indicator_size = 8
            x = rect.right() - indicator_size - 2
            y = rect.bottom() - indicator_size - 2
            painter.drawEllipse(x, y, indicator_size, indicator_size)

            # Draw count if more than 1
            if count > 1:
                painter.setPen(QColor("white"))
                font = painter.font()
                font.setPointSize(6)
                painter.setFont(font)
                painter.drawText(x, y, indicator_size, indicator_size,
                               Qt.AlignmentFlag.AlignCenter, str(count))

            painter.restore()

    def on_date_clicked(self, date):
        self.date_selected_for_view.emit(date)


class ScheduleDialog(QDialog):
    """Enhanced dialog for scheduling posts with intuitive time selection."""

    def __init__(self, parent=None, selected_date=None, platforms=None):
        super().__init__(parent)
        self.setWindowTitle("Schedule Post")
        self.setMinimumWidth(450)
        self.platforms = platforms or ['X', 'Threads', 'LinkedIn', 'Reddit', 'Facebook']
        self.scheduled_times = []  # List of datetimes to schedule

        layout = QVBoxLayout(self)

        # Date selection
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Date:"))

        self.date_edit = QDateTimeEdit()
        self.date_edit.setDisplayFormat("MMM d, yyyy")
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setMinimumDate(QDate.currentDate())

        if selected_date:
            self.date_edit.setDate(selected_date)
        else:
            self.date_edit.setDate(QDate.currentDate())

        date_layout.addWidget(self.date_edit)
        date_layout.addStretch()
        layout.addLayout(date_layout)

        # Time selection with AM/PM
        time_group = QGroupBox("Time")
        time_layout = QVBoxLayout(time_group)

        # Hour/Minute/AM-PM selectors
        time_row = QHBoxLayout()

        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(1, 12)
        self.hour_spin.setValue(9)
        self.hour_spin.setWrapping(True)
        time_row.addWidget(QLabel("Hour:"))
        time_row.addWidget(self.hour_spin)

        self.minute_spin = QSpinBox()
        self.minute_spin.setRange(0, 59)
        self.minute_spin.setValue(0)
        self.minute_spin.setSingleStep(5)
        self.minute_spin.setWrapping(True)
        time_row.addWidget(QLabel("Min:"))
        time_row.addWidget(self.minute_spin)

        self.ampm_combo = QComboBox()
        self.ampm_combo.addItems(["AM", "PM"])
        self.ampm_combo.setCurrentText("AM")
        time_row.addWidget(self.ampm_combo)

        time_row.addStretch()
        time_layout.addLayout(time_row)

        # Use Best Times option
        best_times_row = QHBoxLayout()
        self.use_best_times = QCheckBox("Use platform best times")
        self.use_best_times.toggled.connect(self.toggle_best_times)
        best_times_row.addWidget(self.use_best_times)

        self.best_times_combo = QComboBox()
        self.best_times_combo.setEnabled(False)
        self.load_best_times()
        best_times_row.addWidget(self.best_times_combo)
        best_times_row.addStretch()
        time_layout.addLayout(best_times_row)

        layout.addWidget(time_group)

        # Randomize options
        random_group = QGroupBox("Randomize")
        random_layout = QVBoxLayout(random_group)

        self.randomize_enabled = QCheckBox("Enable randomization")
        random_layout.addWidget(self.randomize_enabled)

        # Randomize type
        random_type_row = QHBoxLayout()
        random_type_row.addWidget(QLabel("Type:"))

        self.random_type = QComboBox()
        self.random_type.addItems([
            "Add jitter (±15 min)",
            "Random within range",
            "Random best time"
        ])
        random_type_row.addWidget(self.random_type)
        random_type_row.addStretch()
        random_layout.addLayout(random_type_row)

        # Range inputs (for "Random within range")
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Range:"))

        self.range_start = QSpinBox()
        self.range_start.setRange(0, 23)
        self.range_start.setValue(8)
        self.range_start.setSuffix(":00")
        range_row.addWidget(self.range_start)

        range_row.addWidget(QLabel("to"))

        self.range_end = QSpinBox()
        self.range_end.setRange(0, 23)
        self.range_end.setValue(18)
        self.range_end.setSuffix(":00")
        range_row.addWidget(self.range_end)

        range_row.addStretch()
        random_layout.addLayout(range_row)

        layout.addWidget(random_group)

        # Schedule for week
        week_group = QGroupBox("Schedule for Week")
        week_layout = QVBoxLayout(week_group)

        self.schedule_week = QCheckBox("Schedule across multiple days")
        week_layout.addWidget(self.schedule_week)

        days_row = QHBoxLayout()
        days_row.addWidget(QLabel("Number of days:"))

        self.num_days = QSpinBox()
        self.num_days.setRange(1, 14)
        self.num_days.setValue(7)
        days_row.addWidget(self.num_days)
        days_row.addStretch()
        week_layout.addLayout(days_row)

        # Posts per day
        ppd_row = QHBoxLayout()
        ppd_row.addWidget(QLabel("Posts per day:"))

        self.posts_per_day = QSpinBox()
        self.posts_per_day.setRange(1, 5)
        self.posts_per_day.setValue(1)
        ppd_row.addWidget(self.posts_per_day)
        ppd_row.addStretch()
        week_layout.addLayout(ppd_row)

        layout.addWidget(week_group)

        # Buttons
        btn_layout = QHBoxLayout()
        schedule_btn = QPushButton("Schedule")
        schedule_btn.clicked.connect(self.calculate_and_accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(schedule_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def load_best_times(self):
        """Load best times into combo box."""
        config = load_config()
        best_times = config.get('best_times', DEFAULT_BEST_TIMES)

        self.best_times_combo.clear()
        all_times = set()

        for platform, times in best_times.items():
            for t in times:
                all_times.add(t)

        # Sort and add to combo
        for t in sorted(all_times):
            try:
                # Convert to 12h format for display
                h, m = map(int, t.split(':'))
                ampm = 'AM' if h < 12 else 'PM'
                h12 = h % 12 or 12
                display = f"{h12}:{m:02d} {ampm}"
                self.best_times_combo.addItem(display, t)
            except Exception:
                self.best_times_combo.addItem(t, t)

    def toggle_best_times(self, enabled):
        """Toggle best times combo box."""
        self.best_times_combo.setEnabled(enabled)
        self.hour_spin.setEnabled(not enabled)
        self.minute_spin.setEnabled(not enabled)
        self.ampm_combo.setEnabled(not enabled)

    def get_base_time(self):
        """Get the selected time as hours and minutes (24h)."""
        if self.use_best_times.isChecked():
            time_str = self.best_times_combo.currentData()
            if time_str:
                h, m = map(int, time_str.split(':'))
                return h, m

        hour = self.hour_spin.value()
        minute = self.minute_spin.value()

        # Convert to 24h
        if self.ampm_combo.currentText() == "PM" and hour != 12:
            hour += 12
        elif self.ampm_combo.currentText() == "AM" and hour == 12:
            hour = 0

        return hour, minute

    def apply_randomization(self, base_dt):
        """Apply randomization to a datetime."""
        if not self.randomize_enabled.isChecked():
            return base_dt

        random_type = self.random_type.currentText()

        if "jitter" in random_type:
            # Add ±15 minutes
            jitter = random.randint(-15, 15)
            return base_dt + timedelta(minutes=jitter)

        elif "range" in random_type:
            # Random time within range
            start_h = self.range_start.value()
            end_h = self.range_end.value()

            random_hour = random.randint(start_h, end_h)
            random_min = random.randint(0, 59)

            return base_dt.replace(hour=random_hour, minute=random_min)

        elif "best time" in random_type:
            # Random best time from config
            config = load_config()
            best_times = config.get('best_times', DEFAULT_BEST_TIMES)

            # Collect all times
            all_times = []
            for times in best_times.values():
                all_times.extend(times)

            if all_times:
                time_str = random.choice(all_times)
                h, m = map(int, time_str.split(':'))
                return base_dt.replace(hour=h, minute=m)

        return base_dt

    def calculate_and_accept(self):
        """Calculate all scheduled times and accept."""
        self.scheduled_times = []

        base_date = self.date_edit.date()
        hour, minute = self.get_base_time()

        if self.schedule_week.isChecked():
            # Schedule across multiple days
            num_days = self.num_days.value()
            ppd = self.posts_per_day.value()

            for day in range(num_days):
                current_date = base_date.addDays(day)

                for post_num in range(ppd):
                    dt = datetime(
                        current_date.year(),
                        current_date.month(),
                        current_date.day(),
                        hour, minute, 0
                    )

                    # Apply randomization
                    dt = self.apply_randomization(dt)

                    # Ensure not in past
                    if dt > datetime.now():
                        self.scheduled_times.append(dt)
        else:
            # Single post
            dt = datetime(
                base_date.year(),
                base_date.month(),
                base_date.day(),
                hour, minute, 0
            )

            dt = self.apply_randomization(dt)

            if dt > datetime.now():
                self.scheduled_times.append(dt)

        if self.scheduled_times:
            self.accept()
        else:
            QMessageBox.warning(self, "Invalid Time", "All selected times are in the past.")

    def get_scheduled_times(self):
        """Get list of scheduled datetimes."""
        return self.scheduled_times

    def get_datetime(self):
        """Get single datetime (for backward compatibility)."""
        if self.scheduled_times:
            return self.scheduled_times[0]
        return None


class DayPostsDialog(QDialog):
    """Dialog showing posts scheduled for a specific day."""

    def __init__(self, parent, date, posts):
        super().__init__(parent)
        self.setWindowTitle(f"Posts for {date.toString('MMMM d, yyyy')}")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)

        if not posts:
            layout.addWidget(QLabel("No posts scheduled for this day."))
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll_widget = QWidget()
            scroll_layout = QVBoxLayout(scroll_widget)

            for post in posts:
                frame = QFrame()
                frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
                frame_layout = QVBoxLayout(frame)

                # Time
                scheduled_time = post.get('scheduled_time', '')
                if scheduled_time:
                    try:
                        dt = datetime.fromisoformat(scheduled_time)
                        time_str = dt.strftime("%I:%M %p")
                        time_label = QLabel(f"Time: {time_str}")
                        time_label.setStyleSheet("font-weight: bold;")
                        frame_layout.addWidget(time_label)
                    except Exception:
                        pass

                # Caption preview
                caption = post.get('caption', '')[:100]
                if len(post.get('caption', '')) > 100:
                    caption += '...'
                caption_label = QLabel(caption or "(No caption)")
                caption_label.setWordWrap(True)
                frame_layout.addWidget(caption_label)

                # Platforms with color dots
                platforms = post.get('platforms', [])
                if platforms:
                    plat_row = QHBoxLayout()
                    for platform in platforms:
                        color = PLATFORM_COLORS.get(platform, '#333333')
                        dot = QLabel()
                        dot.setFixedSize(10, 10)
                        dot.setStyleSheet(f"""
                            QLabel {{
                                background-color: {color};
                                border-radius: 5px;
                            }}
                        """)
                        dot.setToolTip(platform)
                        plat_row.addWidget(dot)
                    plat_row.addStretch()
                    frame_layout.addLayout(plat_row)

                scroll_layout.addWidget(frame)

            scroll_layout.addStretch()
            scroll.setWidget(scroll_widget)
            layout.addWidget(scroll)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# --------------------------------------------------------------------
# QUEUE CARD WIDGET
# --------------------------------------------------------------------

class QueueCard(QFrame):
    """Card widget displaying a queued post with thumbnail."""

    remove_clicked = pyqtSignal(str)
    edit_clicked = pyqtSignal(dict)

    def __init__(self, post_data):
        super().__init__()
        self.post_id = post_data.get('id', '')
        self.post_data = post_data
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setMinimumWidth(200)
        self.setMaximumWidth(250)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Scheduled time
        scheduled_time = post_data.get('scheduled_time', '')
        if scheduled_time:
            try:
                dt = datetime.fromisoformat(scheduled_time)
                time_str = dt.strftime("%b %d, %I:%M %p")
                time_label = QLabel(time_str)
                time_label.setStyleSheet("font-weight: bold; color: #4CAF50; font-size: 11px;")
                layout.addWidget(time_label)
            except Exception:
                pass

        # Thumbnail
        thumb_label = QLabel()
        thumb_label.setFixedSize(180, 100)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_label.setStyleSheet("background-color: #eee; border-radius: 4px;")

        media_path = post_data.get('media_path', '')
        if media_path and os.path.exists(media_path):
            ext = os.path.splitext(media_path)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                pixmap = QPixmap(media_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(180, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
                    thumb_label.setPixmap(pixmap)
                else:
                    thumb_label.setText("Image")
            elif ext in VIDEO_EXTENSIONS:
                thumb_label.setText("Video")
            elif ext in WEB_EXTENSIONS:
                thumb_label.setText("HTML")
        else:
            thumb_label.setText("No media")

        layout.addWidget(thumb_label)

        # Platform color indicators
        platforms = post_data.get('platforms', [])
        if platforms:
            plat_row = QHBoxLayout()
            for platform in platforms:
                color = PLATFORM_COLORS.get(platform, '#333333')
                dot = QLabel()
                dot.setFixedSize(12, 12)
                dot.setStyleSheet(f"""
                    QLabel {{
                        background-color: {color};
                        border-radius: 6px;
                    }}
                """)
                dot.setToolTip(platform)
                plat_row.addWidget(dot)
            plat_row.addStretch()
            layout.addLayout(plat_row)

        # Caption preview
        caption = post_data.get('caption', '')[:50]
        if len(post_data.get('caption', '')) > 50:
            caption += '...'
        caption_label = QLabel(caption or "(No caption)")
        caption_label.setWordWrap(True)
        caption_label.setStyleSheet("font-size: 11px; color: #333;")
        layout.addWidget(caption_label)

        # Edit and Remove buttons
        btn_row = QHBoxLayout()

        edit_btn = QPushButton("Edit")
        edit_btn.setStyleSheet("""
            QPushButton {
                font-size: 10px;
                background-color: #2196F3;
                color: white;
                padding: 4px 8px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.post_data))
        btn_row.addWidget(edit_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setStyleSheet("""
            QPushButton {
                font-size: 10px;
                background-color: #f44336;
                color: white;
                padding: 4px 8px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.post_id))
        btn_row.addWidget(remove_btn)

        layout.addLayout(btn_row)


# --------------------------------------------------------------------
# MAIN APP
# --------------------------------------------------------------------

class SocialRocket(QMainWindow):
    # Create a signal for AI content updates
    ai_content_ready = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        os.makedirs(QUEUE_DIR, exist_ok=True)
        os.makedirs(POSTED_DIR, exist_ok=True)

        self.setWindowTitle("Social Rocket")
        self.resize(1000, 800)

        # Set window icon
        icon_pixmap = QPixmap("logo.jpg")
        if not icon_pixmap.isNull():
            self.setWindowIcon(QIcon(icon_pixmap))

        self.scheduler_running = False
        self.scheduler_thread = None

        # Initialize AI service
        self.ai_service = AIService()

        # Current media being edited
        self.current_media_path = None

        # Track if editing existing post
        self.editing_post_id = None

        # Queue data (list of post dicts)
        self.queue_data = []
        self.load_queue_data()

        # Creative library (list of media paths)
        self.creative_library = []
        self.load_creative_library()

        # Connect AI content signal
        self.ai_content_ready.connect(self.update_ai_fields)

        self._build_ui()

    def is_dry_run(self):
        """Check if dry run mode is enabled from config."""
        config = load_config()
        return config.get('dry_run', True)  # Default to True for safety

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # Set app background to match logo
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0d202f;
            }
            QWidget {
                background-color: #0d202f;
            }
        """)

        # Main scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background-color: #0d202f; border: none; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("QWidget { background-color: #0d202f; }")
        main_layout = QVBoxLayout(scroll_content)
        main_layout.setSpacing(10)

        # Set up central layout with scroll
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(scroll)

        # Top bar with logo
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(10, 10, 10, 10)

        # Logo
        logo_label = QLabel()
        logo_pixmap = QPixmap("logo.jpg")
        if not logo_pixmap.isNull():
            scaled_logo = logo_pixmap.scaled(300, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_logo)
        else:
            logo_label.setText("Social Rocket")
            logo_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        top_bar.addWidget(logo_label)

        top_bar.addStretch()

        history_btn = QPushButton("📊 History")
        history_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        history_btn.clicked.connect(self.open_history)
        top_bar.addWidget(history_btn)

        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.clicked.connect(self.open_settings)
        top_bar.addWidget(settings_btn)

        main_layout.addLayout(top_bar)

        # ===== CURRENT CREATIVE CARD =====
        self.creative_card = QFrame()
        self.creative_card.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.creative_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border: 3px solid #A78BFA;
                border-radius: 12px;
                padding: 15px;
            }
        """)
        creative_layout = QVBoxLayout(self.creative_card)
        creative_layout.setSpacing(12)

        # Header row with Add Creative button
        header_row = QHBoxLayout()

        header_label = QLabel("✨ Creative Library")
        header_label.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold;")
        header_row.addWidget(header_label)
        header_row.addStretch()

        self.add_creative_btn = QPushButton("+ Add Creative")
        self.add_creative_btn.setMinimumHeight(40)
        self.add_creative_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-weight: bold;
                background-color: #10B981;
                color: white;
                border-radius: 8px;
                padding: 8px 20px;
                border: 2px solid #34D399;
            }
            QPushButton:hover {
                background-color: #059669;
                border: 2px solid #10B981;
            }
        """)
        self.add_creative_btn.clicked.connect(self.add_creative_to_library)
        header_row.addWidget(self.add_creative_btn)

        creative_layout.addLayout(header_row)

        # Creative Gallery (scrollable horizontal thumbnails)
        gallery_label = QLabel("📸 Your Creatives:")
        gallery_label.setStyleSheet("color: #F3F4F6; font-size: 12px; font-style: italic; font-weight: 500;")
        creative_layout.addWidget(gallery_label)

        # Scrollable area for thumbnails
        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setFixedHeight(140)
        self.gallery_scroll.setStyleSheet("""
            QScrollArea {
                background-color: rgba(255, 255, 255, 0.15);
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
            }
            QScrollBar:horizontal {
                height: 12px;
                background-color: rgba(0, 0, 0, 0.2);
            }
            QScrollBar::handle:horizontal {
                background-color: #A78BFA;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #C4B5FD;
            }
        """)

        # Container for thumbnails
        self.gallery_widget = QWidget()
        self.gallery_layout = QHBoxLayout(self.gallery_widget)
        self.gallery_layout.setSpacing(10)
        self.gallery_layout.setContentsMargins(10, 10, 10, 10)
        self.gallery_layout.addStretch()

        self.gallery_scroll.setWidget(self.gallery_widget)
        creative_layout.addWidget(self.gallery_scroll)

        # Divider
        divider = QLabel()
        divider.setFixedHeight(2)
        divider.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #A78BFA, stop:0.5 #FCD34D, stop:1 #A78BFA);")
        creative_layout.addWidget(divider)

        # Selected Creative Section
        selected_label = QLabel("🎨 Selected Creative:")
        selected_label.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        creative_layout.addWidget(selected_label)

        # Content row: Preview on left, fields on right
        content_row = QHBoxLayout()

        # Media preview (larger)
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(300, 220)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.15);
                border: 2px solid #C4B5FD;
                border-radius: 8px;
                color: #F3F4F6;
                font-size: 13px;
            }
        """)
        self.preview_label.setText("No creative\nselected")
        content_row.addWidget(self.preview_label)

        # File info label
        self.file_label = QLabel("Select a creative from the gallery above")
        self.file_label.setStyleSheet("color: #E0E7FF; font-size: 11px; font-style: italic;")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setWordWrap(True)

        # Fields column
        fields_layout = QVBoxLayout()
        fields_layout.setSpacing(8)

        # Project Selector Row
        project_row = QHBoxLayout()
        project_label = QLabel("Project:")
        project_label.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 11px;")
        project_row.addWidget(project_label)

        self.project_selector = QComboBox()
        self.project_selector.setStyleSheet("""
            QComboBox {
                background-color: #505050;
                color: white;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 150px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid white;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #505050;
                color: white;
                selection-background-color: #667eea;
            }
        """)
        self.project_selector.currentIndexChanged.connect(self.on_project_changed)
        project_row.addWidget(self.project_selector)

        # Industry/Sub-Industry Display
        self.industry_label = QLabel("")
        self.industry_label.setStyleSheet("color: #999; font-size: 10px; font-style: italic; margin-left: 10px;")
        project_row.addWidget(self.industry_label)

        project_row.addStretch()
        fields_layout.addLayout(project_row)

        # Content Type Selector Row
        content_type_row = QHBoxLayout()
        content_type_label = QLabel("Content Type:")
        content_type_label.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 11px;")
        content_type_row.addWidget(content_type_label)

        self.content_type_selector = QComboBox()
        self.content_type_selector.setStyleSheet("""
            QComboBox {
                background-color: #505050;
                color: white;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 180px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid white;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #505050;
                color: white;
                selection-background-color: #667eea;
            }
        """)
        self.content_type_selector.currentIndexChanged.connect(self.on_content_type_changed)
        content_type_row.addWidget(self.content_type_selector)
        content_type_row.addStretch()
        fields_layout.addLayout(content_type_row)

        # Load projects and populate selectors
        self.projects = load_projects()
        if not self.projects:
            self.projects = create_default_projects()
            save_projects(self.projects)

        for project in self.projects:
            self.project_selector.addItem(project['name'], project['id'])

        # Initialize content types for first project
        if self.projects:
            self.populate_content_types()

        # Info label
        info_label = QLabel("Select content type above, then AI will generate optimized content")
        info_label.setStyleSheet("color: #B0B0B0; font-size: 10px; font-style: italic;")
        fields_layout.addWidget(info_label)

        # Caption
        caption_label = QLabel("Caption")
        caption_label.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 11px;")
        fields_layout.addWidget(caption_label)
        self.caption_input = QTextEdit()
        self.caption_input.setMaximumHeight(60)
        self.caption_input.setPlaceholderText("Auto-generated from your image...")
        self.caption_input.setStyleSheet("""
            QTextEdit {
                background-color: #505050;
                color: white;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        fields_layout.addWidget(self.caption_input)

        # Hashtags
        hashtag_label = QLabel("Hashtags")
        hashtag_label.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 11px;")
        fields_layout.addWidget(hashtag_label)
        self.hashtag_input = QLineEdit()
        self.hashtag_input.setPlaceholderText("Auto-generated from your image...")
        self.hashtag_input.setStyleSheet("""
            QLineEdit {
                background-color: #505050;
                color: white;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        fields_layout.addWidget(self.hashtag_input)

        # Keywords
        keyword_label = QLabel("Keywords")
        keyword_label.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 11px;")
        fields_layout.addWidget(keyword_label)
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("Auto-generated from your image...")
        self.keyword_input.setStyleSheet("""
            QLineEdit {
                background-color: #505050;
                color: white;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        fields_layout.addWidget(self.keyword_input)

        # Hidden prompt fields (still functional but not shown)
        self.caption_prompt = QLineEdit()
        self.caption_prompt.hide()
        self.hashtag_prompt = QLineEdit()
        self.hashtag_prompt.hide()
        self.keyword_prompt = QLineEdit()
        self.keyword_prompt.hide()

        # Regenerate button
        regen_row = QHBoxLayout()
        regen_row.addStretch()
        self.regenerate_btn = QPushButton("Regenerate with AI")
        self.regenerate_btn.clicked.connect(self.regenerate_content)
        self.regenerate_btn.setEnabled(False)
        self.regenerate_btn.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                background-color: #6B8E23;
                color: white;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #556B2F;
            }
            QPushButton:disabled {
                background-color: #606060;
                color: #909090;
            }
        """)
        regen_row.addWidget(self.regenerate_btn)
        fields_layout.addLayout(regen_row)

        content_row.addLayout(fields_layout)
        creative_layout.addLayout(content_row)

        main_layout.addWidget(self.creative_card)

        # Platform checkboxes with color coding
        plat_layout = QHBoxLayout()
        plat_layout.addWidget(QLabel("Platforms:"))

        self.platform_checkboxes = {}

        for platform in ALL_PLATFORMS:
            color = PLATFORM_COLORS.get(platform, '#333333')
            chk = QCheckBox(platform)
            chk.setChecked(True)
            chk.setStyleSheet(f"""
                QCheckBox {{
                    color: {color};
                    font-weight: bold;
                    padding: 4px 8px;
                    border-radius: 4px;
                }}
                QCheckBox::indicator:checked {{
                    background-color: {color};
                    border: 2px solid {color};
                    border-radius: 3px;
                }}
                QCheckBox::indicator:unchecked {{
                    border: 2px solid {color};
                    border-radius: 3px;
                }}
            """)
            self.platform_checkboxes[platform] = chk
            plat_layout.addWidget(chk)

        plat_layout.addStretch()
        main_layout.addLayout(plat_layout)

        # Action buttons
        action_row = QHBoxLayout()

        self.schedule_btn = QPushButton("Schedule Post")
        self.schedule_btn.clicked.connect(self.schedule_post)
        self.schedule_btn.setEnabled(False)
        self.schedule_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1B5E20;
            }
            QPushButton:disabled {
                background-color: #81C784;
                color: #C8E6C9;
            }
        """)
        action_row.addWidget(self.schedule_btn)

        self.post_now_btn = QPushButton("Post Now")
        self.post_now_btn.clicked.connect(self.post_now)
        self.post_now_btn.setEnabled(False)
        self.post_now_btn.setStyleSheet("""
            QPushButton {
                background-color: #1877F2;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0C63D4;
            }
            QPushButton:disabled {
                background-color: #90CAF9;
                color: #E3F2FD;
            }
        """)
        action_row.addWidget(self.post_now_btn)

        action_row.addStretch()
        main_layout.addLayout(action_row)

        # Calendar and Queue section side by side
        calendar_queue_layout = QHBoxLayout()

        # Calendar
        calendar_container = QVBoxLayout()
        calendar_container.addWidget(QLabel("Content Calendar"))

        self.calendar = ContentCalendar()
        self.calendar.setMinimumHeight(350)  # Taller calendar for better visibility
        self.calendar.date_selected_for_view.connect(self.show_day_posts)
        calendar_container.addWidget(self.calendar)

        calendar_queue_layout.addLayout(calendar_container)

        # Queue section
        queue_container = QVBoxLayout()
        queue_header = QHBoxLayout()
        queue_header.addWidget(QLabel("Upcoming Posts"))
        queue_header.addStretch()
        queue_container.addLayout(queue_header)

        # Scrollable queue area
        queue_scroll = QScrollArea()
        queue_scroll.setWidgetResizable(True)
        queue_scroll.setMinimumHeight(350)  # Match calendar height for better layout
        queue_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        queue_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.queue_widget = QWidget()
        self.queue_layout = QHBoxLayout(self.queue_widget)
        self.queue_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        queue_scroll.setWidget(self.queue_widget)
        queue_container.addWidget(queue_scroll)

        calendar_queue_layout.addLayout(queue_container)
        main_layout.addLayout(calendar_queue_layout)

        # Scheduler controls
        sched_row = QHBoxLayout()

        self.start_btn = QPushButton("Start Scheduler")
        self.start_btn.clicked.connect(self.start_scheduler)
        sched_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Scheduler")
        self.stop_btn.clicked.connect(self.stop_scheduler)
        self.stop_btn.setEnabled(False)
        sched_row.addWidget(self.stop_btn)

        sched_row.addStretch()

        # Dynamic mode label that updates based on config
        self.mode_label = QLabel()
        self.update_mode_label()
        sched_row.addWidget(self.mode_label)

        main_layout.addLayout(sched_row)

        # Log
        main_layout.addWidget(QLabel("Log"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(120)
        self.log.setMaximumBlockCount(500)
        main_layout.addWidget(self.log)

        # Finalize scroll area
        scroll.setWidget(scroll_content)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.refresh_queue_display()
        self.refresh_gallery()  # Load creative library thumbnails
        mode = "DRY-RUN (no real posts)" if self.is_dry_run() else "LIVE (will post to platforms)"
        self.append_log(f"App started. Mode: {mode}")

        # Timer to refresh queue
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_queue_display)
        self.refresh_timer.start(60_000)

    def append_log(self, msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {msg}")

    def update_mode_label(self):
        """Update the mode label based on current config."""
        dry_run = self.is_dry_run()
        mode_text = 'DRY-RUN' if dry_run else 'LIVE'
        mode_color = 'orange' if dry_run else 'red'
        self.mode_label.setText(f"Mode: {mode_text}")
        self.mode_label.setStyleSheet(f"color: {mode_color}; font-weight: bold; font-size: 13px;")

    def open_history(self):
        """Open the post history dialog."""
        dialog = HistoryDialog(self)
        dialog.exec()

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            save_config(settings)
            self.update_mode_label()  # Refresh mode label after settings change
            self.append_log("Settings saved.")

    def load_creative_library(self):
        """Load creative library from disk."""
        library_file = os.path.join(QUEUE_DIR, 'creative_library.json')
        if os.path.exists(library_file):
            try:
                with open(library_file, 'r') as f:
                    self.creative_library = json.load(f)
            except:
                self.creative_library = []
        else:
            self.creative_library = []

    def save_creative_library(self):
        """Save creative library to disk."""
        library_file = os.path.join(QUEUE_DIR, 'creative_library.json')
        with open(library_file, 'w') as f:
            json.dump(self.creative_library, f, indent=2)

    def add_creative_to_library(self):
        """Add a new creative to the library."""
        file_filter = "Media Files (*.png *.jpg *.jpeg *.gif *.webp *.svg *.mp4 *.mov *.avi *.webm *.html *.htm);;All Files (*)"
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Creative(s) to Library",
            "",
            file_filter
        )

        for file_path in file_paths:
            if file_path and file_path not in self.creative_library:
                # Copy file to queue directory
                filename = os.path.basename(file_path)
                dest_path = os.path.join(QUEUE_DIR, f"creative_{uuid.uuid4().hex[:8]}_{filename}")

                try:
                    shutil.copy2(file_path, dest_path)
                    self.creative_library.append(dest_path)
                    self.append_log(f"Added creative: {filename}")
                except Exception as e:
                    self.append_log(f"Error adding creative: {e}")

        self.save_creative_library()
        self.refresh_gallery()

    def refresh_gallery(self):
        """Refresh the creative gallery thumbnails."""
        # Clear existing thumbnails
        for i in reversed(range(self.gallery_layout.count())):
            widget = self.gallery_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Add thumbnails for each creative
        for media_path in self.creative_library:
            if not os.path.exists(media_path):
                continue

            thumb = self.create_thumbnail(media_path)
            self.gallery_layout.insertWidget(self.gallery_layout.count() - 1, thumb)

    def create_thumbnail(self, media_path):
        """Create a clickable thumbnail widget for a creative."""
        thumb_frame = QFrame()
        thumb_frame.setFixedSize(100, 100)
        thumb_frame.setStyleSheet("""
            QFrame {
                background-color: #505050;
                border: 2px solid #707070;
                border-radius: 6px;
            }
            QFrame:hover {
                border: 2px solid #90CAF9;
                background-color: #606060;
            }
        """)
        thumb_frame.setCursor(Qt.CursorShape.PointingHandCursor)

        thumb_layout = QVBoxLayout(thumb_frame)
        thumb_layout.setContentsMargins(3, 3, 3, 3)
        thumb_layout.setSpacing(2)

        # Thumbnail image
        thumb_label = QLabel()
        thumb_label.setFixedSize(94, 70)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_label.setScaledContents(False)

        ext = os.path.splitext(media_path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            pixmap = QPixmap(media_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(94, 70, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                thumb_label.setPixmap(pixmap)
            else:
                thumb_label.setText("IMG")
                thumb_label.setStyleSheet("color: #B0B0B0; font-size: 10px;")
        elif ext in VIDEO_EXTENSIONS:
            thumb_label.setText("VIDEO")
            thumb_label.setStyleSheet("color: #B0B0B0; font-size: 10px;")
        else:
            thumb_label.setText("FILE")
            thumb_label.setStyleSheet("color: #B0B0B0; font-size: 10px;")

        thumb_layout.addWidget(thumb_label)

        # Filename label
        name_label = QLabel(os.path.basename(media_path)[:12] + "...")
        name_label.setStyleSheet("color: #D0D0D0; font-size: 8px;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_layout.addWidget(name_label)

        # Remove button (X)
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(18, 18)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border-radius: 9px;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        remove_btn.clicked.connect(lambda: self.remove_creative_from_library(media_path))

        # Position remove button in top-right corner
        remove_btn.setParent(thumb_frame)
        remove_btn.move(78, 2)

        # Click handler for selecting creative
        thumb_frame.mousePressEvent = lambda event: self.select_creative(media_path)

        return thumb_frame

    def select_creative(self, media_path):
        """Select a creative from the gallery."""
        self.current_media_path = media_path
        self.file_label.setText(os.path.basename(media_path))

        # Update preview
        ext = os.path.splitext(media_path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            pixmap = QPixmap(media_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(300, 220, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                self.preview_label.setPixmap(pixmap)
            else:
                self.preview_label.setText(f"Image:\n{os.path.basename(media_path)}")
        elif ext in VIDEO_EXTENSIONS:
            self.preview_label.setText(f"🎥 Video:\n{os.path.basename(media_path)}")
        elif ext in WEB_EXTENSIONS:
            self.preview_label.setText(f"🌐 HTML:\n{os.path.basename(media_path)}")

        # Enable buttons
        self.schedule_btn.setEnabled(True)
        self.post_now_btn.setEnabled(True)
        self.regenerate_btn.setEnabled(True)

        # Auto-generate content
        self.append_log(f"Selected creative: {os.path.basename(media_path)}")
        self.generate_ai_content()

    def remove_creative_from_library(self, media_path):
        """Remove a creative from the library."""
        if media_path in self.creative_library:
            self.creative_library.remove(media_path)
            self.save_creative_library()
            self.refresh_gallery()
            self.append_log(f"Removed creative: {os.path.basename(media_path)}")

            # If it was the currently selected creative, clear it
            if self.current_media_path == media_path:
                self.clear_current()

    def choose_media_file(self):
        """Open file dialog to choose media file (legacy - now uses add_creative_to_library)."""
        file_filter = "Media Files (*.png *.jpg *.jpeg *.gif *.webp *.svg *.mp4 *.mov *.avi *.webm *.html *.htm);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Media File",
            "",
            file_filter
        )
        if file_path:
            self.on_media_dropped(file_path)

    def on_media_dropped(self, file_path):
        """Handle when a media file is selected."""
        self.current_media_path = file_path
        self.append_log(f"Media loaded: {os.path.basename(file_path)}")

        # Update file label
        self.file_label.setText(os.path.basename(file_path))

        # Update preview
        ext = os.path.splitext(file_path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(240, 170, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                self.preview_label.setPixmap(pixmap)
            else:
                self.preview_label.setText(f"Image:\n{os.path.basename(file_path)}")
        elif ext in VIDEO_EXTENSIONS:
            self.preview_label.setText(f"Video:\n{os.path.basename(file_path)}")
        elif ext in WEB_EXTENSIONS:
            self.preview_label.setText(f"HTML:\n{os.path.basename(file_path)}")

        # Enable buttons
        self.schedule_btn.setEnabled(True)
        self.post_now_btn.setEnabled(True)
        self.regenerate_btn.setEnabled(True)

        # Auto-generate content
        self.generate_ai_content()

    def on_project_changed(self):
        """Handle project selection change."""
        self.populate_content_types()
        self.update_industry_label()

    def populate_content_types(self):
        """Populate content type selector based on selected project."""
        self.content_type_selector.clear()

        project_id = self.project_selector.currentData()
        if not project_id:
            return

        # Find the selected project
        project = next((p for p in self.projects if p['id'] == project_id), None)
        if not project:
            return

        # Add content types from project
        content_types = project.get('content_types', {})
        for key, content_type in content_types.items():
            self.content_type_selector.addItem(content_type['name'], key)

    def update_industry_label(self):
        """Update the industry/sub-industry display label."""
        project_id = self.project_selector.currentData()
        if not project_id:
            self.industry_label.setText("")
            return

        project = next((p for p in self.projects if p['id'] == project_id), None)
        if project:
            industry = project.get('industry', '')
            sub_industry = project.get('sub_industry', '')
            self.industry_label.setText(f"{industry} > {sub_industry}")
        else:
            self.industry_label.setText("")

    def on_content_type_changed(self):
        """Handle content type selection change."""
        # Ignore early signal emissions before the UI is fully built
        if not hasattr(self, "caption_prompt"):
            return

        # Get selected project and content type
        project_id = self.project_selector.currentData()
        content_type_key = self.content_type_selector.currentData()

        if not project_id or not content_type_key:
            return

        # Find the project
        project = next((p for p in self.projects if p['id'] == project_id), None)
        if not project:
            return

        # Get content type prompts
        content_types = project.get('content_types', {})
        content_type = content_types.get(content_type_key, {})

        # Add industry context to prompts
        industry = project.get('industry', '')
        sub_industry = project.get('sub_industry', '')
        project_name = project.get('name', '')

        context_prefix = f"Creating content for {project_name} ({industry} - {sub_industry}). "

        # Update hidden prompt fields with context
        caption_prompt = context_prefix + content_type.get('caption_prompt', '')
        hashtag_prompt = context_prefix + content_type.get('hashtag_prompt', '')
        keyword_prompt = context_prefix + content_type.get('keyword_prompt', '')

        self.caption_prompt.setText(caption_prompt)
        self.hashtag_prompt.setText(hashtag_prompt)
        self.keyword_prompt.setText(keyword_prompt)

        # Auto-regenerate if media is already selected
        if self.current_media_path:
            content_type_name = content_type.get('name', 'Unknown')
            self.append_log(f"Content type changed to: {project_name} - {content_type_name} - Regenerating...")
            self.generate_ai_content()

    def generate_ai_content(self):
        """Generate caption, hashtags, and keywords using AI."""
        print(f"DEBUG: generate_ai_content called, media_path={self.current_media_path}")

        if not self.current_media_path:
            print("DEBUG: No media path, returning")
            return

        # Check if any API key is configured
        config = load_config()
        has_key = (config.get('anthropic_key') or
                   config.get('openai_key') or
                   config.get('gemini_key'))

        print(f"DEBUG: API key configured: {has_key}")

        if not has_key:
            self.append_log("ERROR: No API keys configured. Go to Settings > AI tab to add your API key.")
            self.caption_input.setPlaceholderText("No API key - go to Settings to configure")
            QMessageBox.warning(
                self,
                "API Key Required",
                "No AI API keys configured.\n\nGo to Settings > AI tab to add your Anthropic, OpenAI, or Gemini API key."
            )
            return

        # Get prompts from selected preset (stored in hidden fields by on_preset_changed)
        caption_prompt = self.caption_prompt.text()
        hashtag_prompt = self.hashtag_prompt.text()
        keyword_prompt = self.keyword_prompt.text()

        print("DEBUG: Starting AI generation...")
        project_name = self.project_selector.currentText()
        content_type_name = self.content_type_selector.currentText()
        self.append_log(f"Generating AI content for {project_name} - {content_type_name}...")
        self.status.showMessage("Analyzing media with AI...")

        # Show loading state in fields
        self.caption_input.setPlaceholderText("Generating with AI...")
        self.hashtag_input.setPlaceholderText("Generating with AI...")
        self.keyword_input.setPlaceholderText("Generating with AI...")

        # Run in a thread to avoid blocking UI
        def generate():
            print("DEBUG: Thread started, calling AI service...")
            result = self.ai_service.analyze_media(
                self.current_media_path,
                caption_prompt,
                hashtag_prompt,
                keyword_prompt
            )
            print(f"DEBUG: AI service returned: {result}")

            # Emit signal to update UI from main thread
            print("DEBUG: Emitting ai_content_ready signal...")
            self.ai_content_ready.emit(result)

        thread = threading.Thread(target=generate, daemon=True)
        thread.start()
        print("DEBUG: Thread started")

    def update_ai_fields(self, result):
        """Update the UI fields with AI-generated content."""
        print(f"DEBUG: update_ai_fields called with result: {result}")

        if 'error' in result and result['error']:
            self.append_log(f"AI generation error: {result['error']}")
            self.status.showMessage("AI generation failed", 3000)
            print(f"ERROR: AI generation failed - {result['error']}")
            return

        caption = result.get('caption', '')
        hashtags = result.get('hashtags', '')
        keywords = result.get('keywords', '')

        print(f"DEBUG: Setting caption: {caption[:50]}...")
        print(f"DEBUG: Setting hashtags: {hashtags[:50]}...")
        print(f"DEBUG: Setting keywords: {keywords[:50]}...")

        self.caption_input.setPlainText(caption)
        self.hashtag_input.setText(hashtags)
        self.keyword_input.setText(keywords)

        provider = result.get('provider', 'Unknown')
        self.append_log(f"AI content generated successfully using {provider}.")
        self.status.showMessage(f"Generated with {provider}", 3000)
        print(f"SUCCESS: UI updated with content from {provider}")

    def regenerate_content(self):
        """Regenerate content with custom prompts."""
        if self.current_media_path:
            self.generate_ai_content()

    def clear_current(self):
        """Clear the current post being edited."""
        self.current_media_path = None
        self.editing_post_id = None
        self.preview_label.clear()
        self.preview_label.setText("No media\nselected")
        self.file_label.setText("No file selected")
        self.caption_input.clear()
        self.hashtag_input.clear()
        self.keyword_input.clear()
        self.caption_prompt.clear()
        self.hashtag_prompt.clear()
        self.keyword_prompt.clear()
        self.schedule_btn.setEnabled(False)
        self.schedule_btn.setText("Schedule Post")
        self.post_now_btn.setEnabled(False)
        self.regenerate_btn.setEnabled(False)

    def schedule_post(self, selected_date=None):
        """Open schedule dialog and add post to queue with scheduled time."""
        if not self.current_media_path:
            return

        # Open schedule dialog
        platforms = self.get_selected_platforms()
        dialog = ScheduleDialog(self, selected_date=selected_date, platforms=platforms)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        scheduled_times = dialog.get_scheduled_times()

        if not scheduled_times:
            return

        # Get post content
        caption = self.caption_input.toPlainText().strip()
        hashtags = self.hashtag_input.text().strip()

        full_text = caption
        if hashtags:
            full_text += "\n\n" + hashtags

        # If editing an existing post, update it instead of creating new
        if self.editing_post_id and len(scheduled_times) == 1:
            for i, post in enumerate(self.queue_data):
                if post.get('id') == self.editing_post_id:
                    # Update existing post
                    self.queue_data[i]['caption'] = caption
                    self.queue_data[i]['hashtags'] = hashtags
                    self.queue_data[i]['keywords'] = self.keyword_input.text().strip()
                    self.queue_data[i]['full_text'] = full_text
                    self.queue_data[i]['platforms'] = platforms
                    self.queue_data[i]['scheduled_time'] = scheduled_times[0].isoformat()
                    break

            # Sort by scheduled time
            self.queue_data.sort(key=lambda x: x.get('scheduled_time', ''))
            self.save_queue_data()
            self.refresh_queue_display()

            time_str = scheduled_times[0].strftime("%b %d at %I:%M %p")
            self.append_log(f"Updated post {self.editing_post_id} - now scheduled for {time_str}")
            self.clear_current()
            return

        # Create a post for each scheduled time
        for scheduled_time in scheduled_times:
            post_id = str(uuid.uuid4())[:8]

            # Copy media to queue directory
            ext = os.path.splitext(self.current_media_path)[1]
            new_media_name = f"{post_id}{ext}"
            new_media_path = os.path.join(QUEUE_DIR, new_media_name)

            with open(self.current_media_path, 'rb') as src:
                with open(new_media_path, 'wb') as dst:
                    dst.write(src.read())

            post_data = {
                'id': post_id,
                'media_path': new_media_path,
                'caption': caption,
                'hashtags': hashtags,
                'keywords': self.keyword_input.text().strip(),
                'full_text': full_text,
                'platforms': platforms,
                'created_at': datetime.now().isoformat(),
                'scheduled_time': scheduled_time.isoformat()
            }

            self.queue_data.append(post_data)

        # Sort by scheduled time
        self.queue_data.sort(key=lambda x: x.get('scheduled_time', ''))
        self.save_queue_data()
        self.refresh_queue_display()

        if len(scheduled_times) == 1:
            time_str = scheduled_times[0].strftime("%b %d at %I:%M %p")
            self.append_log(f"Scheduled post for {time_str}")
        else:
            self.append_log(f"Scheduled {len(scheduled_times)} posts across multiple days")

        self.clear_current()

    def show_day_posts(self, date):
        """Show dialog with posts scheduled for the selected date, or open scheduler."""
        date_str = date.toString("yyyy-MM-dd")

        # Find posts for this date
        day_posts = []
        for post in self.queue_data:
            scheduled_time = post.get('scheduled_time', '')
            if scheduled_time:
                try:
                    dt = datetime.fromisoformat(scheduled_time)
                    if dt.strftime("%Y-%m-%d") == date_str:
                        day_posts.append(post)
                except Exception:
                    pass

        # Sort by time
        day_posts.sort(key=lambda x: x.get('scheduled_time', ''))

        if day_posts:
            # Show existing posts
            dialog = DayPostsDialog(self, date, day_posts)
            dialog.exec()
        elif self.current_media_path:
            # No posts for this day, but media is loaded - open scheduler with this date
            self.schedule_post(selected_date=date)
        else:
            # No posts and no media - just show empty dialog
            dialog = DayPostsDialog(self, date, [])
            dialog.exec()

    def post_now(self):
        """Post the current content immediately."""
        print("DEBUG: post_now() called")

        if not self.current_media_path:
            print("DEBUG: No media path, returning")
            self.append_log("No media selected. Please select a creative first.")
            return

        caption = self.caption_input.toPlainText().strip()
        hashtags = self.hashtag_input.text().strip()

        full_text = caption
        if hashtags:
            full_text += "\n\n" + hashtags

        platforms = self.get_selected_platforms()
        print(f"DEBUG: Selected platforms: {platforms}")

        if not platforms:
            self.append_log("No platforms selected.")
            return

        dry_run = self.is_dry_run()
        print(f"DEBUG: is_dry_run() = {dry_run}")
        self.append_log(f"Posting now... (Mode: {'DRY RUN' if dry_run else 'LIVE'})")

        # Track results for history
        results = {}

        for p in platforms:
            if dry_run:
                self.append_log(
                    f"[DRY RUN] Would post to {p}: {full_text[:80]!r} "
                    f"(media: {os.path.basename(self.current_media_path)})"
                )
                results[p] = "Dry run - not posted"
            else:
                print(f"DEBUG: About to call post_to_platform for {p}")
                self.append_log(f"[LIVE] Attempting to post to {p}...")
                try:
                    ok, info = self.post_to_platform(p, full_text, self.current_media_path)
                    print(f"DEBUG: post_to_platform returned: ok={ok}, info={info}")
                    if ok:
                        self.append_log(f"[LIVE] ✓ {info}")
                        results[p] = f"Success: {info}"
                    else:
                        self.append_log(f"[LIVE] ✗ Failed to post to {p}: {info}")
                        results[p] = f"Failed: {info}"
                except Exception as e:
                    print(f"DEBUG: Exception in post_to_platform: {e}")
                    self.append_log(f"[LIVE] ✗ Error posting to {p}: {e}")
                    results[p] = f"Error: {e}"

        # Add to history
        post_data = {
            'id': str(uuid.uuid4())[:8],
            'media_path': self.current_media_path,
            'caption': caption,
            'hashtags': hashtags,
            'keywords': self.keyword_input.text().strip(),
            'platforms': platforms,
            'created_at': datetime.now().isoformat(),
            'scheduled_time': ''  # Immediate post, no schedule
        }
        add_to_history(post_data, platforms, results)
        self.append_log(f"Posted immediately. Added to history.")

        self.clear_current()

    def get_selected_platforms(self):
        """Get list of selected platform names."""
        platforms = []
        for platform, chk in self.platform_checkboxes.items():
            if chk.isChecked():
                platforms.append(platform)
        return platforms

    def load_queue_data(self):
        """Load queue data from JSON file."""
        queue_file = os.path.join(QUEUE_DIR, "queue.json")
        if os.path.exists(queue_file):
            try:
                with open(queue_file, 'r', encoding='utf-8') as f:
                    self.queue_data = json.load(f)
            except Exception:
                self.queue_data = []
        else:
            self.queue_data = []

    def save_queue_data(self):
        """Save queue data to JSON file."""
        queue_file = os.path.join(QUEUE_DIR, "queue.json")
        with open(queue_file, 'w', encoding='utf-8') as f:
            json.dump(self.queue_data, f, indent=2)

    def refresh_queue_display(self):
        """Refresh the visual queue display and calendar."""
        # Clear existing cards
        while self.queue_layout.count():
            child = self.queue_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add cards for each queued post
        for post_data in self.queue_data:
            card = QueueCard(post_data)
            card.remove_clicked.connect(self.remove_from_queue)
            card.edit_clicked.connect(self.edit_post)
            self.queue_layout.addWidget(card)

        # Add stretch at end
        self.queue_layout.addStretch()

        # Update calendar with scheduled dates
        self.calendar.set_scheduled_dates(self.queue_data)

        self.status.showMessage(f"{len(self.queue_data)} posts scheduled", 3000)

    def remove_from_queue(self, post_id):
        """Remove a post from the queue."""
        for i, post in enumerate(self.queue_data):
            if post.get('id') == post_id:
                # Delete media file
                media_path = post.get('media_path')
                if media_path and os.path.exists(media_path):
                    try:
                        os.remove(media_path)
                    except Exception:
                        pass

                del self.queue_data[i]
                break

        self.save_queue_data()
        self.refresh_queue_display()
        self.append_log(f"Removed post {post_id} from queue.")

    def edit_post(self, post_data):
        """Load a scheduled post back into the creative card for editing."""
        post_id = post_data.get('id', '')
        media_path = post_data.get('media_path', '')

        if not media_path or not os.path.exists(media_path):
            self.append_log(f"Cannot edit post {post_id}: media file not found.")
            QMessageBox.warning(self, "Edit Error", "Media file not found for this post.")
            return

        # Track that we're editing
        self.editing_post_id = post_id

        # Load media into preview
        self.current_media_path = media_path
        self.file_label.setText(os.path.basename(media_path))

        # Update preview
        ext = os.path.splitext(media_path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            pixmap = QPixmap(media_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(240, 170, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                self.preview_label.setPixmap(pixmap)
            else:
                self.preview_label.setText(f"Image:\n{os.path.basename(media_path)}")
        elif ext in VIDEO_EXTENSIONS:
            self.preview_label.setText(f"Video:\n{os.path.basename(media_path)}")
        elif ext in WEB_EXTENSIONS:
            self.preview_label.setText(f"HTML:\n{os.path.basename(media_path)}")

        # Load content into fields
        self.caption_input.setPlainText(post_data.get('caption', ''))
        self.hashtag_input.setText(post_data.get('hashtags', ''))
        self.keyword_input.setText(post_data.get('keywords', ''))

        # Set platform checkboxes
        platforms = post_data.get('platforms', [])
        for platform, chk in self.platform_checkboxes.items():
            chk.setChecked(platform in platforms)

        # Enable buttons
        self.schedule_btn.setEnabled(True)
        self.post_now_btn.setEnabled(True)
        self.regenerate_btn.setEnabled(True)

        # Update button text to indicate editing
        self.schedule_btn.setText("Update Schedule")

        self.append_log(f"Editing post {post_id}. Make changes and click 'Update Schedule'.")

    # ---- Scheduler ----
    def start_scheduler(self):
        if self.scheduler_running:
            return

        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True
        )
        self.scheduler_thread.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.append_log("Scheduler started. Posts will be published at their scheduled times.")

    def stop_scheduler(self):
        if not self.scheduler_running:
            return
        self.scheduler_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.append_log("Scheduler stopped.")

    def _scheduler_loop(self):
        """Check for due posts every 30 seconds."""
        while self.scheduler_running:
            print(f"DEBUG: Scheduler loop running at {datetime.now()}")
            self.check_due_posts()
            time.sleep(30)

    def check_due_posts(self):
        """Check if any posts are due to be published."""
        now = datetime.now()
        print(f"DEBUG: check_due_posts() called, now={now}, queue has {len(self.queue_data)} posts")

        # Reload queue data to get latest (in case it was modified)
        self.load_queue_data()
        print(f"DEBUG: After reload, queue has {len(self.queue_data)} posts")

        # Find posts that are due
        due_posts = []
        for post in self.queue_data:
            scheduled_time = post.get('scheduled_time', '')
            post_id = post.get('id', 'unknown')
            print(f"DEBUG: Checking post {post_id}, scheduled_time='{scheduled_time}'")
            if scheduled_time:
                try:
                    dt = datetime.fromisoformat(scheduled_time)
                    print(f"DEBUG: Post {post_id}: scheduled={dt}, now={now}, due={dt <= now}")
                    if dt <= now:
                        due_posts.append(post)
                        print(f"DEBUG: ✓ Found due post {post_id} scheduled for {dt}")
                except Exception as e:
                    print(f"DEBUG: Error parsing scheduled_time for {post_id}: {e}")

        if due_posts:
            print(f"DEBUG: Processing {len(due_posts)} due posts")
        else:
            print(f"DEBUG: No due posts found")

        # Post each due post
        for post in due_posts:
            QTimer.singleShot(0, lambda p=post: self.post_scheduled_item(p))

    def post_scheduled_item(self, post):
        """Post a scheduled item that is now due."""
        post_id = post.get('id', 'unknown')
        media_path = post.get('media_path')
        full_text = post.get('full_text', '')
        platforms = post.get('platforms', [])

        if not platforms:
            platforms = self.get_selected_platforms()

        scheduled_time = post.get('scheduled_time', '')
        if scheduled_time:
            try:
                dt = datetime.fromisoformat(scheduled_time)
                time_str = dt.strftime("%I:%M %p")
                self.append_log(f"Publishing scheduled post {post_id} (scheduled for {time_str})")
            except Exception:
                self.append_log(f"Publishing scheduled post {post_id}")
        else:
            self.append_log(f"Publishing post {post_id}")

        # Track results for history
        results = {}

        try:
            for p in platforms:
                if self.is_dry_run():
                    self.append_log(
                        f"[DRY RUN] Would post to {p}: {full_text[:80]!r} "
                        f"(media: {os.path.basename(media_path) if media_path else 'none'})"
                    )
                    results[p] = "Dry run - not posted"
                else:
                    try:
                        ok, info = self.post_to_platform(p, full_text, media_path)
                    except Exception as e:
                        ok, info = False, f"Exception while posting: {e}"
                    if ok:
                        self.append_log(f"[LIVE] {info}")
                        results[p] = f"Success: {info}"
                    else:
                        self.append_log(f"[LIVE] Failed to post to {p}: {info}")
                        results[p] = f"Failed: {info}"

            # Add to history
            add_to_history(post, platforms, results)
        except Exception as e:
            # Ensure failures still get logged to history to avoid infinite retries
            self.append_log(f"[ERROR] Scheduled post {post_id} crashed: {e}")
            results["__error"] = str(e)
            add_to_history(post, platforms, results)
        finally:
            # Move to posted folder and remove from queue so we don't spin forever
            try:
                os.makedirs(POSTED_DIR, exist_ok=True)
                if media_path and os.path.exists(media_path):
                    new_path = os.path.join(POSTED_DIR, os.path.basename(media_path))
                    os.replace(media_path, new_path)
            except Exception as e:
                self.append_log(f"[WARN] Could not move media for {post_id}: {e}")

            self.queue_data = [p for p in self.queue_data if p.get('id') != post_id]
            self.save_queue_data()

            self.append_log(f"Completed post {post_id}. Added to history.")
            self.refresh_queue_display()

    def post_to_platform(self, platform_name, text, img_path):
        """Dispatch to the correct per-platform function."""
        if platform_name == "X":
            return post_to_x(text, img_path)
        elif platform_name == "Reddit":
            return post_to_reddit(text, img_path)
        elif platform_name == "Facebook":
            return post_to_facebook(text, img_path)
        elif platform_name == "LinkedIn":
            return post_to_linkedin(text, img_path)
        elif platform_name == "Threads":
            return post_to_threads(text, img_path)
        elif platform_name == "Instagram":
            return post_to_instagram(text, img_path)
        elif platform_name == "TikTok":
            return post_to_tiktok(text, img_path)
        elif platform_name == "Quora":
            return post_to_quora(text, img_path)
        else:
            return False, f"Unknown platform: {platform_name}"


def main():
    app = QApplication(sys.argv)

    # Create and show splash screen
    from PyQt6.QtWidgets import QSplashScreen

    splash_pix = QPixmap("logo.jpg")
    if not splash_pix.isNull():
        splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
        splash.show()
        app.processEvents()

        # Show splash for 2 seconds
        QTimer.singleShot(2000, splash.close)

    win = SocialRocket()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
