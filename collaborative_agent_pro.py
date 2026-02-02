#!/usr/bin/env python3
"""
================================================================================
COLLABORATIVE SEQUENTIAL CODING AGENT v4.2.1 PROFESSIONAL EDITION
================================================================================

FIXED in v4.2.1:
- Bug fix: Manual :target paths now properly respected (no new project creation)
- Bug fix: Manager project_name no longer overrides manual targets
- Bug fix: Better code extraction for incomplete/truncated responses
- Bug fix: Path resolution handles both absolute and relative paths correctly

NEW in v4.2:
- Sequential multi-file generation with context tracking
- Context report system (CONTEXT_REPORT.md per project)
- File dependency tracking and integration awareness
- Progress visibility and resume capability
- Token management for large projects
- Final integration review with full context

FIXED in v4.1:
- Bug fix: Respects manual :target paths (doesn't create new projects)
- Bug fix: Better code block extraction (uses largest complete block)
- Bug fix: Handles both relative and absolute target paths

v4.0 Features:
- Project folder organization (auto-creates timestamped folders)
- Manual model selection (user chooses GLM or Qwen)
- Auto-testing with pytest
- Iterative refinement with manager feedback
- Template library for common tasks
- Comprehensive error handling & naming validation
"""

from __future__ import annotations
import os, re, sys, time, shutil, subprocess, logging, json, yaml
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from enum import Enum
from pathlib import Path
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Setup logging
LOG_DIR = Path.home() / ".collaborative_agent" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"agent_pro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def now_s(): return time.time()
def which(cmd): return shutil.which(cmd)
def die(msg, code=2): logger.error(msg); print(msg); raise SystemExit(code)

def normalize_host(url, default):
    url = (url or "").strip()
    if not url: url = default
    if url.endswith("/"): url = url[:-1]
    if not url.startswith("http"): die(f"Host must start with http:// : {url}")
    return url

def build_http():
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=0.35, status_forcelist=(429,500,502,503,504))
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s

def sanitize_folder_name(name: str) -> str:
    """Sanitize project name for safe folder creation"""
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '_', name)
    name = name.strip('_')
    name = name[:50]
    if not name:
        name = "project"
    return name.lower()

class ModelRole(Enum):
    MANAGER = "manager"
    CODER = "coder"

@dataclass
class TaskComplexity:
    """Analyze task complexity for informational purposes"""
    file_count: int
    estimated_lines: int
    has_external_deps: bool
    complexity_score: float
    
    @classmethod
    def analyze(cls, spec: str, tasks: str, targets: List[str]) -> 'TaskComplexity':
        file_count = len(targets)
        task_list = [t.strip() for t in tasks.split('\n') if t.strip() and t.strip()[0].isdigit()]
        estimated_lines = len(task_list) * 20
        spec_lower = spec.lower()
        has_external_deps = any(keyword in spec_lower for keyword in [
            'flask', 'fastapi', 'django', 'requests', 'pandas', 'numpy',
            'sqlalchemy', 'pytest', 'api', 'database', 'web'
        ])
        score = 0
        score += min(file_count * 15, 30)
        score += min(estimated_lines / 10, 40)
        score += 30 if has_external_deps else 0
        return cls(file_count, estimated_lines, has_external_deps, score)

class OllamaClient:
    def __init__(self, base_url, http, role):
        self.base_url = base_url
        self.http = http
        self.role = role
    
    def list_models(self):
        logger.info(f"Fetching models from {self.base_url}")
        r = self.http.get(f"{self.base_url}/api/tags", timeout=10)
        r.raise_for_status()
        models = [m.get("name") for m in r.json().get("models", []) if m.get("name")]
        logger.info(f"Found {len(models)} models on {self.role.value} host")
        return models
    
    def generate(self, model, prompt, timeout=240):
        token_limit = 6000 if self.role == ModelRole.MANAGER else 4000
        logger.debug(f"Generating with {model} (limit: {token_limit} tokens)")
        r = self.http.post(f"{self.base_url}/api/generate", json={
            "model": model, "prompt": prompt, "stream": False, "keep_alive": "10m",
            "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": token_limit}
        }, timeout=timeout)
        if r.status_code != 200:
            logger.error(f"Ollama failed: {r.status_code}")
            raise RuntimeError(f"Ollama failed: {r.status_code}")
        return (r.json().get("response") or "").strip()
    
    def generate_stream(self, model, prompt, timeout=300):
        """Streaming generation with real-time output"""
        token_limit = 4000
        logger.debug(f"Streaming generation with {model} (limit: {token_limit} tokens)")
        
        r = self.http.post(f"{self.base_url}/api/generate", json={
            "model": model, "prompt": prompt, "stream": True, "keep_alive": "10m",
            "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": token_limit}
        }, timeout=timeout, stream=True)
        
        if r.status_code != 200:
            logger.error(f"Ollama failed: {r.status_code}")
            raise RuntimeError(f"Ollama failed: {r.status_code}")
        
        full_response = []
        for line in r.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    if 'response' in chunk:
                        text = chunk['response']
                        full_response.append(text)
                        yield text
                    if chunk.get('done', False):
                        break
                except json.JSONDecodeError:
                    continue
        
        return ''.join(full_response)
    
    def warmup(self, model):
        try:
            logger.info(f"Warming up {self.role.value} model: {model}")
            print(f"  🔥 Warming up {self.role.value} model: {model}")
            self.generate(model, "Hello", timeout=60)
            logger.info(f"{self.role.value} model ready")
            print(f"  ✓ Model ready")
        except Exception as e:
            logger.warning(f"Warmup failed: {e}")

SPEC_RE = re.compile(r"BEGIN_SPEC\s*(.*?)\s*END_SPEC", re.S)
TASKS_RE = re.compile(r"BEGIN_CODER_TASKS\s*(.*?)\s*END_CODER_TASKS", re.S)
READY_RE = re.compile(r"PLAN_READY:\s*(YES|NO)\b", re.I)
TARGETS_RE = re.compile(r"TARGET_FILES:\s*(.*?)\s*(?:PLAN_READY:|$)", re.S)
PROJECT_NAME_RE = re.compile(r"PROJECT_NAME:\s*(.+?)(?:\n|$)", re.I)

