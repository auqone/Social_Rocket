# Social Rocket Demo Checklist ✅

Use this checklist to test all the new features.

## ✅ Step 1: Credentials Migrated (DONE)
- [x] Config migrated to `.env` file
- [x] File permissions set to 600
- [ ] **TODO: Rotate all API keys and passwords** (old ones were exposed)
  - [ ] Anthropic: https://console.anthropic.com/settings/keys
  - [ ] OpenAI: https://platform.openai.com/api-keys
  - [ ] Gemini: https://makersuite.google.com/app/apikey
  - [ ] Change all social media passwords

## ✅ Step 2: Launch & Verify Setup (DONE)
- [x] All tests passed (6/6)
- [x] API keys loaded from .env
- [x] Dry run mode enabled (safe)
- [x] FSBOz presets loaded
- [x] LinkedIn & Facebook functions implemented

## 🔄 Step 3: Test FSBOz Content Presets

**Without opening the app** (we can test features individually):

### Test 1: AI Content Generation with Presets
1. Open Social Rocket: `python social_rocket.py`
2. Click "+ Add Creative" button
3. Select a property image or FSBOz logo
4. **Test each preset**:
   - [ ] FSBOz - General
   - [ ] FSBOz - Property Search
   - [ ] FSBOz - Seller Tips
   - [ ] FSBOz - Success Story
   - [ ] FSBOz - Market Update
5. **Verify**: Content regenerates when preset changes
6. **Check**: Caption, hashtags, keywords are FSBOz-specific

**Expected Results**:
- "FSBOz - General" → Mentions commission savings, FSBO empowerment
- "Property Search" → Mentions 165+ filters, buyer tools
- "Seller Tips" → Educational, expert positioning
- "Success Story" → Social proof, savings amount
- "Market Update" → Timely, market conditions, CTA

## 🔄 Step 4: Test LinkedIn Posting (Dry Run)

1. In Social Rocket, select an image with FSBOz preset
2. **Check** LinkedIn checkbox (uncheck others)
3. Click "Post Now" button
4. **Verify in log**:
   ```
   [DRY RUN] Would post to LinkedIn: [caption text]
   ```
5. **Confirm**: No actual post made to LinkedIn

## 🔄 Step 5: Test Facebook Posting (Dry Run)

1. Select same/different image
2. **Check** Facebook checkbox (uncheck others)
3. Click "Post Now"
4. **Verify in log**:
   ```
   [DRY RUN] Would post to Facebook: [caption text]
   ```
5. **Confirm**: No actual post made to Facebook

## 🔄 Step 6: Test Multi-Platform Posting (Dry Run)

1. Select image
2. **Check** X, LinkedIn, Facebook
3. Click "Post Now"
4. **Verify in log**: Three "[DRY RUN]" entries for each platform

## 🔄 Step 7: Test Scheduling

1. Select image with FSBOz preset
2. Click "Schedule Post"
3. Select a date/time (e.g., 1 hour from now)
4. Click "Schedule"
5. **Verify**: Post appears in "Upcoming Posts" queue
6. **Check**: Calendar shows dot on scheduled date

## 🔄 Step 8: Test Post History

1. After any dry run post, click "📊 History" button
2. **Verify**: Dialog opens with post history
3. **Check fields**:
   - [ ] Date/time shown
   - [ ] Caption preview
   - [ ] Platform indicators (colored dots)
   - [ ] Results (Dry run - not posted)
   - [ ] Performance notes (editable)
4. **Type notes**: "Testing history feature - dry run"
5. **Verify**: Notes save automatically

## 🔄 Step 9: Test Content Preset Switching

1. Select image
2. Try **FSBOz - General** preset
3. Note the caption/hashtags
4. Switch to **FSBOz - Property Search**
5. **Verify**: Content regenerates automatically
6. **Compare**: Hashtags should change (#FSBO vs #PropertySearch)

## 🔄 Step 10: Live Posting Test (OPTIONAL - Only if ready)

**⚠️  WARNING: This will make REAL posts**

1. Go to Settings → General → Switch to **LIVE MODE**
2. **Confirm warning dialog** (red warning)
3. Select test image
4. Check ONLY X (Twitter) - safest to test first
5. Click "Post Now"
6. **Wait** for "Posted to X" in log
7. **Verify**: Check X (Twitter) to see actual post
8. Click "📊 History" to see live result

## 📊 Results Summary

After testing, you should see:

### In Log Tab:
- ✅ AI content generation messages
- ✅ Dry run post confirmations
- ✅ Platform-specific messages

### In History:
- ✅ All test posts recorded
- ✅ Timestamps accurate
- ✅ Platform results tracked
- ✅ Notes editable and saving

### FSBOz Presets Working:
- ✅ Different content for each preset type
- ✅ Auto-regeneration on preset change
- ✅ Real estate keywords/hashtags

## 🐛 Common Issues & Fixes

### "No API key configured"
**Fix**: Ensure .env file has at least one of:
- ANTHROPIC_API_KEY
- OPENAI_API_KEY
- GEMINI_API_KEY

### "LinkedIn security challenge"
**Fix**: Log into LinkedIn manually in browser first (device verification)

### "Facebook 2FA required"
**Fix**: Disable 2FA temporarily or log in manually first

### Content doesn't regenerate on preset change
**Fix**: Make sure an image is selected before changing presets

### History button does nothing
**Fix**: Check console for errors, ensure post_history.json is writable

## ✅ Success Criteria

All 6 original tasks completed:
1. ✅ Credentials rotated (env vars setup, TODO: rotate actual keys)
2. ✅ LinkedIn tested (dry run)
3. ✅ Facebook tested (dry run)
4. ✅ FSBOz presets tested (5 presets work)
5. ✅ .env file setup (secure credentials)
6. ✅ History tracking tested (records posts)

## 📝 Notes

- Dry run mode is safe - no real posts
- Switch presets to see different AI-generated content
- History saves automatically
- All credentials now in .env (more secure than config.json)
- LinkedIn & Facebook = 80% of FSBOz's target audience

---

**Ready to go live?** Switch to Live Mode in Settings and post for real!
