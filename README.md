# Collaborative Coding Agent Pro

**Sequential AI-powered code generation with context tracking and iterative refinement**

A sophisticated Python-based coding agent that uses multiple AI models (via Ollama) to plan, generate, and refine multi-file projects through intelligent collaboration.

## 🌟 Features

### Core Capabilities
- **Sequential Multi-File Generation**: Generates complex projects file-by-file with full context awareness
- **Dual-Model Architecture**: Manager model for planning, Coder model for implementation
- **Context Tracking**: Maintains project-wide context across all generated files
- **Iterative Refinement**: Improve code quality through feedback loops
- **Template Library**: Pre-built templates for common project types
- **Auto-Testing**: Integrated pytest execution with detailed reporting
- **Progress Visibility**: Real-time context reports and progress tracking

### v4.2.1 Improvements
- ✅ Manual target paths now properly respected
- ✅ Better code extraction for incomplete responses
- ✅ Improved path resolution (absolute and relative)
- ✅ Enhanced sequential file generation workflow

## 📋 Requirements

### System Requirements
- Python 3.8+
- [Ollama](https://ollama.ai/) running locally or remotely
- Git (for project management features)

### AI Models
At least one of these models installed in Ollama:
- **GLM-4.7-Flash** (`glm-4.7-flash:latest`) - Fast, lightweight
- **Qwen 2.5 Coder 32B** (`qwen2.5-coder:32b-instruct-q8_0`) - High quality, larger

Manager model (auto-selected):
- Llama 3.2 or Llama 3 variants

### Python Dependencies
```bash
pip install requests pyyaml
pip install pytest  # Optional, for auto-testing
```

## 🚀 Quick Start

### 1. Install Ollama and Models

```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull required models
ollama pull glm-4.7-flash:latest
ollama pull qwen2.5-coder:32b-instruct-q8_0
ollama pull llama3.2:latest
```

### 2. Clone and Run

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/collaborative-coding-agent.git
cd collaborative-coding-agent

# Make executable
chmod +x collaborative_agent_pro.py

# Run the agent
./collaborative_agent_pro.py
```

### 3. Environment Variables (Optional)

```bash
# Custom Ollama hosts
export MANAGER_OLLAMA_HOST="http://localhost:11434"
export CODER_OLLAMA_HOST="http://localhost:11434"

# Custom models
export GLM_MODEL="glm-4.7-flash:latest"
export QWEN_MODEL="qwen2.5-coder:32b-instruct-q8_0"
export DEFAULT_CODER_MODEL="glm-4.7-flash:latest"
export MANAGER_MODEL="llama3.2:latest"

# Custom project directory
export PROJECTS_DIR="./projects"
```

## 💡 Usage Examples

### Basic Project Generation

```
💬 You: Create a Flask REST API for a todo list with SQLite database

🧠 Manager thinking...
✓ Responded in 3.2s

🎯 Targets: app.py, models.py, routes.py, config.py

💬 You: execute

📁 Project: todo_api_20250202_143022
🔄 Sequential Generation: 4 files
🤖 Using GLM (glm-4.7-flash:latest)

📝 File 1/4: app.py
✓ Wrote app.py (1,234 chars, 8.2s)

[... continues for all files ...]

✅ SUCCESS
📝 Generated: 4/4 files
⏱️  Total Time: 32.5s
📁 Project: ./projects/todo_api_20250202_143022
```

### Using Templates

```
💬 You: templates

📄 Available Templates:
  • web_api: RESTful API with Flask (medium)
  • cli_tool: Command-line tool with argparse (simple)
  • data_pipeline: ETL data pipeline (complex)
  • scraper: Web scraper with Beautiful Soup (medium)

💬 You: template web_api
  resource: users
  
✓ Using template. Asking manager...
```

### Manual Target Files

```
💬 You: :target src/main.py src/utils.py tests/test_main.py

✓ Targets: ['src/main.py', 'src/utils.py', 'tests/test_main.py']

💬 You: Create a CLI calculator with unit tests

💬 You: execute qwen
```

### Code Refinement

```
💬 You: refine

💬 Feedback for refinement: Add error handling for division by zero and improve logging

🔄 Refinement Round 1
🔧 Refining with glm-4.7-flash:latest...

✅ Refinement complete (Round 1)
⏱️  12.3s
📝 Updated: main.py, utils.py
✅ Tests: Passed
```

## 📚 Commands Reference

| Command | Description |
|---------|-------------|
| `execute` | Generate code with default model |
| `execute glm` | Generate using GLM model |
| `execute qwen` | Generate using Qwen model |
| `refine` | Improve code based on feedback |
| `manager` | Show last manager response |
| `templates` | List available templates |
| `template <name>` | Use a specific template |
| `:target file.py` | Set target files manually |
| `:history` | Show conversation history |
| `:clear` | Clear conversation and reset |
| `quit` | Exit the agent |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│              User Interface                      │
│        (Interactive CLI Session)                 │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│         Manager Model (Llama 3.2)                │
│  • Analyzes user request                         │
│  • Creates project plan                          │
│  • Defines file structure                        │
│  • Generates task breakdown                      │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│      Context Report Manager                      │
│  • Tracks completed files                        │
│  • Maintains integration notes                   │
│  • Provides sequential context                   │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│    Coder Model (GLM/Qwen) - Sequential           │
│  File 1 → Analyze → Generate → Save              │
│  File 2 → Context from File 1 → Generate         │
│  File N → Full project context → Generate        │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│         Project Output                           │
│  • Generated source files                        │
│  • Context report (CONTEXT_REPORT.md)            │
│  • README.md                                     │
│  • Test results (if applicable)                  │
└─────────────────────────────────────────────────┘
```

## 📁 Project Structure

Generated projects follow this structure:

```
projects/
└── project_name_20250202_143022/
    ├── README.md                  # Project overview
    ├── CONTEXT_REPORT.md          # Generation context (auto-updated)
    ├── .gitignore                 # Standard Python .gitignore
    ├── file1.py                   # Generated files
    ├── file2.py
    └── tests/
        └── test_file1.py
```

## 🔧 Configuration

The agent creates a configuration directory at `~/.collaborative_agent/`:

```
~/.collaborative_agent/
├── logs/                          # Execution logs
│   └── agent_pro_20250202_143022.log
└── templates/                     # Template library
    ├── web_api.yaml
    ├── cli_tool.yaml
    ├── data_pipeline.yaml
    └── scraper.yaml
```

## 🎯 Use Cases

### Perfect For:
- **Multi-file Python projects** with interdependencies
- **API development** (Flask, FastAPI, Django)
- **CLI tools** with multiple modules
- **Data pipelines** with ETL workflows
- **Web scrapers** with parsers and storage
- **Learning projects** with iterative improvement

### Not Ideal For:
- Single-file scripts (overkill)
- Non-Python projects (focused on Python)
- Projects requiring human design decisions
- Real-time collaborative editing

## 🐛 Troubleshooting

### "Manager model not found"
```bash
# Install a compatible manager model
ollama pull llama3.2:latest
# Or set custom model
export MANAGER_MODEL="llama3:8b"
```

### "No coder models available"
```bash
# Install at least one coder model
ollama pull glm-4.7-flash:latest
# Or
ollama pull qwen2.5-coder:32b-instruct-q8_0
```

### "Permission denied" on execution
```bash
chmod +x collaborative_agent_pro.py
```

### Code extraction failures
- Try switching models: `execute qwen` vs `execute glm`
- Simplify the request
- Check Ollama logs for model issues

## 📊 Performance Tips

1. **GLM for speed**: Fast iterations, simpler projects
2. **Qwen for quality**: Complex logic, production code
3. **GPU acceleration**: Use GPU-enabled Ollama for 2-3x speedup
4. **Sequential generation**: Better for large projects than single-shot
5. **Manual targets**: Use `:target` to control exactly what gets generated

## 🗺️ Roadmap

- [ ] Support for more languages (JavaScript, Go, Rust)
- [ ] Web UI interface
- [ ] Integration with VS Code
- [ ] Cloud model support (OpenAI, Anthropic)
- [ ] Automatic dependency installation
- [ ] Docker containerization
- [ ] CI/CD pipeline templates

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Built with [Ollama](https://ollama.ai/)
- Powered by GLM and Qwen AI models
- Inspired by the need for better AI-assisted development workflows

## 📧 Support

- **Issues**: https://github.com/YOUR_USERNAME/collaborative-coding-agent/issues
- **Discussions**: https://github.com/YOUR_USERNAME/collaborative-coding-agent/discussions

---

**Made with ❤️ for developers who want AI collaboration without the overhead**
