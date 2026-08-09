from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests

from app.utils.domains import domains_match, normalize_domain
from app.utils.errors import (
    ExternalAuthenticationError,
    ExternalDataError,
    ExternalRateLimitError,
)


@dataclass(frozen=True)
class SearchMetrics:
    search_volume: int
    competitive_difficulty: float


@dataclass(frozen=True)
class VisibilityResult:
    domain_visible: bool
    visibility_position: int | None
    source: str = "dataforseo_chatgpt_web_search"
    tokens_used: int | None = None


class ExternalDataService:
    """DataForSEO v3 adapter for Google Ads metrics and ChatGPT citations."""

    SEARCH_VOLUME_PATH = "/v3/keywords_data/google_ads/search_volume/live"
    AI_VISIBILITY_PATH = "/v3/ai_optimization/chat_gpt/llm_responses/live"

    def __init__(
        self,
        *,
        login: str | None,
        password: str | None,
        base_url: str = "https://api.dataforseo.com",
        timeout: float = 125.0,
        location_code: int = 2840,
        language_code: str = "en",
        ai_model: str = "gpt-4.1-mini",
        country_code: str = "US",
        session: requests.Session | None = None,
    ) -> None:
        if not login or not password:
            raise ExternalAuthenticationError(
                "DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD are required."
            )
        self.auth = (login, password)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.location_code = location_code
        self.language_code = language_code
        self.ai_model = ai_model
        self.country_code = country_code
        self.session = session or requests.Session()

    @staticmethod
    def _provider_keyword(query: str) -> str:
        # Google Ads accepts at most 10 words / 80 characters. Preserve intent while
        # stripping question punctuation that has no keyword-volume meaning.
        cleaned = re.sub(r"[^\w\s'-]", " ", query.casefold())
        cleaned = " ".join(cleaned.split()[:10])
        return cleaned[:80].strip()

    def get_keyword_metrics(self, queries: list[str]) -> dict[str, SearchMetrics]:
        if not queries:
            return {}
        provider_to_originals: dict[str, list[str]] = {}
        for query in queries:
            provider_keyword = self._provider_keyword(query)
            if not provider_keyword:
                continue
            provider_to_originals.setdefault(provider_keyword, []).append(query)

        payload = [
            {
                "keywords": list(provider_to_originals),
                "location_code": self.location_code,
                "language_code": self.language_code,
                "search_partners": False,
            }
        ]
        task = self._post(self.SEARCH_VOLUME_PATH, payload)
        results = task.get("result") or []
        by_provider_keyword: dict[str, SearchMetrics] = {}
        for item in results:
            keyword = str(item.get("keyword") or "").casefold().strip()
            volume = item.get("search_volume")
            difficulty = item.get("competition_index")
            if keyword and volume is not None and difficulty is not None:
                by_provider_keyword[keyword] = SearchMetrics(
                    search_volume=max(0, int(volume)),
                    competitive_difficulty=min(100.0, max(0.0, float(difficulty))),
                )

        mapped: dict[str, SearchMetrics] = {}
        for provider_keyword, originals in provider_to_originals.items():
            metric = by_provider_keyword.get(provider_keyword.casefold())
            if metric is not None:
                for original in originals:
                    mapped[original] = metric
        return mapped

    def get_search_volume(self, query: str) -> int:
        metrics = self.get_keyword_metrics([query]).get(query)
        if metrics is None:
            raise ExternalDataError("DataForSEO returned no keyword metrics.")
        return metrics.search_volume

    def get_competition(self, query: str) -> float:
        metrics = self.get_keyword_metrics([query]).get(query)
        if metrics is None:
            raise ExternalDataError("DataForSEO returned no keyword metrics.")
        return metrics.competitive_difficulty

    def check_ai_visibility(
        self, query: str, target_domain: str
    ) -> VisibilityResult:
        target = normalize_domain(target_domain)
        payload = [
            {
                "user_prompt": query[:500],
                "system_message": (
                    "Answer the user's question directly as an impartial expert. "
                    "Recommend specific options when relevant and cite current web sources."
                ),
                "model_name": self.ai_model,
                "max_output_tokens": 1024,
                "temperature": 0.2,
                "web_search": True,
                "force_web_search": True,
                "web_search_country_iso_code": self.country_code,
            }
        ]
        task = self._post(self.AI_VISIBILITY_PATH, payload)
        results = task.get("result") or []
        if not results:
            raise ExternalDataError("DataForSEO returned no AI visibility result.")
        result = results[0]
        tokens = _sum_optional(result.get("input_tokens"), result.get("output_tokens"))

        source_domains: list[str] = []
        answer_texts: list[str] = []
        for item in result.get("items") or []:
            if item.get("type") != "message":
                continue
            for section in item.get("sections") or []:
                text = section.get("text")
                if isinstance(text, str):
                    answer_texts.append(text)
                for annotation in section.get("annotations") or []:
                    url = annotation.get("url")
                    if not isinstance(url, str):
                        continue
                    hostname = urlsplit(url).hostname
                    if not hostname:
                        continue
                    try:
                        domain = normalize_domain(hostname)
                    except ValueError:
                        continue
                    if domain not in source_domains:
                        source_domains.append(domain)

        for position, source_domain in enumerate(source_domains, start=1):
            if domains_match(source_domain, target):
                return VisibilityResult(True, position, tokens_used=tokens)

        # An uncited literal domain mention counts as visible, but has no defensible
        # citation rank and therefore no position.
        domain_pattern = re.compile(
            rf"(?<![a-z0-9.-])(?:www\.)?{re.escape(target)}(?![a-z0-9.-])",
            re.IGNORECASE,
        )
        literal_mention = any(domain_pattern.search(text) for text in answer_texts)
        return VisibilityResult(literal_mention, None, tokens_used=tokens)

    def _post(self, path: str, payload: list[dict]) -> dict:
        try:
            response = self.session.post(
                f"{self.base_url}{path}",
                json=payload,
                auth=self.auth,
                timeout=self.timeout,
                headers={"Accept": "application/json"},
            )
        except requests.Timeout as exc:
            raise ExternalDataError("DataForSEO request timed out.") from exc
        except requests.ConnectionError as exc:
            raise ExternalDataError("Could not connect to DataForSEO.") from exc
        except requests.RequestException as exc:
            raise ExternalDataError("DataForSEO request failed.") from exc

        if response.status_code in {401, 403}:
            raise ExternalAuthenticationError("DataForSEO rejected the credentials.")
        if response.status_code == 429:
            raise ExternalRateLimitError("DataForSEO rate limit exceeded.")
        if not response.ok:
            raise ExternalDataError(
                f"DataForSEO returned HTTP status {response.status_code}."
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise ExternalDataError("DataForSEO returned invalid JSON.") from exc

        if body.get("status_code") != 20000:
            raise ExternalDataError(
                f"DataForSEO error {body.get('status_code')}: "
                f"{body.get('status_message', 'Unknown provider error')}"
            )
        tasks = body.get("tasks") or []
        if not tasks:
            raise ExternalDataError("DataForSEO returned no task result.")
        task = tasks[0]
        if task.get("status_code") != 20000:
            raise ExternalDataError(
                f"DataForSEO task error {task.get('status_code')}: "
                f"{task.get('status_message', 'Unknown provider error')}"
            )
        return task


def _sum_optional(*values: object) -> int | None:
    present = [int(value) for value in values if isinstance(value, (int, float))]
    return sum(present) if present else None
