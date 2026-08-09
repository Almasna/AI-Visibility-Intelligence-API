from __future__ import annotations

from dataclasses import dataclass

from app.utils.errors import LLMServiceError


@dataclass(frozen=True)
class LLMResult:
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMService:
    def __init__(
        self,
        *,
        provider: str,
        api_key: str | None,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        if provider.casefold() != "openai":
            raise LLMServiceError(
                f"Unsupported LLM_PROVIDER '{provider}'. This build supports 'openai'."
            )
        if not api_key:
            raise LLMServiceError("OPENAI_API_KEY is required to run AI agents.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMServiceError("The openai package is not installed.") from exc

        self.model = model
        self.client = OpenAI(api_key=api_key, timeout=timeout, max_retries=2)

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LLMResult:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = response.choices[0].message.content
            if not content:
                raise LLMServiceError("The LLM returned an empty response.")
            usage = response.usage
            return LLMResult(
                content=content,
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                completion_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
            )
        except LLMServiceError:
            raise
        except Exception as exc:
            raise LLMServiceError("The LLM provider request failed.") from exc
