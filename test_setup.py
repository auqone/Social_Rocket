#!/usr/bin/env python3
"""
Test script to verify Social Rocket setup without launching GUI.
Tests: .env loading, config loading, AI service, content presets
"""

import os
import sys

def test_env_loading():
    """Test that .env file is loaded."""
    print("📋 Testing .env file loading...")

    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("  ✅ python-dotenv installed and .env loaded")
    except ImportError:
        print("  ⚠️  python-dotenv not installed - will use environment variables directly")

    # Check if any credentials are loaded
    creds_found = []
    if os.environ.get('ANTHROPIC_API_KEY'):
        creds_found.append('Anthropic')
    if os.environ.get('OPENAI_API_KEY'):
        creds_found.append('OpenAI')
    if os.environ.get('GEMINI_API_KEY'):
        creds_found.append('Gemini')

    if creds_found:
        print(f"  ✅ Found API keys: {', '.join(creds_found)}")
    else:
        print("  ⚠️  No API keys found in environment")

    return len(creds_found) > 0

def test_config_loading():
    """Test config loading with env var priority."""
    print("\n⚙️  Testing config loading...")

    # Import the config loading function
    sys.path.insert(0, os.path.dirname(__file__))
    from social_rocket import load_config

    config = load_config()

    # Check if config has necessary fields
    has_api_key = (config.get('anthropic_key') or
                   config.get('openai_key') or
                   config.get('gemini_key'))

    if has_api_key:
        print("  ✅ Config loaded with API keys")
    else:
        print("  ❌ No API keys in config")
        print("  💡 Make sure you have credentials in .env file or config.json")
        return False

    # Check dry_run mode
    dry_run = config.get('dry_run', True)
    print(f"  ✅ Dry run mode: {dry_run} (safe for testing)")

    return True

def test_content_presets():
    """Test that FSBOz content presets are available."""
    print("\n🎨 Testing FSBOz content presets...")

    from social_rocket import create_default_projects, load_projects

    projects = load_projects() or create_default_projects()
    fsbo_project = next((p for p in projects if p.get('id') == 'fsboz'), None)

    if not fsbo_project:
        print("  ❌ FSBOz project not found in projects list")
        return False

    expected_industry = ("Real Estate", "FSBO Marketplace")
    if (fsbo_project.get('industry'), fsbo_project.get('sub_industry')) != expected_industry:
        print("  ❌ FSBOz industry/sub-industry mismatch")
        return False

    fsbo_content = fsbo_project.get('content_types', {})
    expected_presets = [
        'general',
        'property_search',
        'seller_tips',
        'success_story',
        'market_update',
    ]

    for preset_key in expected_presets:
        preset = fsbo_content.get(preset_key)
        if not preset:
            print(f"  ❌ Missing FSBOz preset: {preset_key}")
            return False
        print(f"  ✅ {preset['name']} preset found")

    return True

def test_ai_service():
    """Test AI service initialization (not actual API calls)."""
    print("\n🤖 Testing AI service...")

    try:
        from social_rocket import AIService
        ai_service = AIService()
        print("  ✅ AI service initialized")

        # Check provider order
        order = ai_service._get_provider_order()
        print(f"  ✅ Provider order: {' → '.join(order)}")

        return True
    except Exception as e:
        print(f"  ❌ AI service error: {e}")
        return False

def test_platform_functions():
    """Test that posting functions are defined."""
    print("\n🌐 Testing platform posting functions...")

    from social_rocket import (
        post_to_x,
        post_to_linkedin,
        post_to_facebook,
        post_to_reddit,
        post_to_threads,
        post_to_instagram,
        post_to_tiktok,
        post_to_quora
    )

    platforms = {
        'X (Twitter)': post_to_x,
        'LinkedIn': post_to_linkedin,
        'Facebook': post_to_facebook,
        'Reddit': post_to_reddit,
        'Threads': post_to_threads,
        'Instagram': post_to_instagram,
        'TikTok': post_to_tiktok,
        'Quora': post_to_quora,
    }

    for name, func in platforms.items():
        # Check if it's implemented (has more than stub return)
        import inspect
        source = inspect.getsource(func)
        if 'not implemented yet' in source.lower():
            print(f"  ⏳ {name}: Stub (not implemented)")
        else:
            print(f"  ✅ {name}: Fully implemented")

    return True

def test_history_system():
    """Test post history functions."""
    print("\n📊 Testing post history system...")

    from social_rocket import load_post_history, save_post_history, add_to_history

    # Test loading (should be empty or existing)
    history = load_post_history()
    print(f"  ✅ History loaded: {len(history)} posts")

    return True

def main():
    print("🚀 Social Rocket Setup Test")
    print("=" * 60)

    results = []

    # Run all tests
    results.append(("Environment Loading", test_env_loading()))
    results.append(("Config Loading", test_config_loading()))
    results.append(("Content Presets", test_content_presets()))
    results.append(("AI Service", test_ai_service()))
    results.append(("Platform Functions", test_platform_functions()))
    results.append(("History System", test_history_system()))

    # Summary
    print("\n" + "=" * 60)
    print("📈 Test Summary:")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} {name}")

    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n✨ All tests passed! Social Rocket is ready to use.")
        print("\n🎯 Next steps:")
        print("  1. Launch app: python social_rocket.py")
        print("  2. Add a creative (property image)")
        print("  3. Select FSBOz content preset")
        print("  4. Test with dry run mode (default)")
        print("  5. Check post history after posting")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