@dataclass
class ParseResult:
    spec: str
    tasks: str
    plan_ready: bool
    targets: List[str]
    project_name: Optional[str]
    validation_errors: List[str]
    
    @property
    def is_valid(self): return len(self.validation_errors) == 0

def parse_manager_payload(text):
    spec = tasks = ""
    plan_ready = False
    targets = []
    project_name = None
    errors = []
    
    m = SPEC_RE.search(text or "")
    if m: spec = m.group(1).strip()
    if not spec: errors.append("Missing or empty SPEC")
    
    m = TASKS_RE.search(text or "")
    if m: tasks = m.group(1).strip()
    if not tasks: errors.append("Missing or empty TASKS")
    
    m = READY_RE.search(text or "")
    if m: plan_ready = m.group(1).upper() == "YES"
    
    m = TARGETS_RE.search(text or "")
    if m:
        for line in m.group(1).splitlines():
            line = line.strip().lstrip("-").strip()
            if line and not line.lower().startswith("none"):
                targets.append(line)
    
    m = PROJECT_NAME_RE.search(text or "")
    if m: project_name = m.group(1).strip()
    
    if plan_ready and (not spec or not tasks or not targets):
        errors.append("PLAN_READY:YES but missing content")
    
    logger.debug(f"Parsed manager output: ready={plan_ready}, targets={targets}, project={project_name}, errors={errors}")
    return ParseResult(spec, tasks, plan_ready, targets, project_name, errors)

@dataclass
class ConversationTurn:
    role: str
    content: str
    timestamp: float

class ConversationHistory:
    def __init__(self, max_turns=20):
        self.turns = []
        self.max_turns = max_turns
    
    def add_user(self, content):
        self.turns.append(ConversationTurn("user", content, now_s()))
        if len(self.turns) > self.max_turns: self.turns = self.turns[-self.max_turns:]
        logger.debug(f"Added user turn: {content[:50]}...")
    
    def add_assistant(self, content):
        self.turns.append(ConversationTurn("assistant", content, now_s()))
        if len(self.turns) > self.max_turns: self.turns = self.turns[-self.max_turns:]
        logger.debug(f"Added assistant turn: {content[:50]}...")
    
    def get_context(self, max_chars=8000):
        if not self.turns: return ""
        lines = ["Previous conversation:"]
        total = 0
        for turn in reversed(self.turns):
            txt = f"\n{turn.role.upper()}: {turn.content}"
            if total + len(txt) > max_chars: break
            lines.insert(1, txt)
            total += len(txt)
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def clear(self): 
        logger.info("Clearing conversation history")
        self.turns.clear()

@dataclass
class Config:
    manager_host: str
    coder_host: str
    manager_model: str
    default_coder_model: str
    glm_model: str
    qwen_model: str
    projects_dir: Path
    templates_dir: Path

class ContextReportManager:
    """Manages project context across multi-file generation"""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.report_path = project_path / "CONTEXT_REPORT.md"
        self.completed_files = []
        self.pending_files = []
        self.current_file = None
        self.dependencies = {}
        self.integration_notes = []
        self.project_name = project_path.name
        self.start_time = datetime.now()
    
    def initialize(self, project_name: str, spec: str, targets: List[str]):
        """Create initial context report from manager's plan"""
        
        self.project_name = project_name
        self.pending_files = targets.copy()
        
        report = f"""# Project Context Report: {project_name}

**Generated:** {self.start_time.strftime("%Y-%m-%d %H:%M:%S")}
**Status:** INITIALIZED (0/{len(targets)} files complete)

## Project Overview
{spec}

## Architecture
{self._format_file_list(targets)}

## Completed Files ✅
(None yet)

## In Progress 🔄
### {targets[0]}
- Next to generate
- Status: PENDING

## Pending ⏳
{self._format_pending(targets[1:])}

## Integration Notes
(Will be updated as files are generated)

## Known Issues
(None yet)

## Next Steps
1. Generate {targets[0]}
2. Update context report
3. Continue to next file
"""
        self.report_path.write_text(report)
        logger.info(f"Initialized context report: {len(targets)} files")
    
    def _format_file_list(self, targets: List[str]) -> str:
        """Format file list with basic structure"""
        lines = []
        for target in targets:
            lines.append(f"- {target}")
        return "\n".join(lines)
    
    def _format_pending(self, targets: List[str]) -> str:
        """Format pending files list"""
        if not targets:
            return "(All files generated)"
        return "\n".join(f"- {t}" for t in targets)
    
    def mark_file_complete(self, filename: str, file_info: Dict):
        """Mark a file as complete and update context"""
        
        self.completed_files.append({
            'filename': filename,
            'size': file_info.get('size', 0),
            'functions': file_info.get('functions', []),
            'classes': file_info.get('classes', []),
            'dependencies': file_info.get('dependencies', []),
            'exports': file_info.get('exports', []),
            'timestamp': datetime.now()
        })
        
        if filename in self.pending_files:
            self.pending_files.remove(filename)
        
        self._update_report()
        logger.info(f"Marked {filename} complete in context report")
    
    def add_integration_note(self, note: str):
        """Add a note about file integration"""
        self.integration_notes.append({
            'note': note,
            'timestamp': datetime.now()
        })
        self._update_report()
    
    def get_context_for_file(self, filename: str) -> str:
        """Get relevant context for generating a specific file"""
        
        context_lines = [
            f"## Context for {filename}",
            "",
            "### Already Implemented:",
        ]
        
        if not self.completed_files:
            context_lines.append("(No files completed yet - this is the first file)")
        else:
            for file_info in self.completed_files:
                funcs = file_info['functions'][:5]
                classes = file_info['classes'][:3]
                context_lines.append(f"- **{file_info['filename']}** ({file_info['size']} bytes)")
                if funcs:
                    context_lines.append(f"  - Functions: {', '.join(funcs)}")
                if classes:
                    context_lines.append(f"  - Classes: {', '.join(classes)}")
        
        context_lines.extend([
            "",
            "### Available for Import:",
        ])
        
        if self.completed_files:
            for file_info in self.completed_files:
                module_name = file_info['filename'].replace('.py', '')
                exports = file_info['exports'][:5]
                if exports:
                    context_lines.append(f"- `from {module_name} import {', '.join(exports)}`")
        else:
            context_lines.append("(No modules available yet)")
        
        context_lines.extend([
            "",
            "### Integration Requirements:",
            "- Maintain consistent error handling (try/except with logging)",
            "- Include comprehensive docstrings for all public functions",
            "- Follow established patterns from completed files",
            "- Add type hints where appropriate",
        ])
        
        return "\n".join(context_lines)
    
    def _update_report(self):
        """Regenerate the full context report"""
        
        total = len(self.completed_files) + len(self.pending_files)
        completed_count = len(self.completed_files)
        
        if completed_count == total:
            status = f"COMPLETE ({completed_count}/{total} files)"
        else:
            status = f"IN_PROGRESS ({completed_count}/{total} files complete)"
        
        report_lines = [
            f"# Project Context Report: {self.project_name}",
            f"",
            f"**Started:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Status:** {status}",
            f"",
        ]
        
        # Progress bar
        progress_pct = (completed_count / total * 100) if total > 0 else 0
        progress_bar = "█" * int(progress_pct / 5) + "░" * (20 - int(progress_pct / 5))
        report_lines.extend([
            f"## Progress",
            f"```",
            f"[{progress_bar}] {progress_pct:.0f}%",
            f"```",
            f""
        ])
        
        # Completed files
        report_lines.append(f"## Completed Files ✅")
        
        if not self.completed_files:
            report_lines.append("(None yet)")
        else:
            for file_info in self.completed_files:
                elapsed = (file_info['timestamp'] - self.start_time).total_seconds()
                report_lines.extend([
                    f"",
                    f"### {file_info['filename']} ({file_info['size']} bytes)",
                    f"- **Completed:** {file_info['timestamp'].strftime('%H:%M:%S')} (+{elapsed:.0f}s)",
                ])
                
                if file_info['functions']:
                    report_lines.append(f"- **Functions:** {', '.join(file_info['functions'])}")
                if file_info['classes']:
                    report_lines.append(f"- **Classes:** {', '.join(file_info['classes'])}")
                if file_info['dependencies']:
                    report_lines.append(f"- **Dependencies:** {', '.join(file_info['dependencies'])}")
        
        report_lines.append("")
        
        # Pending files
        if self.pending_files:
            report_lines.extend([
                f"## Pending ⏳",
                f"",
            ])
            for pf in self.pending_files:
                report_lines.append(f"- {pf}")
            report_lines.append("")
        
        # Integration notes
        if self.integration_notes:
            report_lines.extend([
                f"## Integration Notes",
                f"",
            ])
            for note_info in self.integration_notes:
                time_str = note_info['timestamp'].strftime('%H:%M:%S')
                report_lines.append(f"- [{time_str}] {note_info['note']}")
            report_lines.append("")
        
        # Next steps
        report_lines.extend([
            f"## Next Steps",
        ])
        
        if not self.pending_files:
            report_lines.extend([
                f"1. ✅ All files generated",
                f"2. Run integration tests",
                f"3. Final review and deployment prep",
            ])
        else:
            next_file = self.pending_files[0]
            report_lines.extend([
                f"1. Generate `{next_file}`",
                f"2. Update context report",
                f"3. Continue to next file ({len(self.pending_files)-1} remaining)",
            ])
        
        self.report_path.write_text("\n".join(report_lines))

