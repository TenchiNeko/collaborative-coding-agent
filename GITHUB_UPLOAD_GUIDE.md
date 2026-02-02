# GitHub Upload Guide - First Time Setup

## Prerequisites Check

Before we start, verify you have:
- [ ] Git installed (`git --version`)
- [ ] GitHub account created (https://github.com/signup)

---

## Step 1: Install Git (if needed)

```bash
# Check if git is installed
git --version

# If not installed, install it:
# Ubuntu/Debian:
sudo apt update && sudo apt install git

# Or download from: https://git-scm.com/downloads
```

---

## Step 2: Configure Git (First Time Only)

```bash
# Set your name (will appear in commits)
git config --global user.name "Your Name"

# Set your email (use your GitHub email)
git config --global user.email "your.email@example.com"

# Verify settings
git config --list
```

---

## Step 3: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `collaborative-coding-agent` (or your choice)
3. Description: "Sequential AI coding agent with context tracking and iterative refinement"
4. **Choose visibility:**
   - ✅ **Public** (recommended for portfolio/sharing)
   - 🔒 **Private** (if you want to keep it private)
5. **DO NOT** check "Add a README file" (we already have one)
6. **DO NOT** add .gitignore or license yet
7. Click "Create repository"

---

## Step 4: Prepare Your Local Repository

```bash
# Navigate to your project directory
cd /path/to/your/collaborative_agent_pro.py/directory

# Initialize git repository
git init

# Check status
git status
```

---

## Step 5: Create Essential Files

You'll need to create these files (I'll provide them):
- README.md
- .gitignore
- LICENSE (optional but recommended)
- requirements.txt

---

## Step 6: Add Files to Git

```bash
# Add all files to staging
git add .

# Or add specific files:
git add collaborative_agent_pro.py
git add README.md
git add .gitignore
git add requirements.txt

# Check what's staged
git status

# Create your first commit
git commit -m "Initial commit: Collaborative Coding Agent v4.2.1"
```

---

## Step 7: Connect to GitHub

```bash
# Add GitHub as remote (replace USERNAME and REPO_NAME)
git remote add origin https://github.com/USERNAME/REPO_NAME.git

# For example:
# git remote add origin https://github.com/brandongray/collaborative-coding-agent.git

# Verify remote
git remote -v
```

---

## Step 8: Push to GitHub

```bash
# Rename branch to 'main' (GitHub's default)
git branch -M main

# Push your code to GitHub
git push -u origin main
```

### If you get authentication errors:

**Option A: Personal Access Token (Recommended)**
1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a name: "Collaborative Agent Upload"
4. Select scopes: `repo` (full control)
5. Generate and **COPY THE TOKEN** (you won't see it again!)
6. When prompted for password, paste the token

**Option B: SSH Keys** (Better for frequent use)
```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your.email@example.com"

# Start ssh-agent
eval "$(ssh-agent -s)"

# Add key
ssh-add ~/.ssh/id_ed25519

# Copy public key
cat ~/.ssh/id_ed25519.pub

# Add to GitHub: Settings → SSH and GPG keys → New SSH key
# Then change remote to SSH:
git remote set-url origin git@github.com:USERNAME/REPO_NAME.git
```

---

## Step 9: Verify Upload

1. Go to https://github.com/USERNAME/REPO_NAME
2. You should see all your files!
3. GitHub will automatically display your README.md

---

## Common Commands for Future Updates

```bash
# Check status
git status

# Add changes
git add .

# Commit changes
git commit -m "Description of changes"

# Push to GitHub
git push

# Pull latest changes
git pull

# View commit history
git log --oneline
```

---

## Troubleshooting

### "Repository not found"
- Double-check the remote URL
- Verify repository name matches

### "Permission denied"
- Check your access token or SSH key
- Verify you're logged into correct GitHub account

### "Already exists and is not an empty directory"
- You already have a git repo here
- Run `rm -rf .git` to start fresh (BE CAREFUL)

### "Refusing to merge unrelated histories"
```bash
git pull origin main --allow-unrelated-histories
```

---

## Next Steps After Upload

1. ✅ Add repository description on GitHub
2. ✅ Add topics/tags (python, ai, coding-agent, ollama)
3. ✅ Star your own repo (why not! 😄)
4. ✅ Share the link
5. ✅ Consider adding:
   - CONTRIBUTING.md (if you want contributions)
   - GitHub Actions for CI/CD
   - Documentation folder
   - Example projects

---

## GitHub Profile Boost

Make your repo stand out:
- Add shields/badges to README (build status, version, etc.)
- Add screenshots or demo GIFs
- Create a detailed "Features" section
- Add installation instructions
- Include usage examples
- Add a "Roadmap" or "Future Features" section

---

## Questions?

If you get stuck:
1. Check the error message carefully
2. Google: "git [error message]"
3. GitHub Docs: https://docs.github.com
4. Ask me for help!

**Pro tip:** Make small commits often rather than huge commits rarely. Good commit messages help you track changes!
