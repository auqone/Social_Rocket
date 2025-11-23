#!/usr/bin/env python3
"""
Manual X/Twitter login helper.
Opens a browser with persistent session so you can log in manually.
After login, close the browser and Social Rocket will use the saved session.
"""
import os
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
session_dir = os.path.join(BASE_DIR, ".browser_sessions", "x_session")
os.makedirs(session_dir, exist_ok=True)

print("=" * 60)
print("X/TWITTER MANUAL LOGIN HELPER")
print("=" * 60)
print()
print("This will open a browser window where you can:")
print("1. Log into X/Twitter manually")
print("2. Complete any verification steps")
print("3. Once logged in, you can close this window")
print()
print("The session will be saved and Social Rocket will use it.")
print()
input("Press ENTER to open the browser...")

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        session_dir,
        headless=False,
        viewport={"width": 1280, "height": 720},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    page = context.pages[0] if context.pages else context.new_page()

    print("\nOpening X/Twitter...")
    page.goto("https://x.com/login")

    print("\n" + "=" * 60)
    print("INSTRUCTIONS:")
    print("=" * 60)
    print("1. Log into X in the browser window that just opened")
    print("2. Complete any verification (phone, email, etc.)")
    print("3. Make sure you see your home feed")
    print("4. Then CLOSE THIS TERMINAL (Ctrl+C) or the browser")
    print()
    print("The session will be saved automatically!")
    print("=" * 60)

    # Keep browser open until user closes it
    try:
        page.wait_for_timeout(300000)  # Wait up to 5 minutes
    except KeyboardInterrupt:
        print("\n\nSession saved! You can now use Social Rocket.")

    context.close()

print("\nDone! Social Rocket will now use this logged-in session.")