class TemplateLibrary:
    """Pre-built templates for common tasks"""
    
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_default_templates()
    
    def _initialize_default_templates(self):
        """Create default templates if they don't exist"""
        
        web_api_template = {
            "name": "web_api",
            "description": "RESTful API with Flask",
            "prompt_template": "Create a Flask REST API for {resource} with CRUD operations, SQLAlchemy ORM, error handling, and API documentation.",
            "files": ["app.py", "models.py", "routes.py", "config.py", "requirements.txt"],
            "complexity": "medium"
        }
        
        cli_tool_template = {
            "name": "cli_tool",
            "description": "Command-line tool with argparse",
            "prompt_template": "Create a CLI tool for {purpose} using argparse with subcommands, help text, and proper error handling.",
            "files": ["cli.py", "utils.py", "config.py"],
            "complexity": "simple"
        }
        
        data_pipeline_template = {
            "name": "data_pipeline",
            "description": "ETL data pipeline",
            "prompt_template": "Create a data pipeline for {source} to {destination} with pandas, data validation, error logging, and scheduling.",
            "files": ["pipeline.py", "extractors.py", "transformers.py", "loaders.py", "config.py"],
            "complexity": "complex"
        }
        
        scraper_template = {
            "name": "scraper",
            "description": "Web scraper with Beautiful Soup",
            "prompt_template": "Create a web scraper for {target_site} using requests and BeautifulSoup with rate limiting, error handling, and data export.",
            "files": ["scraper.py", "parser.py", "storage.py"],
            "complexity": "medium"
        }
        
        templates = [web_api_template, cli_tool_template, data_pipeline_template, scraper_template]
        
        for template in templates:
            template_file = self.templates_dir / f"{template['name']}.yaml"
            if not template_file.exists():
                with open(template_file, 'w') as f:
                    yaml.dump(template, f)
                logger.info(f"Created template: {template['name']}")
    
    def list_templates(self) -> List[Dict]:
        """List all available templates"""
        templates = []
        for template_file in self.templates_dir.glob("*.yaml"):
            try:
                with open(template_file) as f:
                    templates.append(yaml.safe_load(f))
            except Exception as e:
                logger.warning(f"Failed to load template {template_file}: {e}")
        return templates
    
    def get_template(self, name: str) -> Optional[Dict]:
        """Get a specific template by name"""
        template_file = self.templates_dir / f"{name}.yaml"
        if template_file.exists():
            with open(template_file) as f:
                return yaml.safe_load(f)
        return None
    
    def apply_template(self, name: str, **kwargs) -> str:
        """Apply a template with given parameters"""
        template = self.get_template(name)
        if not template:
            return None
        
        try:
            prompt = template['prompt_template'].format(**kwargs)
            return prompt
        except KeyError as e:
            logger.error(f"Missing template parameter: {e}")
            return None

