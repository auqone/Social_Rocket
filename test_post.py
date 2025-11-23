#!/usr/bin/env python3
"""Quick test to verify posting functions work."""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the posting functions
from social_rocket import post_to_x, load_config

def test_post():
    """Test if posting function gets called properly."""
    print("="*60)
    print("TESTING SOCIAL ROCKET POSTING")
    print("="*60)

    # Load config
    config = load_config()
    print(f"\nConfig loaded:")
    print(f"  - dry_run: {config.get('dry_run', 'NOT SET')}")
    print(f"  - x_username: {'SET' if config.get('x_username') else 'NOT SET'}")
    print(f"  - x_password: {'SET' if config.get('x_password') else 'NOT SET'}")
    print(f"  - anthropic_key: {'SET' if config.get('anthropic_key') else 'NOT SET'}")

    # Test image path
    test_image = os.path.join(os.path.dirname(__file__), "logo.jpg")
    if not os.path.exists(test_image):
        print(f"\nWARNING: Test image not found: {test_image}")
        test_image = None
    else:
        print(f"\nTest image: {test_image}")

    # Test posting to X
    print("\n" + "="*60)
    print("ATTEMPTING TEST POST TO X (with real credentials)")
    print("="*60)

    test_text = "Test post from Social Rocket - Testing posting functionality"

    print(f"\nText: {test_text}")
    print(f"Image: {test_image}")
    print("\nCalling post_to_x()...")

    try:
        success, message = post_to_x(test_text, test_image)
        print(f"\nRESULT:")
        print(f"  - Success: {success}")
        print(f"  - Message: {message}")

        if success:
            print("\n✅ POST SUCCESSFUL! Posting functionality is working.")
        else:
            print("\n❌ POST FAILED!")
            print(f"   Error: {message}")

    except Exception as e:
        print(f"\n❌ EXCEPTION OCCURRED:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)

if __name__ == "__main__":
    test_post()
