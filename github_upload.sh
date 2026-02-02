#!/bin/bash

# GitHub First Upload Helper Script
# This script automates the process of uploading your project to GitHub

set -e  # Exit on error

echo "🚀 GitHub First Upload Helper"
echo "=============================="
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Please install git first:"
    echo "   sudo apt install git"
    exit 1
fi

echo "✓ Git is installed"
echo ""

# Check if git is already initialized
if [ -d ".git" ]; then
    echo "⚠️  Git repository already exists in this directory."
    read -p "Do you want to remove it and start fresh? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf .git
        echo "✓ Removed existing git repository"
    else
        echo "Exiting..."
        exit 1
    fi
fi

# Check git config
echo "Checking git configuration..."
GIT_NAME=$(git config --global user.name 2>/dev/null || echo "")
GIT_EMAIL=$(git config --global user.email 2>/dev/null || echo "")

if [ -z "$GIT_NAME" ]; then
    echo ""
    read -p "Enter your name for git commits: " GIT_NAME
    git config --global user.name "$GIT_NAME"
fi

if [ -z "$GIT_EMAIL" ]; then
    echo ""
    read -p "Enter your email for git commits: " GIT_EMAIL
    git config --global user.email "$GIT_EMAIL"
fi

echo "✓ Git configured as: $GIT_NAME <$GIT_EMAIL>"
echo ""

# Get GitHub repository details
echo "GitHub Repository Setup"
echo "-----------------------"
read -p "Enter your GitHub username: " GITHUB_USER
read -p "Enter repository name (e.g., collaborative-coding-agent): " REPO_NAME

REPO_URL="https://github.com/$GITHUB_USER/$REPO_NAME.git"

echo ""
echo "⚠️  IMPORTANT: Before continuing, create the repository on GitHub:"
echo "   1. Go to https://github.com/new"
echo "   2. Repository name: $REPO_NAME"
echo "   3. DO NOT initialize with README, .gitignore, or license"
echo "   4. Click 'Create repository'"
echo ""
read -p "Have you created the repository on GitHub? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please create the repository first, then run this script again."
    exit 1
fi

# Initialize git
echo ""
echo "Initializing git repository..."
git init
echo "✓ Git initialized"

# Create .gitignore if it doesn't exist
if [ ! -f ".gitignore" ]; then
    echo "Creating .gitignore..."
    cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/
.env
.vscode/
.idea/
*.log
projects/*/CONTEXT_REPORT.md
.DS_Store
EOF
    echo "✓ Created .gitignore"
fi

# Check for README
if [ ! -f "README.md" ]; then
    echo "⚠️  No README.md found. You should create one!"
    echo "   (The files I provided include a comprehensive README)"
fi

# Add files
echo ""
echo "Adding files to git..."
git add .
echo "✓ Files staged"

# Show what will be committed
echo ""
echo "Files to be committed:"
git status --short
echo ""

read -p "Continue with commit? (Y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "Commit cancelled"
    exit 1
fi

# Commit
echo ""
echo "Creating initial commit..."
git commit -m "Initial commit: Collaborative Coding Agent v4.2.1"
echo "✓ Committed"

# Add remote
echo ""
echo "Adding GitHub remote..."
git remote add origin "$REPO_URL"
echo "✓ Remote added: $REPO_URL"

# Rename branch to main
echo ""
echo "Setting default branch to 'main'..."
git branch -M main
echo "✓ Branch renamed to main"

# Push
echo ""
echo "🚀 Pushing to GitHub..."
echo "   You may need to authenticate:"
echo "   - Username: $GITHUB_USER"
echo "   - Password: Use Personal Access Token (NOT your GitHub password)"
echo ""
echo "   To create a token:"
echo "   1. Go to https://github.com/settings/tokens"
echo "   2. Generate new token (classic)"
echo "   3. Select 'repo' scope"
echo "   4. Copy and paste the token when prompted"
echo ""

git push -u origin main

echo ""
echo "=============================="
echo "✅ SUCCESS!"
echo "=============================="
echo ""
echo "Your code is now on GitHub at:"
echo "https://github.com/$GITHUB_USER/$REPO_NAME"
echo ""
echo "Next steps:"
echo "  1. Visit your repository and verify files uploaded correctly"
echo "  2. Add a description and topics to your repository"
echo "  3. Share the link with others!"
echo ""
echo "For future updates, just run:"
echo "  git add ."
echo "  git commit -m 'Description of changes'"
echo "  git push"
echo ""
