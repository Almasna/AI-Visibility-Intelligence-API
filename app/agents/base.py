from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.utils.errors import AgentError


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class BaseAgent:
    @staticmethod
    def parse_and_validate(raw: str, schema: type[SchemaT]) -> SchemaT:
        candidate = raw.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            candidate = "\n".join(lines).strip()
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            start, end = candidate.find("{"), candidate.rfind("}")
            if start < 0 or end <= start:
                raise AgentError("The agent returned invalid JSON.")
            try:
                payload = json.loads(candidate[start : end + 1])
            except json.JSONDecodeError as exc:
                raise AgentError("The agent returned invalid JSON.") from exc
        try:
            return schema.model_validate(payload)
        except ValidationError as exc:
            raise AgentError("The agent response failed schema validation.") from exc
