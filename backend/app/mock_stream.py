"""Deterministic fake agent stream for UI development and demo fallback.

Activated when MOCK_TINYFISH=1 or when TINYFISH_API_KEY is unset.

It emits the same event shapes a real TinyFish run would produce, so the
rest of the pipeline (Redis publishers, Cosmo router, React UI) sees
identical data and the demo works end-to-end without burning credits.

Topic catalog is intentionally small: "AI chip supply chain" is the
default demo topic.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .entity_hash import entity_id, relationship_id
from .redis_client import (
    load_session,
    mark_url_visited,
    publish_agent_status,
    publish_crawl_log,
    publish_edge,
    publish_node,
    publish_timeline_event,
    save_session,
    set_streaming_url,
)
from .schemas import (
    AgentState,
    AgentStatus,
    CrawlLogEntry,
    Entity,
    LogLevel,
    Relationship,
    SourceRef,
    SessionStatus,
    TimelineEvent,
    TimelineEventType,
)

log = logging.getLogger(__name__)


# Default canned topic scripts. Each page visit contributes a few entities
# and edges. Keep names unique across pages so deterministic IDs collide
# when (correctly) the same entity reappears across sources.
MOCK_CATALOG: dict[str, list[dict[str, Any]]] = {
    "AI chip supply chain": [
        {
            "url": "https://en.wikipedia.org/wiki/TSMC",
            "title": "TSMC - Wikipedia",
            "entities": [
                {
                    "name": "TSMC",
                    "type": "company",
                    "claims": [
                        "World's largest dedicated independent semiconductor foundry.",
                        "Headquartered in Hsinchu, Taiwan.",
                    ],
                    "rationale": "TSMC manufactures the majority of leading-edge AI accelerators sold worldwide, making it the critical bottleneck of the entire AI chip supply chain.",
                    "excerpt": "Taiwan Semiconductor Manufacturing Company Limited, commonly known as TSMC, is a Taiwanese multinational semiconductor contract manufacturing and design company. It is the world's most valuable semiconductor company, and the world's largest dedicated independent semiconductor foundry. TSMC's products are used in everything from consumer electronics to the most advanced AI accelerators shipped by NVIDIA and AMD.",
                },
                {
                    "name": "Morris Chang",
                    "type": "person",
                    "claims": ["Founded TSMC in 1987."],
                    "rationale": "Chang's decision to pioneer the pure-play foundry model reshaped the global semiconductor industry.",
                    "excerpt": "Morris Chang is a Taiwanese-American businessman who founded TSMC in 1987 after a long career at Texas Instruments. His pure-play foundry model separated chip design from manufacturing for the first time and remains the template for the modern semiconductor industry.",
                },
                {
                    "name": "Foundry model",
                    "type": "concept",
                    "claims": ["Pure-play contract manufacturing of integrated circuits."],
                    "rationale": "The foundry model is the structural reason fabless chip designers like NVIDIA exist.",
                    "excerpt": "The pure-play foundry model is a business structure in which a company dedicates itself exclusively to contract manufacturing of integrated circuits designed by other firms. This decoupling of design and fabrication enabled the rise of fabless giants like NVIDIA and AMD.",
                },
            ],
            "relationships": [
                ("Morris Chang", "founded", "TSMC"),
                ("TSMC", "operates_under", "Foundry model"),
            ],
        },
        {
            "url": "https://en.wikipedia.org/wiki/Nvidia",
            "title": "Nvidia - Wikipedia",
            "entities": [
                {
                    "name": "NVIDIA",
                    "type": "company",
                    "claims": [
                        "Designs GPUs and AI accelerators.",
                        "Largest AI chip designer by revenue.",
                    ],
                    "rationale": "NVIDIA captures the majority of data-center AI accelerator revenue, making it the demand-side anchor of the supply chain.",
                    "excerpt": "Nvidia Corporation is an American multinational technology company headquartered in Santa Clara, California. It designs graphics processing units (GPUs), application programming interfaces (APIs) for data science and high-performance computing, as well as system-on-chip units (SoCs) for the mobile computing and automotive markets. Nvidia is a dominant supplier of AI hardware and software.",
                },
                {
                    "name": "Jensen Huang",
                    "type": "person",
                    "claims": ["Co-founded NVIDIA, current CEO."],
                    "rationale": "Huang has personally steered NVIDIA toward data-center AI since 2012, catalyzing the current boom.",
                    "excerpt": "Jensen Huang co-founded Nvidia in 1993 and has served as its president and CEO ever since. Under his leadership the company pivoted from graphics cards for PC gaming to data-center accelerators that power most modern AI workloads.",
                },
                {
                    "name": "H100",
                    "type": "concept",
                    "claims": ["NVIDIA's flagship AI training accelerator."],
                    "rationale": "H100 is the GPU most frontier-model labs depend on, and it is manufactured by TSMC.",
                    "excerpt": "The NVIDIA H100 is a Hopper-architecture data-center GPU designed for AI training at scale. It is manufactured on TSMC's 4N process and has been the most sought-after AI accelerator for frontier model training throughout 2023-2025.",
                },
            ],
            "relationships": [
                ("Jensen Huang", "founded", "NVIDIA"),
                ("NVIDIA", "designs", "H100"),
                ("TSMC", "supplies", "NVIDIA"),
            ],
        },
        {
            "url": "https://en.wikipedia.org/wiki/ASML_Holding",
            "title": "ASML Holding - Wikipedia",
            "entities": [
                {
                    "name": "ASML",
                    "type": "company",
                    "claims": [
                        "Only producer of EUV lithography systems used in leading-edge fabs.",
                    ],
                    "rationale": "ASML is a single-supplier monopoly for the lithography tools every leading-edge fab depends on.",
                    "excerpt": "ASML Holding N.V. is a Dutch multinational corporation and the largest supplier in the world of photolithography systems for the semiconductor industry. ASML is the sole producer of extreme ultraviolet (EUV) lithography machines, which are required to manufacture chips at the most advanced process nodes used by TSMC and Samsung Foundry.",
                },
                {
                    "name": "EUV lithography",
                    "type": "concept",
                    "claims": ["Extreme ultraviolet lithography; essential for sub-7nm chips."],
                    "rationale": "Without EUV, fabs cannot produce sub-7nm chips, making this the technology choke point of the AI chip supply chain.",
                    "excerpt": "Extreme ultraviolet lithography (EUV or EUVL) is a next-generation lithography technology using an EUV wavelength of 13.5 nm. Commercial EUV scanners, all built by ASML, are used by TSMC and Samsung Foundry for manufacturing the advanced 5-nanometer and 3-nanometer nodes that modern AI accelerators depend on.",
                },
            ],
            "relationships": [
                ("ASML", "manufactures", "EUV lithography"),
                ("TSMC", "uses", "EUV lithography"),
            ],
        },
        {
            "url": "https://en.wikipedia.org/wiki/Arm_Holdings",
            "title": "Arm Holdings - Wikipedia",
            "entities": [
                {
                    "name": "Arm",
                    "type": "company",
                    "claims": [
                        "Licenses CPU architectures used in most mobile and AI SoCs.",
                    ],
                    "rationale": "Arm IP is inside nearly every mobile and server AI accelerator, including NVIDIA's Grace CPU.",
                    "excerpt": "Arm Holdings plc is a British semiconductor and software design company based in Cambridge, England. Its primary business is in the design of ARM processors (CPUs). Arm licenses its architectures to most major chip designers including NVIDIA, Apple, and Qualcomm.",
                },
                {
                    "name": "Neoverse",
                    "type": "concept",
                    "claims": ["Arm server CPU platform targeted at data centers."],
                    "rationale": "Neoverse is Arm's data-center platform and underpins NVIDIA's Grace CPU.",
                    "excerpt": "Arm Neoverse is a family of 64-bit ARM architecture-based CPU cores and platforms aimed at data center, cloud, and HPC workloads. NVIDIA's Grace CPU, paired with its Hopper and Blackwell GPUs, is built on Neoverse cores.",
                },
            ],
            "relationships": [
                ("Arm", "licenses_to", "NVIDIA"),
                ("NVIDIA", "uses", "Neoverse"),
            ],
        },
        {
            "url": "https://en.wikipedia.org/wiki/Samsung_Foundry",
            "title": "Samsung Foundry - Wikipedia",
            "entities": [
                {
                    "name": "Samsung Foundry",
                    "type": "company",
                    "claims": [
                        "Second-largest foundry by revenue, competes with TSMC on leading-edge nodes.",
                    ],
                    "rationale": "Samsung is TSMC's only viable competitor for leading-edge nodes, providing a second source of supply.",
                    "excerpt": "Samsung Foundry is the semiconductor contract manufacturing business of Samsung Electronics. It is the second-largest foundry in the world by revenue and one of only three companies - alongside TSMC and Intel Foundry - capable of manufacturing chips at sub-5nm nodes that modern AI accelerators require.",
                },
            ],
            "relationships": [
                ("Samsung Foundry", "competes_with", "TSMC"),
            ],
        },
    ],
}


def _script_for(topic: str) -> list[dict[str, Any]]:
    """Best-effort topic match. Falls back to the AI chip script."""
    normalized = topic.strip().lower()
    for key, script in MOCK_CATALOG.items():
        if key.lower() in normalized or normalized in key.lower():
            return script
    return MOCK_CATALOG["AI chip supply chain"]


def get_mock_script_pages(topic: str) -> list[dict[str, Any]]:
    """Public accessor for the mock multi-page script (used by two-phase mode)."""
    return _script_for(topic)


async def run_mock_agent(
    session_id: str,
    topic: str,
    seed_url: str,
    *,
    pages: list[dict[str, Any]] | None = None,
) -> None:
    """Emit a scripted but realistic sequence of events over ~60-90 seconds.

    If `pages` is provided, only that subset of the catalog is used (two-phase
    agent-on-each-URL demo). Otherwise the full topic script runs.
    """
    script: list[dict[str, Any]]
    if pages is not None:
        script = list(pages) if pages else []
    else:
        script = _script_for(topic)
    if not script:
        script = [MOCK_CATALOG["AI chip supply chain"][0]]
    entry_url = script[0]["url"]
    seq = 1

    # Prime the UI with a fake "live browser" placeholder. The AgentPanel
    # falls back to a static card when streamingUrl is None, so don't set
    # one here - let the user see the placeholder in mock mode.

    await publish_agent_status(
        session_id,
        AgentStatus(
            sessionId=session_id,
            state=AgentState.browsing,
            currentUrl=entry_url,
            pagesVisited=0,
            queueLength=len(script),
            lastAction="Mock: warming up the agent",
        ),
    )
    await publish_timeline_event(
        session_id,
        TimelineEvent(
            sessionId=session_id,
            sequenceNumber=seq,
            type=TimelineEventType.query_started,
            label=f"Research started: {topic}",
            url=entry_url,
        ),
    )
    await publish_crawl_log(
        session_id,
        CrawlLogEntry(
            sessionId=session_id,
            level=LogLevel.info,
            message=f"Opening seed URL {entry_url}",
        ),
    )

    # Expose a mock streaming URL so the AgentPanel iframe renders
    # something. Using a benign about:blank variant lets the UI show
    # its loading state rather than a broken iframe.
    await set_streaming_url(session_id, "about:blank")

    name_to_id: dict[str, str] = {}
    pages_visited = 0

    for page in script:
        pages_visited += 1
        url = page["url"]
        await mark_url_visited(session_id, url)

        await publish_agent_status(
            session_id,
            AgentStatus(
                sessionId=session_id,
                state=AgentState.browsing,
                currentUrl=url,
                pagesVisited=pages_visited,
                queueLength=len(script) - pages_visited,
                lastAction=f"Visiting {page['title']}",
            ),
        )
        seq += 1
        await publish_timeline_event(
            session_id,
            TimelineEvent(
                sessionId=session_id,
                sequenceNumber=seq,
                type=TimelineEventType.page_visited,
                label=page["title"][:40],
                url=url,
            ),
        )
        await publish_crawl_log(
            session_id,
            CrawlLogEntry(
                sessionId=session_id,
                level=LogLevel.info,
                message=f"Visiting {url}",
                url=url,
            ),
        )
        await asyncio.sleep(1.2)

        await publish_agent_status(
            session_id,
            AgentStatus(
                sessionId=session_id,
                state=AgentState.extracting,
                currentUrl=url,
                pagesVisited=pages_visited,
                queueLength=len(script) - pages_visited,
                lastAction=f"Extracting entities from {page['title']}",
            ),
        )

        for ent in page["entities"]:
            eid = entity_id(ent["type"], ent["name"])
            name_to_id[ent["name"]] = eid
            # Per-entity source includes that entity's rationale + excerpt so the
            # SourcePreviewDrawer has something meaningful to render.
            per_entity_source = SourceRef(
                url=url,
                title=page["title"],
                rationale=ent.get("rationale"),
                excerpt=ent.get("excerpt"),
            )
            entity = Entity(
                id=eid,
                name=ent["name"],
                type=ent["type"],
                claims=ent.get("claims", []),
                sources=[per_entity_source],
                confidence=0.82,
            )
            await publish_node(session_id, entity)
            seq += 1
            await publish_timeline_event(
                session_id,
                TimelineEvent(
                    sessionId=session_id,
                    sequenceNumber=seq,
                    type=TimelineEventType.entity_normalized,
                    label=f"Extracted {ent['name']}",
                    entityId=eid,
                    url=url,
                ),
            )
            await publish_crawl_log(
                session_id,
                CrawlLogEntry(
                    sessionId=session_id,
                    level=LogLevel.info,
                    message=f"Found {ent['type']} {ent['name']}",
                    url=url,
                ),
            )
            await asyncio.sleep(0.6)

        # Bare SourceRef (no rationale/excerpt) for edges and auto-created nodes.
        bare_source_ref = SourceRef(url=url, title=page["title"])

        for from_name, predicate, to_name in page["relationships"]:
            from_id = name_to_id.get(from_name) or entity_id("concept", from_name)
            to_id = name_to_id.get(to_name) or entity_id("concept", to_name)

            # Auto-create unseen targets so edges always resolve.
            for (name, nid) in ((from_name, from_id), (to_name, to_id)):
                if name not in name_to_id:
                    name_to_id[name] = nid
                    auto = Entity(
                        id=nid,
                        name=name,
                        type="concept",
                        sources=[bare_source_ref],
                        confidence=0.6,
                    )
                    await publish_node(session_id, auto)

            rid = relationship_id(from_id, to_id, predicate)
            await publish_edge(
                session_id,
                Relationship(
                    id=rid,
                    fromId=from_id,
                    toId=to_id,
                    predicate=predicate,
                    confidence=0.82,
                    sources=[bare_source_ref],
                ),
            )
            seq += 1
            await publish_timeline_event(
                session_id,
                TimelineEvent(
                    sessionId=session_id,
                    sequenceNumber=seq,
                    type=TimelineEventType.edge_created,
                    label=f"{from_name} -> {predicate} -> {to_name}",
                    relationshipId=rid,
                ),
            )
            await asyncio.sleep(0.4)

    await publish_agent_status(
        session_id,
        AgentStatus(
            sessionId=session_id,
            state=AgentState.done,
            currentUrl=entry_url,
            pagesVisited=pages_visited,
            queueLength=0,
            lastAction="Research complete",
        ),
    )
    seq += 1
    await publish_timeline_event(
        session_id,
        TimelineEvent(
            sessionId=session_id,
            sequenceNumber=seq,
            type=TimelineEventType.fact_extracted,
            label="Research complete",
        ),
    )
    session_obj = await load_session(session_id)
    if session_obj is not None and session_obj.status != SessionStatus.paused:
        session_obj.status = SessionStatus.complete
        await save_session(session_obj)
