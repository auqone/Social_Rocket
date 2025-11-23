# Security Notice 🔒

## URGENT: Your `config.json` Contains Exposed Credentials

**Your current `config.json` file contains API keys and passwords in plaintext that may be committed to your git repository.**

### Immediate Actions Required

1. **Rotate ALL credentials in `config.json`**:
   - Anthropic API key
   - OpenAI API key
   - Gemini API key
   - All social media passwords

2. **Check git history**:
   ```bash
   git log --all --full-history -- config.json
   ```
   If `config.json` was ever committed, those credentials are exposed.

3. **Remove from git history** (if needed):
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch config.json" \
     --prune-empty --tag-name-filter cat -- --all
   ```

4. **Verify `.gitignore`**:
   ```bash
   cat .gitignore | grep config.json
   ```
   Should show `config.json` is ignored (already configured).

### Secure Credential Management

Choose one of these secure methods going forward:

#### Option 1: 1Password CLI (Recommended for Teams)
```bash
# Install 1Password CLI
brew install --cask 1password-cli

# Enable in 1Password app:
# Settings → Developer → Connect with 1Password CLI

# Store credentials in items named:
# - "X (Twitter)"
# - "LinkedIn"
# - "Facebook"
# etc.

# Social Rocket will auto-fetch with biometric unlock
```

**Benefits**:
- No credentials in files
- Biometric unlock
- Team credential sharing
- Audit logs

#### Option 2: Environment Variables (Recommended for Solo)
```bash
# Copy template
cp .env.example .env

# Edit .env with real credentials
nano .env

# Load before running
export $(cat .env | xargs)
python social_rocket.py

# Or use python-dotenv (add to requirements.txt)
pip install python-dotenv
```

**Benefits**:
- Not in code/config files
- Per-environment configs
- Server-friendly

#### Option 3: Keep Using config.json (Least Secure)

If you must use `config.json`:

1. **Ensure it's in `.gitignore`** ✓ (already done)
2. **Never commit it** to git
3. **Keep backups** in a secure location
4. **Rotate credentials** regularly
5. **Restrict file permissions**:
   ```bash
   chmod 600 config.json
   ```

### Current Exposure Assessment

Based on your `config.json`:

- ❌ **Anthropic API key** - Exposed (can rack up charges)
- ❌ **OpenAI API key** - Exposed (can rack up charges)
- ❌ **Gemini API key** - Exposed (can rack up charges)
- ❌ **X/Twitter credentials** - Exposed (account takeover risk)
- ❌ **LinkedIn credentials** - Exposed (account takeover risk)
- ❌ **Facebook credentials** - Exposed (account takeover risk)
- ❌ **Instagram credentials** - Exposed (account takeover risk)
- ❌ **Reddit credentials** - Exposed (account takeover risk)

### How to Rotate Credentials

#### API Keys:
- **Anthropic**: https://console.anthropic.com/settings/keys
- **OpenAI**: https://platform.openai.com/api-keys
- **Google AI**: https://makersuite.google.com/app/apikey

#### Social Media:
- Change passwords through each platform's security settings
- Enable 2FA (may require manual login for automation)

### Prevention Checklist

- [ ] Rotated all API keys
- [ ] Changed all social media passwords
- [ ] Checked git history for config.json
- [ ] Verified config.json in .gitignore
- [ ] Set up 1Password CLI or .env file
- [ ] Deleted sensitive data from config.json
- [ ] Set restrictive file permissions (chmod 600)
- [ ] Enabled 2FA on social accounts
- [ ] Reviewed GitHub/GitLab for accidental commits
- [ ] Checked any shared/backup locations

### Questions?

This security model is standard for applications handling credentials. The improvements prioritize:

1. **1Password CLI** - Best for security, teams, and audit trails
2. **Environment variables** - Good for development and deployment
3. **Config file** - Convenient but requires discipline

Need help setting up secure credential management? Check the README.md for detailed instructions.

---

**Remember**: Exposed API keys can result in unexpected charges. Exposed social media credentials can lead to account takeover. Take this seriously.
