"""
Ollama client for the subconscious daemon.
Talks to the 9B model on the PVE node for analysis tasks.
"""

import json
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class OllamaClient:
    """Simple async Ollama API client."""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "qwen2.5-coder:7b",
                 temperature: float = 0.1,
                 max_tokens: int = 4096,
                 timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    async def generate(self, prompt: str, system: str = "",
                       temperature: Optional[float] = None,
                       json_mode: bool = False) -> str:
        """
        Generate a completion from the model.
        Returns the response text.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_predict": self.max_tokens,
            }
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "")
        except httpx.TimeoutException:
            logger.error(f"Ollama request timed out after {self.timeout}s")
            return ""
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            return ""

    async def generate_json(self, prompt: str, system: str = "",
                            temperature: Optional[float] = None) -> Optional[dict]:
        """
        Generate a JSON response. Returns parsed dict or None on failure.
        """
        raw = await self.generate(prompt, system=system,
                                  temperature=temperature, json_mode=True)
        if not raw:
            return None

        # Try to parse — handle markdown-wrapped JSON
        text = raw.strip()
        if text.startswith("```"):
            # Strip markdown fences
            lines = text.split("\n")
            text = "\n".join(
                l for l in lines
                if not l.strip().startswith("```")
            ).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from model: {e}\nRaw: {text[:200]}")
            return None

    async def is_available(self) -> bool:
        """Check if Ollama is running and the model is loaded."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    # Check if our model is available (fuzzy match)
                    for name in model_names:
                        if self.model.split(":")[0] in name:
                            return True
                    logger.warning(f"Model {self.model} not found. Available: {model_names}")
                    return len(models) > 0  # At least Ollama is running
                return False
        except Exception:
            return False
