# Contributing to Collaborative Coding Agent

First off, thanks for considering contributing! 🎉

## How Can I Contribute?

### Reporting Bugs

If you find a bug, please open an issue with:
- Clear title describing the bug
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, Ollama version)
- Relevant logs from `~/.collaborative_agent/logs/`

### Suggesting Enhancements

Enhancement suggestions are welcome! Please:
- Use a clear, descriptive title
- Explain the use case and benefits
- Provide examples if possible

### Code Contributions

1. **Fork the repository**

2. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow existing code style
   - Add docstrings to new functions
   - Update README if needed
   - Add tests if applicable

4. **Test your changes**
   ```bash
   # Run the agent
   ./collaborative_agent_pro.py
   
   # Test specific features
   pytest tests/
   ```

5. **Commit your changes**
   ```bash
   git commit -m "Add feature: brief description"
   ```

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request**
   - Reference any related issues
   - Describe what changed and why
   - Include screenshots for UI changes

## Code Style Guidelines

### Python Style
- Follow PEP 8
- Use type hints where appropriate
- Keep functions focused and small
- Add docstrings to public functions

Example:
```python
def parse_response(text: str) -> Dict[str, Any]:
    """
    Parse AI model response into structured format.
    
    Args:
        text: Raw response text from model
        
    Returns:
        Dictionary containing parsed sections
        
    Raises:
        ValueError: If response format is invalid
    """
    # Implementation here
    pass
```

### Commit Messages
- Use present tense ("Add feature" not "Added feature")
- Start with a verb
- Keep first line under 50 characters
- Add detailed description if needed

Good examples:
```
Add support for TypeScript projects
Fix code extraction for incomplete responses
Update README with new template examples
```

## Testing

If you add new features, please include tests:

```python
# tests/test_new_feature.py
def test_new_feature():
    """Test that new feature works as expected"""
    result = new_feature("input")
    assert result == "expected_output"
```

## Project Structure

```
collaborative-coding-agent/
├── collaborative_agent_pro.py    # Main application
├── README.md                      # Documentation
├── requirements.txt               # Dependencies
├── tests/                         # Test files
│   └── test_*.py
└── .github/                       # GitHub specific
    └── workflows/
        └── tests.yml              # CI/CD pipeline
```

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/collaborative-coding-agent.git
cd collaborative-coding-agent

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest black flake8 mypy

# Run tests
pytest

# Format code
black collaborative_agent_pro.py

# Check style
flake8 collaborative_agent_pro.py
```

## Questions?

Feel free to:
- Open an issue for questions
- Start a discussion in the Discussions tab
- Reach out to maintainers

## Code of Conduct

Be respectful and constructive. We're all here to build something useful together.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thanks for contributing! 🚀
