#!/usr/bin/env python3
"""
Migration script to move credentials from config.json to .env file.
This is a ONE-TIME operation to improve security.
"""

import json
import os

def migrate_config_to_env():
    """Read config.json and create .env file with credentials."""

    config_file = "config.json.backup"
    env_file = ".env"

    if not os.path.exists(config_file):
        print("❌ config.json.backup not found. Run this script from the social_rocket directory.")
        return False

    if os.path.exists(env_file):
        response = input(f"⚠️  {env_file} already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Aborted. No changes made.")
            return False

    # Load config
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Map config keys to env var names
    env_mappings = {
        'anthropic_key': 'ANTHROPIC_API_KEY',
        'openai_key': 'OPENAI_API_KEY',
        'gemini_key': 'GEMINI_API_KEY',
        'x_username': 'X_USERNAME',
        'x_password': 'X_PASSWORD',
        'linkedin_email': 'LINKEDIN_EMAIL',
        'linkedin_password': 'LINKEDIN_PASSWORD',
        'facebook_email': 'FACEBOOK_EMAIL',
        'facebook_password': 'FACEBOOK_PASSWORD',
        'facebook_url': 'FACEBOOK_URL',
        'threads_username': 'THREADS_USERNAME',
        'threads_password': 'THREADS_PASSWORD',
        'reddit_username': 'REDDIT_USERNAME',
        'reddit_password': 'REDDIT_PASSWORD',
        'instagram_username': 'INSTAGRAM_USERNAME',
        'instagram_password': 'INSTAGRAM_PASSWORD',
        'tiktok_username': 'TIKTOK_USERNAME',
        'tiktok_password': 'TIKTOK_PASSWORD',
        'quora_email': 'QUORA_EMAIL',
        'quora_password': 'QUORA_PASSWORD',
    }

    # Build .env content
    env_lines = [
        "# Social Rocket Environment Variables",
        "# Generated from config.json",
        "# These credentials are MORE SECURE than storing in config.json",
        "",
        "# AI API Keys",
    ]

    # Add API keys
    for config_key in ['anthropic_key', 'openai_key', 'gemini_key']:
        value = config.get(config_key, '')
        if value:
            env_var = env_mappings[config_key]
            env_lines.append(f"{env_var}={value}")

    # Add social media credentials by platform
    platforms = {
        'X / Twitter': ['x_username', 'x_password'],
        'LinkedIn': ['linkedin_email', 'linkedin_password'],
        'Facebook': ['facebook_email', 'facebook_password', 'facebook_url'],
        'Threads': ['threads_username', 'threads_password'],
        'Reddit': ['reddit_username', 'reddit_password'],
        'Instagram': ['instagram_username', 'instagram_password'],
        'TikTok': ['tiktok_username', 'tiktok_password'],
        'Quora': ['quora_email', 'quora_password'],
    }

    for platform_name, keys in platforms.items():
        has_creds = any(config.get(k) for k in keys)
        if has_creds:
            env_lines.append("")
            env_lines.append(f"# {platform_name}")
            for config_key in keys:
                value = config.get(config_key, '')
                if value:
                    env_var = env_mappings.get(config_key)
                    if env_var:
                        env_lines.append(f"{env_var}={value}")

    # Write .env file
    with open(env_file, 'w') as f:
        f.write('\n'.join(env_lines))

    # Set restrictive permissions
    os.chmod(env_file, 0o600)

    print(f"✅ Created {env_file} with credentials from config.json.backup")
    print(f"✅ Set file permissions to 600 (owner read/write only)")
    print()
    print("Next steps:")
    print("1. Review the .env file to ensure all credentials migrated correctly")
    print("2. ROTATE ALL CREDENTIALS (they were exposed in config.json):")
    print("   - Anthropic: https://console.anthropic.com/settings/keys")
    print("   - OpenAI: https://platform.openai.com/api-keys")
    print("   - Gemini: https://makersuite.google.com/app/apikey")
    print("   - Social media: Change passwords in each platform's settings")
    print("3. Update the NEW credentials in .env file")
    print("4. Delete config.json.backup securely: shred -u config.json.backup")
    print("5. The app will now read from .env instead of config.json")

    return True

if __name__ == "__main__":
    print("🔐 Social Rocket - Config to .env Migration")
    print("=" * 50)
    print()
    migrate_config_to_env()
