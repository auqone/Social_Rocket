#!/usr/bin/env python3
"""Direct test of LinkedIn posting function - bypass GUI"""
import sys
import os

# Force reimport
if 'social_rocket' in sys.modules:
    del sys.modules['social_rocket']

# Clear any cached bytecode
import importlib
importlib.invalidate_caches()

# Now import
from social_rocket import post_to_linkedin

# Test
print("=" * 60)
print("TESTING LINKEDIN POST FUNCTION DIRECTLY")
print("=" * 60)

test_image = "/Users/nicholashanks/Desktop/social_rocket/queue/creative_f243bc56_Screenshot 2025-11-15 at 6.27.11 AM.png"
test_text = "Test post from Social Rocket - Direct function call"

print(f"\nCalling post_to_linkedin with:")
print(f"  Text: {test_text}")
print(f"  Image: {test_image}")
print("\n" + "=" * 60)

success, message = post_to_linkedin(test_text, test_image)

print("\n" + "=" * 60)
print(f"RESULT: {'SUCCESS' if success else 'FAILED'}")
print(f"Message: {message}")
print("=" * 60)
