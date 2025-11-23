#!/usr/bin/env python3
"""
Test script to verify history system works and manually add test entry.
"""

import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from social_rocket import add_to_history, load_post_history, save_post_history

def test_history():
    """Test adding and loading history."""

    print("🧪 Testing Post History System")
    print("=" * 60)

    # Create a test post
    test_post = {
        'id': 'test123',
        'media_path': '/Users/nicholashanks/Desktop/social_rocket/fsboz_logo.png',
        'caption': 'Test caption for FSBOz - Save thousands on commission!',
        'hashtags': '#FSBO #ForSaleByOwner #RealEstate',
        'keywords': 'fsbo, for sale by owner, real estate',
        'platforms': ['X', 'LinkedIn', 'Facebook'],
        'created_at': datetime.now().isoformat(),
        'scheduled_time': ''
    }

    platforms = ['X', 'LinkedIn', 'Facebook']
    results = {
        'X': 'Dry run - not posted',
        'LinkedIn': 'Dry run - not posted',
        'Facebook': 'Dry run - not posted'
    }

    print("\n📝 Adding test post to history...")
    try:
        entry = add_to_history(test_post, platforms, results)
        print(f"✅ Added post with ID: {entry['id']}")
    except Exception as e:
        print(f"❌ Failed to add to history: {e}")
        return False

    print("\n📖 Loading history...")
    try:
        history = load_post_history()
        print(f"✅ Loaded {len(history)} posts from history")

        if history:
            latest = history[0]
            print(f"\n📊 Latest post:")
            print(f"   ID: {latest.get('id')}")
            print(f"   Caption: {latest.get('caption', '')[:50]}...")
            print(f"   Platforms: {', '.join(latest.get('platforms', []))}")
            print(f"   Posted at: {latest.get('posted_at', 'N/A')}")

    except Exception as e:
        print(f"❌ Failed to load history: {e}")
        return False

    print("\n" + "=" * 60)
    print("✅ History system is working correctly!")
    print("\n💡 Now when you click 'Post Now' in the app,")
    print("   posts will be saved to history automatically.")

    return True

if __name__ == "__main__":
    success = test_history()
    sys.exit(0 if success else 1)
