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
from datetime import datetime, timedelta

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

DRY_RUN = True  # flip to False when you're ready to go live

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_DIR = os.path.join(BASE_DIR, "queue")
POSTED_DIR = os.path.join(BASE_DIR, "posted")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

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
    """Load configuration from JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(config):
    """Save configuration to JSON file."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


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

    if not username or not password:
        return False, "X credentials not configured. Please set them in Settings."

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            page.goto("https://x.com/login", timeout=60000)

            try:
                page.wait_for_selector('input[name="text"], input[autocomplete="username"]', timeout=30000)
                username_box = page.query_selector('input[name="text"]') or page.query_selector('input[autocomplete="username"]')
                username_box.fill(username)
                username_box.press("Enter")
            except Exception as e:
                return False, f"X login: username field error: {e}"

            try:
                page.wait_for_selector('input[name="password"]', timeout=30000)
                page.fill('input[name="password"]', password)
                page.press('input[name="password"]', "Enter")
            except Exception as e:
                return False, f"X login: password field error: {e}"

            try:
                page.wait_for_url("https://x.com/home", timeout=60000)
            except Exception:
                page.wait_for_load_state("networkidle", timeout=60000)

            try:
                post_button = page.query_selector('a[aria-label="Post"], a[data-testid="SideNav_NewPost_Button"]')
                if post_button:
                    post_button.click()
                else:
                    composer = page.query_selector('div[aria-label="Post text"], div[data-testid="tweetTextarea_0"]')
                    if composer:
                        composer.click()
                page.wait_for_timeout(1000)
            except Exception as e:
                return False, f"X: could not open composer: {e}"

            try:
                textarea = page.query_selector('div[aria-label="Post text"]') or page.query_selector(
                    'div[data-testid="tweetTextarea_0"]'
                )
                if not textarea:
                    return False, "X: composer textarea not found."
                textarea.fill(text)
            except Exception as e:
                return False, f"X: error filling text: {e}"

            if image_path and os.path.exists(image_path):
                try:
                    file_input = page.query_selector('input[type="file"]')
                    if file_input:
                        file_input.set_input_files(image_path)
                        page.wait_for_timeout(4000)
                except Exception as e:
                    return False, f"X: error attaching image: {e}"

            try:
                btn = (
                    page.query_selector('div[data-testid="tweetButtonInline"]')
                    or page.query_selector('div[data-testid="tweetButton"]')
                    or page.query_selector('button[data-testid="tweetButtonInline"]')
                )
                if not btn:
                    return False, "X: tweet button not found."
                btn.click()
                page.wait_for_timeout(5000)
            except Exception as e:
                return False, f"X: error clicking tweet button: {e}"

            return True, "Posted to X"
    except Exception as e:
        return False, f"X Playwright error: {e}"
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass


def post_to_reddit(text, image_path=None):
    return False, "Reddit posting not implemented yet."


def post_to_facebook(text, image_path=None):
    return False, "Facebook posting not implemented yet."


def post_to_linkedin(text, image_path=None):
    return False, "LinkedIn posting not implemented yet."


def post_to_threads(text, image_path=None):
    return False, "Threads posting not implemented yet."


def post_to_instagram(text, image_path=None):
    return False, "Instagram posting not implemented yet."


def post_to_tiktok(text, image_path=None):
    return False, "TikTok posting not implemented yet."


def post_to_quora(text, image_path=None):
    return False, "Quora posting not implemented yet."


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

        # Style for dates with posts
        self.post_format = QTextCharFormat()
        self.post_format.setBackground(QBrush(QColor("#4CAF50")))
        self.post_format.setForeground(QBrush(QColor("white")))

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

        settings_btn = QPushButton("Settings")
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

        # Info label
        info_label = QLabel("Select a file to auto-generate content with AI")
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
                background-color: #ccc;
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
                background-color: #ccc;
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
        queue_scroll.setMinimumHeight(200)
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

        mode_label = QLabel(f"Mode: {'DRY-RUN' if DRY_RUN else 'LIVE'}")
        mode_label.setStyleSheet(f"color: {'orange' if DRY_RUN else 'green'}; font-weight: bold;")
        sched_row.addWidget(mode_label)

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
        mode = "DRY-RUN (no real posts)" if DRY_RUN else "LIVE (will post to platforms)"
        self.append_log(f"App started. Mode: {mode}")

        # Timer to refresh queue
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_queue_display)
        self.refresh_timer.start(60_000)

    def append_log(self, msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {msg}")

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            save_config(settings)
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

        print("DEBUG: Starting AI generation...")
        self.append_log("Generating AI content...")
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
                self.caption_prompt.text(),
                self.hashtag_prompt.text(),
                self.keyword_prompt.text()
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
        if not self.current_media_path:
            return

        caption = self.caption_input.toPlainText().strip()
        hashtags = self.hashtag_input.text().strip()

        full_text = caption
        if hashtags:
            full_text += "\n\n" + hashtags

        platforms = self.get_selected_platforms()

        if not platforms:
            self.append_log("No platforms selected.")
            return

        self.append_log("Posting now...")

        for p in platforms:
            if DRY_RUN:
                self.append_log(
                    f"[DRY RUN] Would post to {p}: {full_text[:80]!r} "
                    f"(media: {os.path.basename(self.current_media_path)})"
                )
            else:
                ok, info = self.post_to_platform(p, full_text, self.current_media_path)
                if ok:
                    self.append_log(f"[LIVE] {info}")
                else:
                    self.append_log(f"[LIVE] Failed to post to {p}: {info}")

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
            self.check_due_posts()
            time.sleep(30)

    def check_due_posts(self):
        """Check if any posts are due to be published."""
        now = datetime.now()

        # Find posts that are due
        due_posts = []
        for post in self.queue_data:
            scheduled_time = post.get('scheduled_time', '')
            if scheduled_time:
                try:
                    dt = datetime.fromisoformat(scheduled_time)
                    if dt <= now:
                        due_posts.append(post)
                except Exception:
                    pass

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

        for p in platforms:
            if DRY_RUN:
                self.append_log(
                    f"[DRY RUN] Would post to {p}: {full_text[:80]!r} "
                    f"(media: {os.path.basename(media_path) if media_path else 'none'})"
                )
            else:
                ok, info = self.post_to_platform(p, full_text, media_path)
                if ok:
                    self.append_log(f"[LIVE] {info}")
                else:
                    self.append_log(f"[LIVE] Failed to post to {p}: {info}")

        # Move to posted
        os.makedirs(POSTED_DIR, exist_ok=True)
        if media_path and os.path.exists(media_path):
            new_path = os.path.join(POSTED_DIR, os.path.basename(media_path))
            os.replace(media_path, new_path)

        # Remove from queue
        self.queue_data = [p for p in self.queue_data if p.get('id') != post_id]
        self.save_queue_data()

        self.append_log(f"Completed post {post_id}.")
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
