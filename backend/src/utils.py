"""Utility helpers shared across deep researcher services."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Union
from urllib.parse import urlparse

CHARS_PER_TOKEN = 4

logger = logging.getLogger(__name__)


def get_config_value(value: Any) -> str:
    """Return configuration value as plain string."""

    return value if isinstance(value, str) else value.value


def classify_source_tier(url: str) -> tuple[int, str]:
    """Classify a source deterministically from its domain.

    This is intentionally conservative: unknown domains default to tier 3
    rather than being treated as authoritative.
    """

    hostname = (urlparse(url).hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    parsed_url = urlparse(url)
    path_parts = [
        part.lower()
        for part in parsed_url.path.split("/")
        if part
    ]

    tier_1_domains = {
        "qwenlm.github.io",
        "arxiv.org",
    }

    tier_2_domains = {
        "help.aliyun.com",
        "alibabacloud.com",
        "docs.vllm.ai",
        "artificialanalysis.ai",
    }

    tier_3_domains = {
        "promptquorum.com",
        "zhetao.com",
        "csdn.net",
        "blog.csdn.net",
        "cnblogs.com",
        "medium.com",
        "baike.baidu.com",
        "53ai.com",
        "openinstall.com",
    }

    if hostname in tier_1_domains:
        return 1, "一级来源"

    # GitHub 的可信等级不能只根据域名判断。
    # 仅 QwenLM 官方组织下的仓库视为一级来源。
    if hostname == "github.com":
        repository_owner = path_parts[0] if path_parts else ""

        if repository_owner == "qwenlm":
            return 1, "一级来源"

        return 3, "三级来源（非官方 GitHub 仓库，保守分级）"

    if hostname in tier_2_domains:
        return 2, "二级来源"

    if hostname in tier_3_domains:
        return 3, "三级来源"

    return 3, "三级来源（未识别域名，保守分级）"


def strip_thinking_tokens(text: str) -> str:
    """Remove ``<think>`` sections from model responses."""

    while "<think>" in text and "</think>" in text:
        start = text.find("<think>")
        end = text.find("</think>") + len("</think>")
        text = text[:start] + text[end:]
    return text


def deduplicate_and_format_sources(
    search_response: Dict[str, Any] | List[Dict[str, Any]],
    max_tokens_per_source: int,
    *,
    fetch_full_page: bool = False,
) -> str:
    """Format and deduplicate search results for downstream prompting."""

    if isinstance(search_response, dict):
        sources_list = search_response.get("results", [])
    else:
        sources_list = search_response

    unique_sources: dict[str, Dict[str, Any]] = {}
    for source in sources_list:
        url = source.get("url")
        if not url:
            continue
        if url not in unique_sources:
            unique_sources[url] = source

    formatted_parts: List[str] = []
    for source in unique_sources.values():
        title = source.get("title") or source.get("url", "")
        url = source.get("url", "")
        content = source.get("content", "")
        tier, tier_label = classify_source_tier(url)

        formatted_parts.append(f"信息来源: {title}\n\n")
        formatted_parts.append(f"URL: {url}\n\n")
        formatted_parts.append(f"来源等级: {tier_label}（tier={tier}）\n\n")
        formatted_parts.append(
            "使用要求: 必须严格使用此处给出的来源等级，禁止自行升级或降级。\n\n"
        )
        formatted_parts.append(f"信息内容: {content}\n\n")

        if fetch_full_page:
            raw_content = source.get("raw_content")
            if raw_content is None:
                logger.debug("raw_content missing for %s", source.get("url", ""))
                raw_content = ""
            char_limit = max_tokens_per_source * CHARS_PER_TOKEN
            if len(raw_content) > char_limit:
                raw_content = f"{raw_content[:char_limit]}... [truncated]"
            formatted_parts.append(
                f"详细信息内容限制为 {max_tokens_per_source} 个 token: {raw_content}\n\n"
            )

    return "".join(formatted_parts).strip()


def format_sources(search_results: Dict[str, Any] | None) -> str:
    """Return bullet list summarising search sources."""

    if not search_results:
        return ""

    results = search_results.get("results", [])
    formatted_sources: List[str] = []

    for item in results:
        url = item.get("url")
        if not url:
            continue

        title = item.get("title", url)
        tier, tier_label = classify_source_tier(url)

        formatted_sources.append(
            f"* [{tier_label} | tier={tier}] {title} : {url}"
        )

    return "\n".join(formatted_sources)
