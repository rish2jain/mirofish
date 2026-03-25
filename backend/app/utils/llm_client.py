"""
LLM Client Wrapper
Supports OpenAI API, Anthropic API, Claude CLI, Codex CLI, and Gemini CLI
"""

import json
import re
import subprocess
from typing import Any, Dict, Iterable, List, Optional

from ..config import Config
from .logger import get_logger

logger = get_logger('mirofish.llm_client')


class LLMClient:
    """LLM Client - supports OpenAI, Anthropic, Claude CLI, Codex CLI, and Gemini CLI"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        self.provider = (provider or Config.LLM_PROVIDER or "").lower()

        # CLI providers don't need an API key
        if self.provider in ("claude-cli", "codex-cli", "gemini-cli"):
            self.client = None
        elif not self.api_key:
            raise ValueError("LLM_API_KEY not configured")

        # Auto-detect provider if not specified
        if not self.provider:
            self.provider = self._detect_provider()

        # Initialize the appropriate client
        if self.provider == "anthropic":
            try:
                from anthropic import Anthropic
            except ImportError:
                raise ImportError(
                    "anthropic package required for Claude support. "
                    "Install with: pip install anthropic"
                )
            self.client = Anthropic(api_key=self.api_key)
        elif self.provider in ("claude-cli", "codex-cli", "gemini-cli"):
            self.client = None  # CLI-based, no SDK client needed
        else:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

    def _detect_provider(self) -> str:
        """Auto-detect provider from base_url or model name"""
        model_lower = (self.model or "").lower()
        base_lower = (self.base_url or "").lower()

        if any(k in model_lower for k in ["claude", "anthropic"]):
            return "anthropic"
        if "anthropic" in base_lower:
            return "anthropic"
        if "gemini" in model_lower:
            return "gemini-cli"

        return "openai"

    def _split_system_message(self, messages: List[Dict[str, str]]):
        """
        Split system message from conversation messages.
        Returns (system_text, conversation_messages)
        """
        system_text = None
        conversation = []

        for msg in messages:
            if msg.get("role") == "system":
                if system_text is None:
                    system_text = msg["content"]
                else:
                    system_text += "\n\n" + msg["content"]
            else:
                conversation.append(msg)

        return system_text, conversation

    def _clean_content(self, content: str) -> str:
        """Remove <think> tags from reasoning models"""
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content

    @staticmethod
    def _build_cli_prompt(
        system_text: Optional[str],
        conversation: List[Dict[str, str]],
        response_format: Optional[Dict] = None,
    ) -> str:
        """Build a prompt for CLI providers using XML tags for JSON output.

        When response_format requests JSON, wraps instructions in XML tags and
        uses few-shot + prefill techniques so the model returns only valid JSON
        inside <json_output> tags.  For non-JSON requests, falls back to plain
        text prompting.
        """
        parts: List[str] = []
        wants_json = response_format and response_format.get("type") == "json_object"

        if system_text:
            parts.append(f"<system>\n{system_text}\n</system>")

        if wants_json:
            parts.append(
                "<instructions>\n"
                "You MUST respond with valid JSON only.\n"
                "Do not include any introductory or concluding remarks.\n"
                "Do not wrap the JSON in markdown code fences.\n"
                "Output ONLY the raw JSON object, nothing else.\n"
                "</instructions>"
            )

        for msg in conversation:
            role = msg.get("role", "user").upper()
            parts.append(f"<{role.lower()}>\n{msg['content']}\n</{role.lower()}>")

        if wants_json:
            # Remind at the end — no prefill (CLI doesn't support it)
            parts.append("<reminder>Respond with the raw JSON object only. No tags, no markdown, no explanation.</reminder>")

        return "\n\n".join(parts)

    @staticmethod
    def _extract_json_from_xml(content: str) -> str:
        """Extract JSON from the LLM response, handling various wrapping formats.

        Models may wrap JSON in <json_output> tags, markdown fences, or return
        it raw.  This method normalizes all cases to a plain JSON string.
        """
        # Try <json_output> tags first
        match = re.search(r'<json_output>\s*([\s\S]*?)\s*</json_output>', content)
        if match:
            return match.group(1).strip()

        # Strip stray tags if model partially used them
        content = re.sub(r'</?json_output>', '', content)
        # Strip any other XML-like wrapper tags the model might emit
        content = re.sub(r'</?(?:response|output|result|answer|json)>', '', content)

        return content.strip()

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send a chat request.

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Maximum tokens
            response_format: Response format (e.g., JSON mode)

        Returns:
            Model response text
        """
        if self.provider == "claude-cli":
            return self._chat_claude_cli(messages, temperature, max_tokens, response_format)
        elif self.provider == "codex-cli":
            return self._chat_codex_cli(messages, temperature, max_tokens, response_format)
        elif self.provider == "gemini-cli":
            return self._chat_gemini_cli(messages, temperature, max_tokens, response_format)
        elif self.provider == "anthropic":
            return self._chat_anthropic(messages, temperature, max_tokens, response_format)
        else:
            return self._chat_openai(messages, temperature, max_tokens, response_format)

    def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict]
    ) -> str:
        """Chat via OpenAI-compatible API"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return self._clean_content(content)

    def _chat_anthropic(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict] = None
    ) -> str:
        """Chat via Anthropic API"""
        system_text, conversation = self._split_system_message(messages)

        # For JSON requests that go through chat() (not chat_structured),
        # use XML tag approach as a lightweight fallback
        if response_format and response_format.get("type") == "json_object":
            json_instruction = (
                "\n\nYou MUST respond with valid JSON only. "
                "Do not include any introductory or concluding remarks. "
                "Do not wrap the JSON in markdown code fences. "
                "Place your entire JSON response inside <json_output> tags."
            )
            if system_text:
                system_text += json_instruction
            else:
                system_text = json_instruction.strip()

        kwargs = {
            "model": self.model,
            "messages": conversation,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system_text:
            kwargs["system"] = system_text

        response = self.client.messages.create(**kwargs)
        content = response.content[0].text
        content = self._clean_content(content)

        if response_format and response_format.get("type") == "json_object":
            content = self._extract_json_from_xml(content)

        return content

    def _chat_claude_cli(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict] = None
    ) -> str:
        """Chat via Claude Code CLI (uses your Claude subscription)"""
        system_text, conversation = self._split_system_message(messages)
        prompt = self._build_cli_prompt(system_text, conversation, response_format)

        try:
            result = subprocess.run(
                ["claude", "-p", "--output-format", "text"],
                input=prompt,
                capture_output=True, text=True, timeout=120,
                cwd="/tmp",
            )

            if result.returncode != 0:
                logger.error(f"Claude CLI error: {result.stderr[:200]}")
                raise RuntimeError(f"Claude CLI failed: {result.stderr[:200]}")

            content = result.stdout.strip()
            content = self._clean_content(content)

            if response_format and response_format.get("type") == "json_object":
                content = self._extract_json_from_xml(content)

            return content

        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude CLI timed out after 120s")

    def _chat_codex_cli(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict] = None
    ) -> str:
        """Chat via Codex CLI (uses your OpenAI subscription)"""
        system_text, conversation = self._split_system_message(messages)
        prompt = self._build_cli_prompt(system_text, conversation, response_format)

        try:
            result = subprocess.run(
                ["codex", "exec", "--skip-git-repo-check"],
                input=prompt,
                capture_output=True, text=True, timeout=180,
                cwd="/tmp"
            )

            if result.returncode != 0:
                logger.error(f"Codex CLI error: {result.stderr[:200]}")
                raise RuntimeError(f"Codex CLI failed: {result.stderr[:200]}")

            # Codex exec outputs headers + conversation. Extract the last assistant response.
            raw = result.stdout.strip()
            parts = raw.split("\ncodex\n")
            if len(parts) > 1:
                content = parts[-1].strip()
                lines = content.split("\n")
                clean_lines = []
                for line in lines:
                    if line.strip() == "tokens used":
                        break
                    clean_lines.append(line)
                content = "\n".join(clean_lines).strip()
            else:
                content = raw

            content = self._clean_content(content)

            if response_format and response_format.get("type") == "json_object":
                content = self._extract_json_from_xml(content)

            return content

        except subprocess.TimeoutExpired:
            raise RuntimeError("Codex CLI timed out after 180s")

    def _chat_gemini_cli(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict] = None
    ) -> str:
        """Chat via Gemini CLI (uses your Google subscription)"""
        system_text, conversation = self._split_system_message(messages)
        prompt = self._build_cli_prompt(system_text, conversation, response_format)

        try:
            result = subprocess.run(
                ["gemini", "-p", ""],
                input=prompt,
                capture_output=True, text=True, timeout=180,
                cwd="/tmp"
            )

            if result.returncode != 0:
                logger.error(f"Gemini CLI error: {result.stderr[:200]}")
                raise RuntimeError(f"Gemini CLI failed: {result.stderr[:200]}")

            content = result.stdout.strip()
            content = self._clean_content(content)

            if response_format and response_format.get("type") == "json_object":
                content = self._extract_json_from_xml(content)

            return content

        except subprocess.TimeoutExpired:
            raise RuntimeError("Gemini CLI timed out after 180s")

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        expected_keys: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send a chat request and return JSON.

        Args:
            messages: Message list
            temperature: Temperature parameter
            max_tokens: Maximum tokens
            expected_keys: If the parsed value is a list of dicts, return the first dict
                that contains any of these keys; if None, only single-element lists are
                unwrapped and other lists become ``{"items": parsed}``.

        Returns:
            Parsed JSON object
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # Clean markdown code block markers
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            parsed = json.loads(cleaned_response)
        except json.JSONDecodeError:
            logger.debug("chat_json raw response (first 300 chars): %s", response[:300] if response else "<empty>")
            logger.debug("chat_json cleaned response (first 300 chars): %s", cleaned_response[:300] if cleaned_response else "<empty>")
            raise ValueError(f"Invalid JSON returned by LLM: {cleaned_response[:500]}")

        # LLMs sometimes wrap the object in a single-element array — unwrap it
        if isinstance(parsed, list):
            if len(parsed) == 1 and isinstance(parsed[0], dict):
                return parsed[0]
            if expected_keys is not None:
                for item in parsed:
                    if isinstance(item, dict) and any(
                        k in item for k in expected_keys
                    ):
                        return item
            return {"items": parsed}

        return parsed

    def chat_structured(
        self,
        messages: List[Dict[str, str]],
        output_schema,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ):
        """
        Send a chat request and return a Pydantic model instance.

        Uses Anthropic's messages.parse() for schema-constrained output when the
        provider is 'anthropic'. For all other providers, falls back to chat_json()
        and manual Pydantic validation.

        Args:
            messages: Message list
            output_schema: A Pydantic BaseModel class defining the expected output shape
            temperature: Temperature parameter
            max_tokens: Maximum tokens

        Returns:
            An instance of output_schema populated with the LLM's response
        """
        if self.provider == "anthropic" and self.client is not None:
            return self._chat_structured_anthropic(
                messages, output_schema, temperature, max_tokens
            )

        # Fallback for non-Anthropic providers: use chat_json + Pydantic validation
        # Derive expected_keys from the schema's top-level fields
        expected_keys = tuple(output_schema.model_fields.keys())
        raw = self.chat_json(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            expected_keys=expected_keys,
        )
        return output_schema.model_validate(raw)

    def _chat_structured_anthropic(
        self,
        messages: List[Dict[str, str]],
        output_schema,
        temperature: float,
        max_tokens: int,
    ):
        """Use Anthropic's native structured output via messages.parse()."""
        system_text, conversation = self._split_system_message(messages)

        kwargs = {
            "model": self.model,
            "messages": conversation,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "output_format": output_schema,
        }

        if system_text:
            kwargs["system"] = system_text

        try:
            response = self.client.messages.parse(**kwargs)
            if response.parsed_output is not None:
                return response.parsed_output
            # If parsed_output is None, extract text and validate manually
            content = response.content[0].text
            logger.warning("Anthropic messages.parse() returned None parsed_output, falling back to manual parse")
            cleaned = self._clean_content(content)
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)
            return output_schema.model_validate_json(cleaned.strip())
        except AttributeError:
            # messages.parse() not available in this SDK version — fall back
            logger.info("messages.parse() not available, falling back to chat_json")
            expected_keys = tuple(output_schema.model_fields.keys())
            raw = self.chat_json(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                expected_keys=expected_keys,
            )
            return output_schema.model_validate(raw)