class ProjectManager:
    """Manages project folder structure and organization"""
    
    def __init__(self, projects_dir: Path):
        self.projects_dir = projects_dir
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.current_project = None
    
    def create_project(self, name: str, user_request: str) -> Path:
        """Create a new project folder with timestamp"""
        clean_name = sanitize_folder_name(name) if name else "unnamed_project"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{clean_name}_{timestamp}"
        project_path = self.projects_dir / folder_name
        
        counter = 1
        while project_path.exists():
            folder_name = f"{clean_name}_{timestamp}_{counter}"
            project_path = self.projects_dir / folder_name
            counter += 1
        
        project_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created project folder: {project_path}")
        
        readme_content = f"""# {clean_name.replace('_', ' ').title()}

**Created:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## User Request
{user_request}

## Files
(Files will be listed here after generation)

## Generated by
Collaborative Coding Agent v4.2.1
"""
        (project_path / "README.md").write_text(readme_content)
        
        gitignore_content = """__pycache__/
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
CONTEXT_REPORT.md
"""
        (project_path / ".gitignore").write_text(gitignore_content)
        
        self.current_project = project_path
        return project_path
    
    def get_project_path(self, *parts) -> Path:
        """Get path within current project"""
        if not self.current_project:
            raise RuntimeError("No active project")
        return self.current_project / Path(*parts)
    
    def update_readme(self, files: List[str], test_results: Optional[str] = None):
        """Update README with generated files and test results"""
        if not self.current_project:
            return
        
        readme_path = self.current_project / "README.md"
        current_content = readme_path.read_text()
        
        files_section = "\n## Files\n" + "\n".join(f"- {f}" for f in files)
        
        if test_results:
            test_section = f"\n## Test Results\n```\n{test_results}\n```"
        else:
            test_section = ""
        
        if "(Files will be listed here" in current_content:
            current_content = current_content.replace(
                "## Files\n(Files will be listed here after generation)",
                files_section
            )
        else:
            current_content += files_section
        
        current_content += test_section
        readme_path.write_text(current_content)

