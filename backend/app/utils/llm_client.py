"""
LLM Client Wrapper
Supports OpenAI API, Anthropic API, Claude CLI, Codex CLI, and Gemini CLI
"""

import json
import re
import subprocess
import warnings
from typing import Any, Dict, Generator, Iterable, List, Optional

from ..config import Config
from .cost_estimator import CostEstimate, estimate_cost, estimate_tokens_from_text
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

    @property
    def supports_streaming(self) -> bool:
        """
        True when :meth:`chat_stream_text` can stream via an SDK (Anthropic or OpenAI-compatible).

        False for CLI providers (``claude-cli``, ``codex-cli``, ``gemini-cli``) or when
        ``self.client`` is unset.
        """
        if self.provider in ("claude-cli", "codex-cli", "gemini-cli"):
            return False
        return self.client is not None

    def estimate_call_cost(
        self,
        messages: List[Dict[str, str]],
        expected_completion_tokens: int = 1000,
        warn_threshold_usd: float = 0.10,
    ) -> CostEstimate:
        """
        Estimate cost of an LLM call before making it.

        Args:
            messages: The messages that would be sent.
            expected_completion_tokens: Estimated output tokens.
            warn_threshold_usd: Log a warning if estimated cost exceeds this.

        Returns:
            CostEstimate with breakdown.
        """
        prompt_text = " ".join(m.get("content", "") for m in messages)
        prompt_tokens = estimate_tokens_from_text(prompt_text)
        is_cli = self.provider in ("claude-cli", "codex-cli", "gemini-cli")

        est = estimate_cost(
            prompt_tokens=prompt_tokens,
            completion_tokens=expected_completion_tokens,
            model=self.model or "",
            is_cli=is_cli,
        )

        if est.total_cost_usd > warn_threshold_usd:
            logger.warning(
                "Expensive LLM call estimated: ~$%.4f "
                "(~%d prompt tokens, ~%d completion tokens, model=%s)",
                est.total_cost_usd,
                prompt_tokens,
                expected_completion_tokens,
                self.model,
            )
        else:
            logger.debug(
                "LLM call estimate: ~%d prompt tokens, ~%d completion, ~$%.6f",
                prompt_tokens,
                expected_completion_tokens,
                est.total_cost_usd,
            )

        return est

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
        """Remove <think>/<thinking> tags from reasoning models.

        If stripping thinking blocks would leave the response empty,
        fall back to extracting any JSON object found inside the
        thinking block itself (the model may have placed the answer there).
        """
        cleaned = re.sub(r'<think(?:ing)?>[\s\S]*?</think(?:ing)?>', '', content).strip()
        if cleaned:
            return cleaned

        # Thinking block consumed the entire response — try to salvage JSON from it
        match = re.search(r'(\{[\s\S]*\})', content)
        if match:
            logger.warning(
                "Response was entirely inside <think> tags; "
                "extracted JSON object (%d chars) from thinking block",
                len(match.group(1)),
            )
            return match.group(1).strip()

        # Nothing salvageable — return original (stripped of think tags = empty)
        return cleaned

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
                "Place your entire JSON response inside <json_output> tags.\n"
                "</instructions>"
            )

        for msg in conversation:
            role = msg.get("role", "user").upper()
            parts.append(f"<{role.lower()}>\n{msg['content']}\n</{role.lower()}>")

        if wants_json:
            parts.append(
                "<example>\n"
                "<json_output>\n"
                '{"key": "value"}\n'
                "</json_output>\n"
                "</example>"
            )
            parts.append(
                "<reminder>Place your JSON response inside <json_output> tags. "
                "No markdown, no explanation — only the <json_output> block.</reminder>"
            )

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

    def chat_stream_text(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Generator[str, None, None]:
        """
        Stream plain text deltas (OpenAI-compatible API and native Anthropic API only).

        Check :attr:`supports_streaming` before calling; when it is ``False``, prefer
        :meth:`chat` for a full non-streaming response.

        If invoked when :attr:`supports_streaming` is ``False``, emits ``UserWarning`` once
        per call, logs at debug for telemetry, and returns without yielding (no exception).
        """
        if not self.supports_streaming:
            warnings.warn(
                (
                    "LLMClient.chat_stream_text is not supported for this configuration "
                    f"(provider={self.provider!r}, no SDK streaming client). Use "
                    "LLMClient.chat() instead. Check LLMClient.supports_streaming before "
                    "calling to avoid this warning."
                ),
                UserWarning,
                stacklevel=2,
            )
            logger.debug(
                "chat_stream_text: streaming not supported for provider=%r (CLI or missing "
                "client); callers should use chat() as a non-streaming fallback",
                self.provider,
            )
            return
        if self.provider == "anthropic":
            system_text, conversation = self._split_system_message(messages)
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": conversation,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if system_text:
                kwargs["system"] = system_text
            with self.client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    if text:
                        yield text
            return
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = getattr(choice.delta, "content", None)
            if delta:
                yield delta

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
            content = self._run_claude_cli_text(prompt)

            # If --output-format text returned empty, retry with JSON format
            # and extract the assistant text from the structured output
            if not content:
                logger.warning(
                    "Claude CLI --output-format text returned empty, "
                    "retrying with --output-format json"
                )
                content = self._run_claude_cli_json(prompt)

            if not content:
                raise RuntimeError(
                    "Claude CLI returned empty response in both text and json modes"
                )

            content = self._clean_content(content)

            if response_format and response_format.get("type") == "json_object":
                content = self._extract_json_from_xml(content)

            return content

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Claude CLI timed out after {Config.CLI_TIMEOUT}s")

    def _run_claude_cli_text(self, prompt: str) -> str:
        """Run Claude CLI with --output-format text and return raw stdout."""
        result = subprocess.run(
            ["claude", "-p", "--output-format", "text"],
            input=prompt,
            capture_output=True, text=True, timeout=Config.CLI_TIMEOUT,
            cwd="/tmp",
        )

        if result.returncode != 0:
            logger.error("Claude CLI (text) error (rc=%d): %s", result.returncode, result.stderr[:300])
            raise RuntimeError(f"Claude CLI failed: {result.stderr[:200]}")

        content = result.stdout.strip()
        if not content:
            logger.warning(
                "Claude CLI (text) returned empty stdout. "
                "stderr (first 300 chars): %s",
                result.stderr[:300] if result.stderr else "<empty>",
            )
        else:
            logger.debug("Claude CLI (text) response length: %d chars", len(content))

        return content

    def _run_claude_cli_json(self, prompt: str) -> str:
        """Run Claude CLI with --output-format json and extract assistant text.

        The JSON format returns an array of event objects.  We look for
        ``{"type": "assistant", "subtype": "text", ...}`` entries and
        concatenate their ``text`` fields.
        """
        result = subprocess.run(
            ["claude", "-p", "--output-format", "json"],
            input=prompt,
            capture_output=True, text=True, timeout=Config.CLI_TIMEOUT,
            cwd="/tmp",
        )

        if result.returncode != 0:
            logger.error("Claude CLI (json) error (rc=%d): %s", result.returncode, result.stderr[:300])
            raise RuntimeError(f"Claude CLI (json) failed: {result.stderr[:200]}")

        raw = result.stdout.strip()
        if not raw:
            logger.warning("Claude CLI (json) also returned empty stdout")
            return ""

        try:
            events = json.loads(raw)
        except json.JSONDecodeError:
            # Might be NDJSON (one object per line)
            events = []
            for line in raw.splitlines():
                line = line.strip().rstrip(",")
                if not line or line in ("[]", "[", "]"):
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        if not isinstance(events, list):
            events = [events]

        # Extract assistant text blocks
        text_parts = []
        for evt in events:
            if not isinstance(evt, dict):
                continue
            if evt.get("type") == "assistant" and evt.get("subtype") == "text":
                text_parts.append(evt.get("text", ""))
            # Also check for result event (some CLI versions)
            elif evt.get("type") == "result":
                if "result" in evt:
                    text_parts.append(str(evt["result"]))

        content = "\n".join(text_parts).strip()
        logger.debug("Claude CLI (json) extracted %d text parts, %d chars total",
                     len(text_parts), len(content))
        return content

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
                capture_output=True, text=True, timeout=Config.CLI_TIMEOUT,
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
            raise RuntimeError(f"Codex CLI timed out after {Config.CLI_TIMEOUT}s")

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
                capture_output=True, text=True, timeout=Config.CLI_TIMEOUT,
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
            raise RuntimeError(f"Gemini CLI timed out after {Config.CLI_TIMEOUT}s")

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
