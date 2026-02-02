# Git Command Cheatsheet

## First Time Setup (One-Time Only)

```bash
# Configure your identity
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Check configuration
git config --list
```

## Creating Your First Repository

```bash
# Initialize git in your project folder
cd /path/to/your/project
git init

# Add remote GitHub repository
git remote add origin https://github.com/USERNAME/REPO_NAME.git

# Verify remote
git remote -v
```

## Daily Workflow

```bash
# Check status (see what's changed)
git status

# Add all changes
git add .

# Or add specific files
git add file1.py file2.py

# Commit with message
git commit -m "Brief description of changes"

# Push to GitHub
git push

# Pull latest changes from GitHub
git pull
```

## Branching (Advanced)

```bash
# Create new branch
git checkout -b feature-name

# Switch between branches
git checkout main
git checkout feature-name

# Merge branch into main
git checkout main
git merge feature-name

# Delete branch
git branch -d feature-name
```

## Undoing Changes

```bash
# Unstage file (undo git add)
git reset HEAD file.py

# Discard local changes to file
git checkout -- file.py

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes) ⚠️ CAREFUL
git reset --hard HEAD~1
```

## Viewing History

```bash
# View commit history
git log

# Compact view
git log --oneline

# See what changed
git diff

# See staged changes
git diff --staged
```

## Common Scenarios

### "I want to start over"
```bash
rm -rf .git
git init
```

### "I committed to wrong branch"
```bash
git log  # Copy the commit hash
git checkout correct-branch
git cherry-pick COMMIT_HASH
```

### "I need to ignore files I already committed"
```bash
# Add to .gitignore first, then:
git rm --cached file.py
git commit -m "Remove tracked file"
```

## GitHub Authentication

### Personal Access Token
1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. Select scopes: `repo`
4. Use token as password when pushing

### SSH (Recommended for frequent use)
```bash
# Generate key
ssh-keygen -t ed25519 -C "your.email@example.com"

# Copy public key
cat ~/.ssh/id_ed25519.pub

# Add to GitHub: Settings → SSH Keys
# Change remote to SSH
git remote set-url origin git@github.com:USERNAME/REPO_NAME.git
```

## Quick Reference

| Command | What it does |
|---------|--------------|
| `git init` | Start tracking project with git |
| `git add .` | Stage all changes |
| `git commit -m "msg"` | Save changes with message |
| `git push` | Upload to GitHub |
| `git pull` | Download from GitHub |
| `git status` | See what's changed |
| `git log` | View history |
| `git diff` | See exact changes |
| `git branch` | List branches |
| `git checkout -b name` | Create new branch |

## Getting Help

```bash
# Get help for any command
git help commit
git commit --help

# Quick help
git commit -h
```

## Pro Tips

1. **Commit often** - Small commits are easier to manage
2. **Write good commit messages** - Future you will thank you
3. **Pull before push** - Avoid merge conflicts
4. **Use branches** for experimental features
5. **Review changes** with `git diff` before committing
6. **`.gitignore`** - Add files you don't want tracked

## Common Error Messages

### "fatal: not a git repository"
→ You're not in a git-initialized folder. Run `git init`

### "Permission denied (publickey)"
→ SSH key issue. Use HTTPS or fix SSH keys

### "Updates were rejected"
→ Remote has changes you don't have. Run `git pull` first

### "Please commit your changes or stash them"
→ You have uncommitted changes. Commit or use `git stash`

## Emergency: "I messed up everything!"

```bash
# If you haven't pushed yet
git reset --hard HEAD

# If you pushed bad commits
git revert HEAD
git push

# Nuclear option (lose everything)
git reset --hard origin/main
```

Remember: Git is forgiving - most mistakes can be fixed! Don't panic.