class TestRunner:
    """Automatically run pytest on generated code"""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
    
    def has_tests(self) -> bool:
        """Check if project has test files"""
        test_files = list(self.project_path.glob("test_*.py"))
        test_files += list(self.project_path.glob("*_test.py"))
        test_files += list((self.project_path / "tests").glob("*.py")) if (self.project_path / "tests").exists() else []
        return len(test_files) > 0
    
    def run_tests(self) -> Tuple[bool, str]:
        """Run pytest and return (success, output)"""
        if not which("pytest"):
            return False, "pytest not installed. Run: pip install pytest"
        
        if not self.has_tests():
            return True, "No tests found (skipped)"
        
        try:
            result = subprocess.run(
                ["pytest", "-v", "--tb=short"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            output = result.stdout + result.stderr
            success = result.returncode == 0
            
            return success, output
        except subprocess.TimeoutExpired:
            return False, "Tests timed out after 60 seconds"
        except Exception as e:
            return False, f"Test execution failed: {e}"

class Prerequisites:
    """Validates prerequisites before execution"""
    
    @staticmethod
    def check_git_repo(path: Path) -> tuple[bool, str]:
        """Check if directory is a git repo"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return True, "Git repository found"
            else:
                return False, "Not a git repository"
        except Exception as e:
            return False, f"Git not available: {e}"
    
    @staticmethod
    def check_target_files(project_path: Path, targets: List[str]) -> tuple[bool, str]:
        """Check if target files can be created"""
        for target in targets:
            target_path = project_path / target
            parent = target_path.parent
            if not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
            if not os.access(parent, os.W_OK):
                return False, f"No write permission: {parent}"
        return True, "All target files accessible"
    
    @staticmethod
    def validate_all(project_path: Path, targets: List[str]) -> tuple[bool, List[str]]:
        """Run all prerequisite checks"""
        issues = []
        
        git_ok, git_msg = Prerequisites.check_git_repo(project_path)
        if not git_ok:
            issues.append(f"⚠️  Git: {git_msg}")
        else:
            issues.append(f"✓ Git: {git_msg}")
        
        files_ok, files_msg = Prerequisites.check_target_files(project_path, targets)
        if not files_ok:
            issues.append(f"❌ Files: {files_msg}")
        else:
            issues.append(f"✓ Files: {files_msg}")
        
        all_ok = files_ok
        return all_ok, issues

class CollaborativeAgentPro:
    def __init__(self):
        logger.info("Initializing Collaborative Agent v4.2.1 (Professional Edition)")
        http = build_http()
        self.http = http
        self.cfg = self._load_config()
        self.manager = OllamaClient(self.cfg.manager_host, http, ModelRole.MANAGER)
        self.coder = OllamaClient(self.cfg.coder_host, http, ModelRole.CODER)
        self._verify()
        
        self.project_manager = ProjectManager(self.cfg.projects_dir)
        self.template_library = TemplateLibrary(self.cfg.templates_dir)
        self.history = ConversationHistory()
        
        self.last_manager_text = None
        self.last_parsed = None
        self.targets = []
        self.current_model = None
        self.refinement_round = 0
        self.manual_target_set = False
        
        print(f"\n📋 Logs: {LOG_FILE}")
        print(f"📁 Projects: {self.cfg.projects_dir}")
        print(f"📄 Templates: {len(self.template_library.list_templates())} available")
    
    def _load_config(self):
        base_dir = Path.home() / ".collaborative_agent"
        base_dir.mkdir(parents=True, exist_ok=True)
        
        glm = os.getenv("GLM_MODEL", "glm-4.7-flash:latest").strip()
        qwen = os.getenv("QWEN_MODEL", "qwen2.5-coder:32b-instruct-q8_0").strip()
        default = os.getenv("DEFAULT_CODER_MODEL", glm).strip()
        
        cfg = Config(
            manager_host=normalize_host(os.getenv("MANAGER_OLLAMA_HOST", ""), "http://localhost:11434"),
            coder_host=normalize_host(os.getenv("CODER_OLLAMA_HOST", ""), "http://localhost:11434"),
            manager_model=os.getenv("MANAGER_MODEL", "").strip(),
            default_coder_model=default,
            glm_model=glm,
            qwen_model=qwen,
            projects_dir=Path(os.getenv("PROJECTS_DIR", "./projects")).resolve(),
            templates_dir=base_dir / "templates"
        )
        
        cfg.projects_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Config loaded: default_coder={default}")
        return cfg
    
    def _verify(self):
        print("\n🔍 Verifying setup...")
        logger.info("Starting setup verification")
        
        try:
            mgr_models = self.manager.list_models()
        except Exception as e:
            die(f"❌ Manager host unreachable: {self.cfg.manager_host}\n{e}")
        
        try:
            cod_models = self.coder.list_models()
        except Exception as e:
            die(f"❌ Coder host unreachable: {self.cfg.coder_host}\n{e}")
        
        if not self.cfg.manager_model:
            for pref in ["llama3.2:latest", "llama3:8b", "llama3:latest"]:
                if pref in mgr_models:
                    self.cfg.manager_model = pref
                    break
        
        if self.cfg.manager_model not in mgr_models:
            die(f"❌ Manager model not found: {self.cfg.manager_model}\nAvailable: {mgr_models[:5]}")
        
        has_glm = any(self.cfg.glm_model in m for m in cod_models)
        has_qwen = any(self.cfg.qwen_model in m for m in cod_models)
        
        print(f"✓ Manager: {self.cfg.manager_host} ({self.cfg.manager_model})")
        print(f"✓ Default Coder: {self.cfg.default_coder_model}")
        print(f"  • GLM: {self.cfg.glm_model} {'✓' if has_glm else '✗ (not installed)'}")
        print(f"  • Qwen: {self.cfg.qwen_model} {'✓' if has_qwen else '✗ (not installed)'}")
        
        if not has_glm and not has_qwen:
            die("❌ No coder models available. Install GLM or Qwen.")
        
        if self.cfg.default_coder_model not in cod_models:
            print(f"⚠️  Default model not found: {self.cfg.default_coder_model}")
            if has_glm:
                self.cfg.default_coder_model = self.cfg.glm_model
            elif has_qwen:
                self.cfg.default_coder_model = self.cfg.qwen_model
            print(f"   Using fallback: {self.cfg.default_coder_model}")
        
        print("\n🔥 Warming up manager model...")
        self.manager.warmup(self.cfg.manager_model)
        logger.info("Setup verification complete")
    
    def manager_prompt(self, user_text: str) -> str:
        ctx = self.history.get_context()
        
        base_prompt = f"""You are the MANAGER. Create executable plans.

OUTPUT FORMAT:
PROJECT_NAME: short_descriptive_name

BEGIN_SPEC
## Requirements
- [specific requirements]
## Implementation
- [approach, files]
## Acceptance
- [how to verify]
END_SPEC

BEGIN_CODER_TASKS
1. [specific task with filenames]
2. [continue...]
END_CODER_TASKS

TARGET_FILES:
- file.py

PLAN_READY: YES/NO

RULES:
- PROJECT_NAME should be short, descriptive, snake_case
- Only what user requested, no extras
- Specific filenames and functions
- PLAN_READY:YES only when complete

{ctx}

USER: {user_text}"""
        
        return base_prompt
    
    def ask_manager(self, user_text):
        print("\n🧠 Manager thinking...")
        logger.info("Asking manager")
        t0 = now_s()
        out = self.manager.generate(self.cfg.manager_model, self.manager_prompt(user_text), 300)
        elapsed = now_s() - t0
        print(f"✓ Responded in {elapsed:.1f}s")
        logger.info(f"Manager responded in {elapsed:.1f}s")
        
        self.history.add_user(user_text)
        self.history.add_assistant(out)
        self.last_manager_text = out
        self.last_parsed = parse_manager_payload(out)
        
        if not self.last_parsed.is_valid:
            print("\n⚠️  VALIDATION WARNINGS:")
            for e in self.last_parsed.validation_errors:
                print(f"  - {e}")
                logger.warning(f"Validation: {e}")
        
        # FIX v4.2.1: Don't override manual targets
        if self.last_parsed.plan_ready and self.last_parsed.targets and not self.manual_target_set:
            self.targets = self.last_parsed.targets
            print(f"\n🎯 Targets: {', '.join(self.targets)}")
            
            complexity = TaskComplexity.analyze(
                self.last_parsed.spec,
                self.last_parsed.tasks,
                self.targets
            )
            
            print(f"📊 Task Complexity: {complexity.complexity_score:.1f}/100")
            print(f"   Files: {complexity.file_count}, Est. lines: ~{complexity.estimated_lines}, External deps: {'Yes' if complexity.has_external_deps else 'No'}")
            
            logger.info(f"Targets set: {self.targets}")
        
        return out
    
    def _extract_code_blocks(self, text: str) -> Dict[str, str]:
        """FIX v4.2.1: Better code extraction for incomplete blocks"""
        # Pattern to match complete code blocks
        pattern = r"```(?:python)?\n(.*?)```"
        blocks = re.findall(pattern, text, re.DOTALL)
        
        # FIX: Also try to extract incomplete blocks (missing closing ```)
        if not blocks or (len(blocks) == 1 and len(blocks[0].strip()) < 200):
            # Look for opening ``` without closing
            incomplete_pattern = r"```(?:python)?\n(.*?)$"
            incomplete_blocks = re.findall(incomplete_pattern, text, re.DOTALL | re.MULTILINE)
            if incomplete_blocks:
                # Use the incomplete block if it's substantial
                for block in incomplete_blocks:
                    if len(block.strip()) > 200:
                        blocks.append(block)
                        logger.warning(f"Extracted incomplete code block ({len(block)} chars)")
        
        if not blocks:
            logger.warning("No code blocks found in response")
            return {}
        
        # For single target, use the largest/most complete block
        if len(self.targets) == 1:
            # Filter out tiny blocks
            substantial_blocks = [b for b in blocks if len(b.strip()) > 100]
            
            if substantial_blocks:
                largest_block = max(substantial_blocks, key=len)
                logger.info(f"Using largest code block: {len(largest_block)} chars")
                return {self.targets[0]: largest_block.strip()}
            elif blocks:
                logger.warning("No substantial blocks found, using first block")
                return {self.targets[0]: blocks[0].strip()}
            else:
                return {}
        
        # For multiple files, try to match by filename mentions
        result = {}
        for target in self.targets:
            target_name = Path(target).name
            for i, block in enumerate(blocks):
                block_start = text.find(f"```python\n{block}")
                if block_start == -1:
                    block_start = text.find(f"```\n{block}")
                
                if block_start != -1:
                    context_before = text[max(0, block_start-500):block_start]
                    
                    if target_name in context_before:
                        result[target] = block.strip()
                        logger.info(f"Matched {target_name} to block {i}")
                        break
        
        # Fallback: distribute blocks to targets
        if not result:
            logger.warning("No filename matches, distributing blocks to targets")
            for i, target in enumerate(self.targets):
                if i < len(blocks):
                    result[target] = blocks[i].strip()
        
        return result
    
    def choose_model(self, user_preference: Optional[str] = None) -> str:
        """Choose model based on user preference or default"""
        if user_preference:
            pref_lower = user_preference.lower()
            if "glm" in pref_lower:
                logger.info("User selected GLM")
                return self.cfg.glm_model
            elif "qwen" in pref_lower:
                logger.info("User selected Qwen")
                return self.cfg.qwen_model
        
        logger.info(f"Using default model: {self.cfg.default_coder_model}")
        return self.cfg.default_coder_model
    
    def _analyze_file(self, filepath: Path) -> Dict:
        """Extract metadata from generated file"""
        try:
            code = filepath.read_text()
            
            # Extract function names
            functions = re.findall(r'^def (\w+)\(', code, re.MULTILINE)
            
            # Extract class names
            classes = re.findall(r'^class (\w+)', code, re.MULTILINE)
            
            # Extract imports
            imports = re.findall(r'^import (\w+)', code, re.MULTILINE)
            imports += re.findall(r'^from (\w+)', code, re.MULTILINE)
            
            return {
                'size': len(code),
                'functions': functions,
                'classes': classes,
                'dependencies': list(set(imports)),
                'exports': functions + classes
            }
        except Exception as e:
            logger.error(f"Error analyzing file {filepath}: {e}")
            return {
                'size': 0,
                'functions': [],
                'classes': [],
                'dependencies': [],
                'exports': []
            }
    
    def _extract_tasks_for_file(self, tasks: str, filename: str) -> str:
        """Extract relevant tasks for a specific file"""
        relevant = []
        for line in tasks.split('\n'):
            if filename in line:
                relevant.append(line)
        
        if relevant:
            return '\n'.join(relevant)
        else:
            return tasks
    
    def run_coder_sequential(self, spec, tasks, user_request="", model_preference=None):
        """FIX v4.2.1: Sequential file-by-file generation with proper path handling"""
        
        if not self.targets:
            return {"success": False, "error": "No target files"}
        
        # FIX v4.2.1: CRITICAL - Check manual_target_set FIRST before any manager logic
        first_target = Path(self.targets[0])
        
        # Convert to absolute path
        if not first_target.is_absolute():
            first_target = Path.cwd() / first_target
        
        # FIX v4.2.1: If user manually set target, ALWAYS respect it
        if self.manual_target_set:
            project_path = first_target.parent
            
            # Create folder if it doesn't exist
            if not project_path.exists():
                project_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created target directory: {project_path}")
            
            print(f"\n📁 Using manually specified path: {project_path.name}")
            logger.info(f"Manual target path respected: {project_path}")
            self.project_manager.current_project = project_path
            
            # Update targets to be relative to project
            self.targets = [Path(t).name if Path(t).is_absolute() or '/' in t else t for t in self.targets]
        else:
            # Normal flow - create new project
            project_name = self.last_parsed.project_name if self.last_parsed else None
            project_path = self.project_manager.create_project(project_name, user_request)
            print(f"\n📁 Project: {project_path.name}")
        
        # Prerequisites check
        prereqs_ok, prereq_msgs = Prerequisites.validate_all(project_path, self.targets)
        print("\n🔍 Prerequisites Check:")
        for msg in prereq_msgs:
            print(f"  {msg}")
        
        if not prereqs_ok:
            logger.error("Prerequisites check failed")
            return {"success": False, "error": "Prerequisites check failed", "prereqs": prereq_msgs}
        
        # Initialize context report (skip if manual target to existing project)
        context_mgr = ContextReportManager(project_path)
        
        # Only initialize if new project or no existing context report
        if not self.manual_target_set or not context_mgr.report_path.exists():
            context_mgr.initialize(
                self.last_parsed.project_name if self.last_parsed else "project",
                spec,
                self.targets
            )
            print(f"\n📋 Context Report: {project_path.name}/CONTEXT_REPORT.md")
        else:
            print(f"\n📋 Using existing context report: {context_mgr.report_path.name}")
        
        print(f"🔄 Sequential Generation: {len(self.targets)} files")
        
        # Choose model
        chosen_model = self.choose_model(model_preference)
        self.current_model = chosen_model
        model_name = "GLM" if "glm" in chosen_model.lower() else "Qwen"
        print(f"🤖 Using {model_name} ({chosen_model})")
        
        # Generate files sequentially
        all_results = []
        
        for idx, target_file in enumerate(self.targets, 1):
            print(f"\n{'='*70}")
            print(f"📝 File {idx}/{len(self.targets)}: {target_file}")
            print(f"{'='*70}")
            
            # Get context from previous files
            file_context = context_mgr.get_context_for_file(target_file)
            
            # Build file-specific prompt
            file_tasks = self._extract_tasks_for_file(tasks, target_file)
            
            prompt = f"""You are generating file {idx} of {len(self.targets)} for a project.

OVERALL SPECIFICATION:
{spec}

TASKS FOR THIS FILE ({target_file}):
{file_tasks}

{file_context}

TARGET FILE: {target_file}

INSTRUCTIONS:
- Generate ONLY {target_file} (complete implementation)
- Import from already-completed modules as needed
- Maintain consistency with existing code patterns
- Include comprehensive error handling
- Add docstrings and type hints
- Put ALL code for {target_file} in a SINGLE ```python code block
- Make it production-ready and fully functional

Generate the complete {target_file} now:"""
            
            # Generate this file
            print(f"🔧 Generating {target_file}...")
            t0 = now_s()
            
            try:
                print("\n--- CODER OUTPUT ---")
                full_response = []
                for chunk in self.coder.generate_stream(chosen_model, prompt, timeout=300):
                    print(chunk, end='', flush=True)
                    full_response.append(chunk)
                
                response_text = ''.join(full_response)
                print("\n--- END OUTPUT ---\n")
                
                elapsed = now_s() - t0
                
                # Extract code (temporarily set targets to single file)
                original_targets = self.targets.copy()
                self.targets = [target_file]
                code_blocks = self._extract_code_blocks(response_text)
                self.targets = original_targets
                
                if target_file not in code_blocks:
                    print(f"❌ Failed to extract code for {target_file}")
                    logger.error(f"No code block found for {target_file}")
                    all_results.append({"file": target_file, "success": False, "error": "No code block found"})
                    continue
                
                # Write file
                filepath = project_path / target_file
                code = code_blocks[target_file]
                filepath.write_text(code)
                
                print(f"✓ Wrote {target_file} ({len(code)} chars, {elapsed:.1f}s)")
                logger.info(f"Generated {target_file}: {len(code)} chars in {elapsed:.1f}s")
                
                # Analyze file
                file_info = self._analyze_file(filepath)
                
                # Update context report
                context_mgr.mark_file_complete(target_file, file_info)
                
                # Add integration note
                if file_info['dependencies']:
                    note = f"{target_file} imports: {', '.join(file_info['dependencies'][:3])}"
                    context_mgr.add_integration_note(note)
                
                all_results.append({
                    "file": target_file,
                    "success": True,
                    "size": len(code),
                    "time_s": elapsed,
                    "functions": len(file_info['functions']),
                    "classes": len(file_info['classes'])
                })
                
                # Show progress
                completed = idx
                remaining = len(self.targets) - completed
                print(f"\n✅ Progress: {completed}/{len(self.targets)} complete")
                if remaining > 0:
                    print(f"   Next: {self.targets[idx] if idx < len(self.targets) else 'None'}")
                print(f"   Context: {context_mgr.report_path.name}")
                
            except Exception as e:
                print(f"\n❌ Error generating {target_file}: {e}")
                logger.exception(f"Error generating {target_file}")
                all_results.append({"file": target_file, "success": False, "error": str(e)})
        
        # Final summary
        print(f"\n{'='*70}")
        print(f"📊 GENERATION COMPLETE")
        print(f"{'='*70}")
        
        success_count = sum(1 for r in all_results if r.get("success"))
        total_time = sum(r.get("time_s", 0) for r in all_results if r.get("success"))
        total_size = sum(r.get("size", 0) for r in all_results if r.get("success"))
        
        print(f"✅ Successful: {success_count}/{len(self.targets)} files")
        print(f"⏱️  Total Time: {total_time:.1f}s")
        print(f"📦 Total Code: {total_size:,} chars")
        print(f"📋 Context Report: {context_mgr.report_path}")
        
        # Update README
        successful_files = [r['file'] for r in all_results if r.get('success')]
        self.project_manager.update_readme(successful_files)
        
        # Run integration tests
        test_runner = TestRunner(project_path)
        if test_runner.has_tests():
            print(f"\n🧪 Running integration tests...")
            test_success, test_output = test_runner.run_tests()
            if test_success:
                print("✅ All tests passed!")
                context_mgr.add_integration_note("All integration tests passed")
            else:
                print("⚠️  Some tests failed")
                print(test_output[:500])
                context_mgr.add_integration_note("Integration tests: Some failures")
            
            self.project_manager.update_readme(successful_files, test_output)
        else:
            print("📝 No tests found")
        
        return {
            "success": success_count == len(self.targets),
            "files_generated": success_count,
            "total_files": len(self.targets),
            "results": all_results,
            "project_path": str(project_path),
            "context_report": str(context_mgr.report_path),
            "total_time_s": total_time,
            "total_size": total_size
        }
    
    def refine_code(self, feedback: str) -> Dict:
        """Iterative refinement based on manager feedback"""
        if not self.project_manager.current_project:
            return {"success": False, "error": "No active project to refine"}
        
        self.refinement_round += 1
        print(f"\n🔄 Refinement Round {self.refinement_round}")
        
        current_code = {}
        for target in self.targets:
            filepath = self.project_manager.get_project_path(target)
            if filepath.exists():
                current_code[target] = filepath.read_text()
        
        files_content = "\n\n".join([f"# {fname}\n```python\n{code}\n```" for fname, code in current_code.items()])
        
        prompt = f"""You are refining existing code based on feedback.

CURRENT CODE:
{files_content}

FEEDBACK:
{feedback}

INSTRUCTIONS:
- Address all points in the feedback
- Maintain existing functionality
- Improve code quality, error handling, documentation
- Put refined code in ```python blocks with filenames
- Only include files that need changes

Generate the refined code now."""

        print(f"🔧 Refining with {self.current_model}...")
        t0 = now_s()
        
        try:
            print("\n--- REFINEMENT OUTPUT ---")
            full_response = []
            for chunk in self.coder.generate_stream(self.current_model, prompt, timeout=300):
                print(chunk, end='', flush=True)
                full_response.append(chunk)
            
            response_text = ''.join(full_response)
            print("\n--- END OUTPUT ---\n")
            
            elapsed = now_s() - t0
            
            code_blocks = self._extract_code_blocks(response_text)
            
            if not code_blocks:
                return {"success": False, "error": "No refined code found"}
            
            updated_files = []
            for filename, code in code_blocks.items():
                filepath = self.project_manager.get_project_path(filename)
                filepath.write_text(code)
                updated_files.append(filename)
                print(f"  ✓ Updated {filename}")
            
            test_runner = TestRunner(self.project_manager.current_project)
            test_success, test_output = test_runner.run_tests()
            
            if test_runner.has_tests():
                print(f"\n🧪 Re-running tests...")
                if test_success:
                    print("✅ All tests passed after refinement!")
                else:
                    print("⚠️  Some tests still failing")
            
            return {
                "success": True,
                "time_s": elapsed,
                "files_updated": updated_files,
                "tests_passed": test_success if test_runner.has_tests() else None,
                "round": self.refinement_round
            }
            
        except Exception as e:
            logger.error(f"Refinement error: {e}")
            return {"success": False, "error": str(e)}
    
    def review(self, spec, output):
        print("\n🧠 Manager reviewing...")
        logger.info("Manager reviewing output")
        prompt = f"""Review coder output vs spec. If complete, give checklist. If issues, list them.

SPEC:\n{spec}\n\nOUTPUT:\n{output[:6000]}"""
        return self.manager.generate(self.cfg.manager_model, prompt, 300)
    
    def interactive(self):
        print("\n" + "="*78)
        print("🚀 COLLABORATIVE AGENT v4.2.1 PROFESSIONAL EDITION")
        print("="*78)
        print("FIXED: Manual :target paths now properly respected!")
        print("")
        print("Commands:")
        print("  execute             - Run sequential generation (default model)")
        print("  execute glm         - Run with GLM")
        print("  execute qwen        - Run with Qwen")
        print("  refine              - Improve code based on feedback")
        print("  manager             - Show last manager response")
        print("  templates           - List available templates")
        print("  template <name>     - Use a template")
        print("  :target file.py     - Set target files manually")
        print("  :history            - Show conversation history")
        print("  :clear              - Clear conversation")
        print("  quit                - Exit")
        print("="*78)
        logger.info("Starting interactive session")
        
        last_user_request = ""
        
        while True:
            try:
                inp = input("\n💬 You: ").strip()
                if not inp:
                    continue
                
                if inp in ["quit", "exit", "q"]:
                    logger.info("User quit")
                    return 0
                
                if inp == "templates":
                    templates = self.template_library.list_templates()
                    print("\n📄 Available Templates:")
                    for t in templates:
                        print(f"  • {t['name']}: {t['description']} ({t['complexity']})")
                    continue
                
                if inp.startswith("template "):
                    template_name = inp.split(maxsplit=1)[1]
                    template = self.template_library.get_template(template_name)
                    if template:
                        print(f"\n📄 Template: {template['name']}")
                        print(f"Description: {template['description']}")
                        print(f"Complexity: {template['complexity']}")
                        print(f"Files: {', '.join(template['files'])}")
                        
                        params = {}
                        for match in re.finditer(r'\{(\w+)\}', template['prompt_template']):
                            param_name = match.group(1)
                            value = input(f"  {param_name}: ")
                            params[param_name] = value
                        
                        prompt = self.template_library.apply_template(template_name, **params)
                        if prompt:
                            print(f"\n✓ Using template. Asking manager...")
                            last_user_request = prompt
                            out = self.ask_manager(prompt)
                            print(f"\n🤖 Manager:\n{out}")
                    else:
                        print(f"❌ Template not found: {template_name}")
                    continue
                
                if inp.startswith(":target "):
                    self.targets = [f.strip() for f in inp.split()[1:]]
                    self.manual_target_set = True  # FIX v4.2.1: Set flag
                    print(f"✓ Targets: {self.targets}")
                    logger.info(f"Manual targets set: {self.targets}")
                    continue
                
                if inp == ":history":
                    for t in self.history.turns:
                        print(f"\n{t.role.upper()}: {t.content[:200]}")
                    continue
                
                if inp == ":clear":
                    self.history.clear()
                    self.refinement_round = 0
                    self.manual_target_set = False  # FIX v4.2.1: Reset flag
                    print("✓ Cleared")
                    continue
                
                if inp == "manager":
                    print(f"\n🤖 {self.last_manager_text or '(none)'}")
                    continue
                
                if inp.startswith("execute"):
                    parts = inp.split()
                    model_pref = parts[1] if len(parts) > 1 else None
                    
                    # FIX v4.2.1: Allow execution even without manager if manual target set
                    if not self.manual_target_set:
                        if not self.last_parsed:
                            print("❌ No plan yet")
                            logger.warning("Execute called without plan")
                            continue
                        if not self.last_parsed.plan_ready:
                            print("❌ PLAN_READY is NO")
                            logger.warning("Execute called but plan not ready")
                            continue
                        if not self.last_parsed.is_valid:
                            print("❌ Validation errors - ask manager to fix")
                            logger.warning("Execute called with validation errors")
                            continue
                    
                    self.refinement_round = 0
                    
                    # Use sequential generation
                    result = self.run_coder_sequential(
                        self.last_parsed.spec if self.last_parsed else "",
                        self.last_parsed.tasks if self.last_parsed else "",
                        user_request=last_user_request,
                        model_preference=model_pref
                    )
                    
                    success_emoji = '✅' if result.get('success') else '⚠️'
                    print(f"\n{success_emoji} {'SUCCESS' if result.get('success') else 'PARTIAL SUCCESS'}")
                    
                    if result.get("files_generated"):
                        print(f"📝 Generated: {result['files_generated']}/{result['total_files']} files")
                    if result.get("total_time_s"):
                        print(f"⏱️  Total Time: {result['total_time_s']:.1f}s")
                    if result.get("total_size"):
                        print(f"📦 Code Size: {result['total_size']:,} chars")
                    if result.get("project_path"):
                        print(f"📁 Project: {result['project_path']}")
                    if result.get("context_report"):
                        print(f"📋 Context: {result['context_report']}")
                    if result.get("error"):
                        print(f"❌ Error: {result['error']}")
                    
                    # FIX v4.2.1: Reset manual flag after execution
                    self.manual_target_set = False
                    continue
                
                if inp == "refine":
                    if not self.project_manager.current_project:
                        print("❌ No active project. Run 'execute' first.")
                        continue
                    
                    feedback = input("\n💬 Feedback for refinement: ").strip()
                    if not feedback:
                        print("❌ No feedback provided")
                        continue
                    
                    result = self.refine_code(feedback)
                    
                    if result.get("success"):
                        print(f"\n✅ Refinement complete (Round {result['round']})")
                        print(f"⏱️  {result['time_s']:.1f}s")
                        print(f"📝 Updated: {', '.join(result['files_updated'])}")
                        if result.get("tests_passed") is not None:
                            test_emoji = '✅' if result['tests_passed'] else '⚠️'
                            print(f"{test_emoji} Tests: {'Passed' if result['tests_passed'] else 'Failed'}")
                    else:
                        print(f"❌ Refinement failed: {result.get('error')}")
                    continue
                
                # Regular user request
                last_user_request = inp
                self.manual_target_set = False  # FIX v4.2.1: Reset for new request
                out = self.ask_manager(inp)
                print(f"\n🤖 Manager:\n{out}")
                
            except KeyboardInterrupt:
                print("\n👋 Bye")
                logger.info("Interrupted by user")
                return 0
            except Exception as e:
                print(f"\n❌ Error: {e}")
                logger.exception("Unexpected error")
                continue

if __name__ == "__main__":
    raise SystemExit(CollaborativeAgentPro().interactive())
