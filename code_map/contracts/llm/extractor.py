# SPDX-License-Identifier: MIT
"""
Level 3: LLM-based contract extraction using Ollama.

Extracts implicit contracts from unstructured comments and docstrings.
"""

import logging
from typing import Optional

from ..schema import ContractData, ThreadSafety

logger = logging.getLogger(__name__)

# Prompt template for contract extraction
EXTRACTION_PROMPT = """Analyze the following code and extract implicit contracts.
Look for: preconditions, postconditions, invariants, errors, thread-safety.

CODE:
{code_block}

DOCUMENTATION:
{documentation}

Respond ONLY in valid YAML format with this schema:
```yaml
thread_safety: <not_safe|safe|safe_after_start|immutable|unknown>
invariants:
  - <invariant 1>
preconditions:
  - <precondition 1>
postconditions:
  - <postcondition 1>
errors:
  - <error 1>
confidence_notes: <brief explanation of why you inferred this>
```

If you cannot infer something with confidence, omit it.
Only include fields you are confident about."""


class LLMContractExtractor:
    """Extracts contracts using Ollama LLM."""

    def __init__(self, ollama_service=None):
        """
        Initialize the extractor.

        Args:
            ollama_service: Optional OllamaService instance.
                           If None, will try to import from code_map.
        """
        self._ollama = ollama_service
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        if self._available is not None:
            return self._available

        try:
            if self._ollama is None:
                from code_map.integrations.ollama_service import OllamaService

                self._ollama = OllamaService()

            # Try a simple ping
            self._available = self._ollama.is_available()
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            self._available = False

        return self._available

    async def extract(
        self, code_block: str, documentation: str
    ) -> ContractData:
        """
        Extract contract from code and documentation using LLM.

        Args:
            code_block: Source code around the symbol
            documentation: Comments/docstrings found near the symbol

        Returns:
            ContractData with extracted fields (may be partial)
        """
        if not self.is_available():
            return ContractData(
                confidence=0.0,
                source_level=3,
                confidence_notes="Ollama not available",
            )

        prompt = EXTRACTION_PROMPT.format(
            code_block=code_block[:2000],  # Limit size
            documentation=documentation[:1000],
        )

        try:
            response = await self._call_ollama(prompt)
            contract = self._parse_response(response)
            contract.source_level = 3
            contract.confidence = 0.6
            contract.needs_review = True
            return contract

        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return ContractData(
                confidence=0.0,
                source_level=3,
                confidence_notes=f"LLM extraction error: {str(e)}",
            )

    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama and return response text."""
        if self._ollama is None:
            from code_map.integrations.ollama_service import OllamaService

            self._ollama = OllamaService()

        # Use the chat method
        result = await self._ollama.chat_async(
            messages=[{"role": "user", "content": prompt}],
            model=None,  # Use default model
        )

        return result.get("message", {}).get("content", "")

    def _parse_response(self, response: str) -> ContractData:
        """Parse YAML response from LLM."""
        import yaml

        # Extract YAML block if wrapped in ```yaml ... ```
        if "```yaml" in response:
            start = response.find("```yaml") + 7
            end = response.find("```", start)
            if end > start:
                response = response[start:end]
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                response = response[start:end]

        try:
            data = yaml.safe_load(response)
        except yaml.YAMLError:
            return ContractData(
                confidence=0.0,
                confidence_notes="Failed to parse LLM response as YAML",
            )

        if not data or not isinstance(data, dict):
            return ContractData(confidence=0.0, confidence_notes="Empty LLM response")

        contract = ContractData()

        # Thread safety
        if "thread_safety" in data:
            try:
                contract.thread_safety = ThreadSafety(data["thread_safety"])
            except ValueError:
                pass

        # Lists
        contract.invariants = data.get("invariants", []) or []
        contract.preconditions = data.get("preconditions", []) or []
        contract.postconditions = data.get("postconditions", []) or []
        contract.errors = data.get("errors", []) or []

        # Confidence notes from LLM
        contract.confidence_notes = data.get("confidence_notes")

        return contract
