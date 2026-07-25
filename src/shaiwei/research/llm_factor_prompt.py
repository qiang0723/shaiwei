"""Frozen D1-2A prompt, knowledge-manifest and feedback contracts."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


TOPICS = (
    "trend_momentum",
    "reversal_mean_reversion",
    "volatility_range",
    "liquidity_volume",
    "price_volume_state",
)
PROMPT_SCHEMA = "d1-prompt-bundle-v1"
KNOWLEDGE_SCHEMA = "d1-knowledge-manifest-v1"
ALLOWED_SOURCE_TYPES = {"official_provider_documentation", "primary_research_paper"}


class PromptContractError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timezone_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise PromptContractError(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PromptContractError(f"{field} must be an ISO-8601 string") from error
    if parsed.tzinfo is None:
        raise PromptContractError(f"{field} must contain a timezone")
    return parsed


def _required_mapping(document: dict[str, Any], field: str) -> dict[str, Any]:
    value = document.get(field)
    if not isinstance(value, dict):
        raise PromptContractError(f"{field} must be an object")
    return value


@dataclass(frozen=True)
class PromptBundle:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str) -> "PromptBundle":
        if not path.is_file():
            raise PromptContractError(f"prompt bundle is missing: {path}")
        if sha256_file(path) != expected_sha256:
            raise PromptContractError("prompt bundle hash differs from the frozen protocol")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("schema_version") != PROMPT_SCHEMA:
            raise PromptContractError("prompt bundle schema is invalid")
        system_prompt = document.get("system_prompt")
        if not isinstance(system_prompt, str) or len(system_prompt.strip()) < 200:
            raise PromptContractError("system prompt is missing or too short")
        topics = _required_mapping(document, "topic_templates")
        if tuple(topics) != TOPICS:
            raise PromptContractError("prompt topic order differs from the frozen contract")
        for topic, template in topics.items():
            if not isinstance(template, dict) or not isinstance(template.get("objective"), str):
                raise PromptContractError(f"topic template is invalid: {topic}")
            if not template.get("allowed_questions") or not template.get("guardrails"):
                raise PromptContractError(f"topic template is incomplete: {topic}")
        feedback = _required_mapping(document, "feedback_contract")
        allowed = feedback.get("allowed_fields")
        forbidden = feedback.get("forbidden_fields")
        if not isinstance(allowed, list) or len(allowed) != len(set(allowed)):
            raise PromptContractError("feedback allowlist is invalid")
        if not isinstance(forbidden, list) or set(allowed).intersection(forbidden):
            raise PromptContractError("feedback forbidden fields are invalid")
        if int(feedback.get("maximum_records", -1)) != 7:
            raise PromptContractError("feedback record limit differs from the frozen contract")
        return cls(path=path, document=document, sha256=expected_sha256)

    @property
    def system_prompt(self) -> str:
        return str(self.document["system_prompt"])

    def topic_template(self, topic: str) -> dict[str, Any]:
        if topic not in TOPICS:
            raise PromptContractError(f"unknown D1 topic: {topic}")
        return dict(self.document["topic_templates"][topic])

    def serialize_feedback(
        self,
        *,
        topic: str,
        current_global_ordinal: int,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        contract = self.document["feedback_contract"]
        allowed = tuple(contract["allowed_fields"])
        forbidden = set(contract["forbidden_fields"])
        normalized: list[dict[str, Any]] = []
        seen_attempts: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                raise PromptContractError("feedback record must be an object")
            unknown = set(record) - set(allowed)
            if unknown:
                raise PromptContractError(f"feedback contains non-allowlisted fields: {sorted(unknown)}")
            if set(record).intersection(forbidden):
                raise PromptContractError("feedback contains result or production fields")
            if record.get("topic") != topic:
                raise PromptContractError("feedback must come from the same topic")
            attempt_id = record.get("attempt_id")
            ordinal = record.get("global_ordinal")
            if not isinstance(attempt_id, str) or not attempt_id:
                raise PromptContractError("feedback attempt_id is invalid")
            if isinstance(ordinal, bool) or not isinstance(ordinal, int):
                raise PromptContractError("feedback global_ordinal is invalid")
            if ordinal >= current_global_ordinal:
                raise PromptContractError("feedback must precede the current attempt")
            if attempt_id in seen_attempts:
                raise PromptContractError("feedback attempt ids must be unique")
            for field, value in record.items():
                if field in {"discovery_coverage", "discovery_rank_ic"}:
                    if value is not None and (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(float(value))
                    ):
                        raise PromptContractError(f"feedback numeric field is invalid: {field}")
                    if field == "discovery_coverage" and value is not None and not 0 <= value <= 1:
                        raise PromptContractError("feedback discovery_coverage must be within 0..1")
                    if field == "discovery_rank_ic" and value is not None and not -1 <= value <= 1:
                        raise PromptContractError("feedback discovery_rank_ic must be within -1..1")
                elif field in {"expression_tokens", "ast_nodes", "max_lookback_days"}:
                    if value is not None and (
                        isinstance(value, bool) or not isinstance(value, int) or value < 0
                    ):
                        raise PromptContractError(f"feedback integer field is invalid: {field}")
                elif field not in {"global_ordinal"} and value is not None:
                    if not isinstance(value, str) or len(value) > 1000:
                        raise PromptContractError(f"feedback text field is invalid: {field}")
                    if any(ord(character) < 32 for character in value):
                        raise PromptContractError(f"feedback text contains control characters: {field}")
            seen_attempts.add(attempt_id)
            normalized.append({field: record.get(field) for field in allowed})
        normalized.sort(key=lambda row: (int(row["global_ordinal"]), str(row["attempt_id"])))
        if len(normalized) > int(contract["maximum_records"]):
            raise PromptContractError("feedback exceeds the frozen record limit")
        return normalized


@dataclass(frozen=True)
class KnowledgeManifest:
    path: Path
    document: dict[str, Any]
    sha256: str
    entries_by_topic: dict[str, tuple[dict[str, Any], ...]]

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        expected_sha256: str,
        expected_cutoff: str,
    ) -> "KnowledgeManifest":
        if not path.is_file():
            raise PromptContractError(f"knowledge manifest is missing: {path}")
        if sha256_file(path) != expected_sha256:
            raise PromptContractError("knowledge manifest hash differs from the frozen protocol")
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("schema_version") != KNOWLEDGE_SCHEMA:
            raise PromptContractError("knowledge manifest schema is invalid")
        if document.get("knowledge_cutoff") != expected_cutoff:
            raise PromptContractError("knowledge cutoff differs from the frozen protocol")
        cutoff = _timezone_timestamp(document.get("knowledge_cutoff"), "knowledge_cutoff")
        if document.get("full_text_stored") is not False or document.get("full_text_prompted") is not False:
            raise PromptContractError("full-text knowledge must remain disabled")
        entries = document.get("entries")
        if not isinstance(entries, list) or not entries:
            raise PromptContractError("knowledge manifest has no entries")
        source_ids: set[str] = set()
        source_urls: set[str] = set()
        topic_entries: dict[str, list[dict[str, Any]]] = {topic: [] for topic in TOPICS}
        for entry in entries:
            if not isinstance(entry, dict):
                raise PromptContractError("knowledge entry must be an object")
            source_id = entry.get("source_id")
            if not isinstance(source_id, str) or not source_id or source_id in source_ids:
                raise PromptContractError("knowledge source ids must be non-empty and unique")
            source_ids.add(source_id)
            if entry.get("source_type") not in ALLOWED_SOURCE_TYPES:
                raise PromptContractError(f"knowledge source type is not allowed: {source_id}")
            roles = entry.get("roles")
            if not isinstance(roles, list) or len(roles) != 1:
                raise PromptContractError(f"knowledge source role is invalid: {source_id}")
            parsed_url = urlparse(str(entry.get("source_url", "")))
            if parsed_url.scheme != "https" or not parsed_url.netloc:
                raise PromptContractError(f"knowledge source URL must use HTTPS: {source_id}")
            source_url = str(entry["source_url"])
            if source_url in source_urls:
                raise PromptContractError(f"knowledge source URLs must be unique: {source_id}")
            source_urls.add(source_url)
            authors = entry.get("publisher_or_authors")
            if (
                not isinstance(authors, list)
                or not authors
                or any(not isinstance(author, str) or not author.strip() for author in authors)
            ):
                raise PromptContractError(f"knowledge authors or publisher are invalid: {source_id}")
            try:
                date.fromisoformat(str(entry.get("published_at", "")))
            except ValueError as error:
                raise PromptContractError(
                    f"knowledge publication date is invalid: {source_id}"
                ) from error
            retrieved = _timezone_timestamp(entry.get("retrieved_at"), f"{source_id}.retrieved_at")
            if retrieved > cutoff:
                raise PromptContractError(f"knowledge source was retrieved after cutoff: {source_id}")
            capture = entry.get("content_capture")
            if not isinstance(capture, dict) or entry.get("content_sha256") != sha256_text(
                canonical_json(capture)
            ):
                raise PromptContractError(f"knowledge content hash differs: {source_id}")
            facts = capture.get("facts") if isinstance(capture, dict) else None
            if (
                not isinstance(capture.get("title"), str)
                or not isinstance(facts, list)
                or not 1 <= len(facts) <= 8
                or any(not isinstance(fact, str) or not fact or len(fact) > 500 for fact in facts)
                or len(canonical_json(capture)) > 5000
            ):
                raise PromptContractError(f"knowledge capture is invalid or too large: {source_id}")
            summary = entry.get("authored_summary")
            if not isinstance(summary, str) or not 30 <= len(summary.strip()) <= 1000:
                raise PromptContractError(f"knowledge authored summary is invalid: {source_id}")
            if entry.get("authored_summary_sha256") != sha256_text(summary):
                raise PromptContractError(f"knowledge summary hash differs: {source_id}")
            topics = entry.get("topics")
            if not isinstance(topics, list) or any(topic not in TOPICS for topic in topics):
                raise PromptContractError(f"knowledge topics are invalid: {source_id}")
            prompt_eligible = entry.get("prompt_eligible")
            if not isinstance(prompt_eligible, bool):
                raise PromptContractError(f"knowledge prompt eligibility is invalid: {source_id}")
            if not isinstance(entry.get("retrospective_discovery"), bool):
                raise PromptContractError(f"knowledge retrospective flag is invalid: {source_id}")
            usage_basis = entry.get("license_or_usage_basis")
            if not isinstance(usage_basis, str) or len(usage_basis.strip()) < 20:
                raise PromptContractError(f"knowledge usage basis is invalid: {source_id}")
            if prompt_eligible:
                if (
                    entry.get("source_type") != "primary_research_paper"
                    or roles != ["research_knowledge"]
                    or len(topics) != 1
                ):
                    raise PromptContractError(
                        f"prompt knowledge must be one primary paper for one topic: {source_id}"
                    )
                if entry["retrospective_discovery"] is not True:
                    raise PromptContractError(
                        f"historical prompt knowledge must be retrospective: {source_id}"
                    )
                topic_entries[topics[0]].append(entry)
            elif topics:
                raise PromptContractError(
                    f"execution-only knowledge cannot be assigned a research topic: {source_id}"
                )
            elif (
                entry.get("source_type") != "official_provider_documentation"
                or roles != ["execution_contract"]
                or entry["retrospective_discovery"] is not False
            ):
                raise PromptContractError(f"execution knowledge role is invalid: {source_id}")
        if any(len(values) != 1 for values in topic_entries.values()):
            raise PromptContractError("each topic must have exactly one prompt-eligible primary source")
        frozen = {topic: tuple(values) for topic, values in topic_entries.items()}
        return cls(path=path, document=document, sha256=expected_sha256, entries_by_topic=frozen)

    def packet_for_topic(self, topic: str) -> list[dict[str, Any]]:
        if topic not in TOPICS:
            raise PromptContractError(f"unknown D1 topic: {topic}")
        return [
            {
                "source_id": entry["source_id"],
                "source_type": entry["source_type"],
                "source_url": entry["source_url"],
                "published_at": entry["published_at"],
                "retrospective_discovery": entry["retrospective_discovery"],
                "authored_summary": entry["authored_summary"],
                "authored_summary_sha256": entry["authored_summary_sha256"],
            }
            for entry in self.entries_by_topic[topic]
        ]
