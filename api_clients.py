"""API wrapper functions using OpenRouter for all translation providers."""

import os
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

from config import (
    TRANSLATION_PROMPT_WITH_IDENTITY,
    TRANSLATION_PROMPT_BASELINE,
    TRANSLATION_PROMPT_BACK,
    TRANSLATION_PROMPT_BACK_WITH_IDENTITY,
    OPENROUTER_BASE_URL,
)


class OpenRouterClient:
    """OpenRouter translation client that supports multiple models."""

    def __init__(self, model_id: str):
        """Initialize with a specific model ID.

        Args:
            model_id: The OpenRouter model identifier (e.g., 'anthropic/claude-sonnet-4-20250514')
        """
        self.client = OpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            base_url=OPENROUTER_BASE_URL,
        )
        self.model = model_id

    def _call_api(self, prompt: str) -> str:
        """Make an API call to OpenRouter.

        Args:
            prompt: The prompt to send to the model

        Returns:
            The model's response text
        """
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            extra_headers={
                "HTTP-Referer": "https://translation-sycophancy-detector.app",
                "X-Title": "Translation Sycophancy Detector",
            }
        )
        return response.choices[0].message.content

    def translate_to_intermediate(
        self, text: str, target_language: str, identity: Optional[str] = None
    ) -> str:
        """Translate from English to intermediate language.

        Args:
            text: The English text to translate
            target_language: The target language name (e.g., 'Spanish')
            identity: Optional identity statement to include in the prompt

        Returns:
            The translated text in the target language
        """
        if identity:
            prompt = TRANSLATION_PROMPT_WITH_IDENTITY.format(
                identity=identity,
                language=target_language,
                text=text
            )
        else:
            prompt = TRANSLATION_PROMPT_BASELINE.format(
                language=target_language,
                text=text
            )

        return self._call_api(prompt)

    def translate_to_english(
        self, text: str, source_language: str, identity: Optional[str] = None
    ) -> str:
        """Translate from intermediate language back to English.

        Args:
            text: The text in the intermediate language
            source_language: The source language name (e.g., 'Spanish')
            identity: Optional identity statement to include in the prompt

        Returns:
            The text translated back to English
        """
        if identity:
            prompt = TRANSLATION_PROMPT_BACK_WITH_IDENTITY.format(
                identity=identity,
                source_language=source_language,
                text=text
            )
        else:
            prompt = TRANSLATION_PROMPT_BACK.format(
                source_language=source_language,
                text=text
            )

        return self._call_api(prompt)


def get_client(model_id: str) -> OpenRouterClient:
    """Factory function to get a translation client for the specified model.

    Args:
        model_id: The OpenRouter model identifier

    Returns:
        An OpenRouterClient configured for the specified model
    """
    return OpenRouterClient(model_id)


def run_translation_path(
    client: OpenRouterClient,
    source_text: str,
    intermediate_language: str,
    identity: Optional[str] = None
) -> dict:
    """Run a complete translation path: English -> Intermediate -> English.

    Args:
        client: The OpenRouter client to use
        source_text: The original English text
        intermediate_language: The language to translate through
        identity: Optional identity statement for the prompt

    Returns:
        dict with keys:
            - intermediate: The intermediate language translation
            - back_to_english: The round-trip translation back to English
            - identity: The identity used (or None for baseline)
    """
    # Step 1: Translate to intermediate language (with identity context if provided)
    intermediate = client.translate_to_intermediate(
        source_text, intermediate_language, identity
    )

    # Step 2: Translate back to English (with same identity context)
    back_to_english = client.translate_to_english(
        intermediate, intermediate_language, identity
    )

    return {
        "intermediate": intermediate,
        "back_to_english": back_to_english,
        "identity": identity
    }


def run_all_paths_parallel(
    model_id: str,
    source_text: str,
    intermediate_language: str,
    identity_a: str,
    identity_b: str
) -> dict:
    """Run all three translation paths in parallel.

    Args:
        model_id: The OpenRouter model identifier to use
        source_text: The original English text
        intermediate_language: The language to translate through
        identity_a: The first identity statement
        identity_b: The second identity statement

    Returns:
        dict with keys: path_a, path_b, baseline
        Each containing the translation results, plus metadata
    """
    client = get_client(model_id)

    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all three paths
        future_a = executor.submit(
            run_translation_path, client, source_text, intermediate_language, identity_a
        )
        future_b = executor.submit(
            run_translation_path, client, source_text, intermediate_language, identity_b
        )
        future_baseline = executor.submit(
            run_translation_path, client, source_text, intermediate_language, None
        )

        # Collect results
        results = {
            "path_a": future_a.result(),
            "path_b": future_b.result(),
            "baseline": future_baseline.result(),
            "model_id": model_id,
            "intermediate_language": intermediate_language,
            "source_text": source_text,
            "identity_a": identity_a,
            "identity_b": identity_b,
        }

    return results
