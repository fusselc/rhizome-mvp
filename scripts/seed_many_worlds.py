#!/usr/bin/env python3
"""
scripts/seed_many_worlds.py

Async script that ingests the canonical Everett 1957 → DeWitt 1970
Many-Worlds Interpretation arc directly into the Neo4j database using
the project's Pydantic models (NodeCreate / EdgeCreate).

Usage:
    python scripts/seed_many_worlds.py

Environment variables (with defaults):
    NEO4J_URI      bolt://localhost:7687
    NEO4J_USER     neo4j
    NEO4J_PASSWORD rhizome-secret

The script is idempotent — nodes and edges are upserted via MERGE so
re-running it is safe.
"""

import asyncio
import json
import os
import sys

try:
    from neo4j import AsyncGraphDatabase
except ImportError:
    sys.exit("neo4j driver is required: pip install neo4j>=5.20")

# Allow running from the repo root or from the scripts/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

try:
    from app.models import EdgeCreate, NodeCreate
except ModuleNotFoundError:
    sys.exit(
        "Could not import app.models. Run this script from the repo root:\n"
        "  python scripts/seed_many_worlds.py"
    )

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "rhizome-secret")

# ── Node definitions ──────────────────────────────────────────────────────────
_RAW_NODES = [
    {
        "id": "everett1957",
        "title": "Relative State Formulation (Everett 1957)",
        "year": 1957,
        "authors": ["Hugh Everett III"],
        "summary": "Introduces relative state / many-worlds framework; removes collapse postulate.",
        "tier": 1,
        "method_flavor": "Axiomatic",
        "raw_quote": "I wish to propose a new formulation of quantum mechanics which is built upon the concept of relative state.",
        "provenance": "Everett, H. (1957). 'Relative State' Formulation of Quantum Mechanics. Reviews of Modern Physics, 29(3), 454–462.",
    },
    {
        "id": "bohr_copenhagen",
        "title": "Copenhagen Interpretation (Bohr)",
        "year": 1928,
        "authors": ["Niels Bohr"],
        "summary": "Measurement-centric interpretation emphasizing classical description.",
        "tier": 1,
        "method_flavor": "Phenomenological",
    },
    {
        "id": "dewitt1970",
        "title": "Many-Worlds Revival (DeWitt 1970)",
        "year": 1970,
        "authors": ["Bryce DeWitt"],
        "summary": "Coins 'many-worlds interpretation'; resurrects and popularises Everett's thesis.",
        "tier": 1,
        "method_flavor": "Axiomatic",
        "raw_quote": "The universe is constantly splitting into a stupendous number of branches.",
        "provenance": "DeWitt, B. S. (1970). Quantum Mechanics and Reality. Physics Today, 23(9), 30-35.",
    },
    {
        "id": "bell1964",
        "title": "Bell's Theorem (1964)",
        "year": 1964,
        "authors": ["John S. Bell"],
        "summary": "Shows constraints on local hidden variable theories; sharpens non-locality.",
        "tier": 1,
        "method_flavor": "Axiomatic",
    },
    {
        "id": "decoherence",
        "title": "Decoherence Program",
        "year": 1970,
        "authors": ["H. Dieter Zeh", "Wojciech Zurek"],
        "summary": "Explains environment-induced suppression of interference; grounds MWI branches.",
        "tier": 1,
        "method_flavor": "Axiomatic",
    },
    {
        "id": "qbism",
        "title": "QBism",
        "year": 2010,
        "authors": ["C. A. Fuchs", "R. Schack"],
        "summary": "Interprets quantum states as personalist Bayesian degrees of belief; rejects MWI.",
        "tier": 2,
        "method_flavor": "Phenomenological",
    },
]

# ── Edge definitions ──────────────────────────────────────────────────────────
_RAW_EDGES = [
    {
        "type": "CONTESTS",
        "from_id": "everett1957",
        "to_id": "bohr_copenhagen",
        "timestamp": 1957,
        "rationale": "Everett eliminates collapse; directly contests Copenhagen measurement axiom.",
        "source_flavor": "Axiomatic",
        "target_flavor": "Phenomenological",
    },
    {
        "type": "RESURRECTS",
        "from_id": "dewitt1970",
        "to_id": "everett1957",
        "timestamp": 1970,
        "rationale": "DeWitt coins 'many-worlds' and propels Everett's fringe thesis into mainstream.",
        "source_flavor": "Axiomatic",
        "target_flavor": "Axiomatic",
    },
    {
        "type": "REFINES",
        "from_id": "decoherence",
        "to_id": "everett1957",
        "timestamp": 1970,
        "rationale": "Decoherence grounds branch-selection without collapse.",
        "source_flavor": "Axiomatic",
        "target_flavor": "Axiomatic",
    },
    {
        "type": "EXTENDS",
        "from_id": "bell1964",
        "to_id": "bohr_copenhagen",
        "timestamp": 1964,
        "rationale": "Bell sharpens nonlocality/realism tensions within Copenhagen.",
        "source_flavor": "Axiomatic",
        "target_flavor": "Phenomenological",
    },
    {
        "type": "CONTESTS",
        "from_id": "qbism",
        "to_id": "everett1957",
        "timestamp": 2010,
        "rationale": "QBism rejects ontic multiverse; states are epistemic.",
        "source_flavor": "Phenomenological",
        "target_flavor": "Axiomatic",
    },
]


async def seed(driver) -> None:
    print("\n🌿 Project Rhizome — async Neo4j seed script")
    print(f"   Target: {NEO4J_URI}\n")

    # Validate models first (raises on bad data)
    nodes = [NodeCreate(**raw) for raw in _RAW_NODES]
    edges = [EdgeCreate(**raw) for raw in _RAW_EDGES]

    async with driver.session() as session:
        print("── Nodes ──────────────────────────────────────────────────")
        for node in nodes:
            data = node.model_dump()
            data["authors"] = json.dumps(data["authors"])
            data["credibility_history"] = json.dumps(data["credibility_history"])
            await session.run(
                """
                MERGE (i:Idea {id: $id})
                ON CREATE SET
                    i.title               = $title,
                    i.year                = $year,
                    i.authors             = $authors,
                    i.summary             = $summary,
                    i.tier                = $tier,
                    i.raw_quote           = $raw_quote,
                    i.provenance          = $provenance,
                    i.source_hash         = $source_hash,
                    i.method_flavor       = $method_flavor,
                    i.credibility_history = $credibility_history
                """,
                **data,
            )
            print(f"  ✓ {node.id}  [{node.method_flavor or '-'}]")

        print("\n── Edges ──────────────────────────────────────────────────")
        for edge in edges:
            await session.run(
                """
                MATCH (a:Idea {id: $from_id}), (b:Idea {id: $to_id})
                MERGE (a)-[r:EDGE {from_id: $from_id, to_id: $to_id,
                                   type: $type, timestamp: $timestamp}]->(b)
                ON CREATE SET
                    r.rationale           = $rationale,
                    r.tension             = $tension,
                    r.method_flavor_delta = $method_flavor_delta
                """,
                from_id=edge.from_id,
                to_id=edge.to_id,
                type=edge.type.value,
                timestamp=edge.timestamp,
                rationale=edge.rationale,
                tension=edge.tension,
                method_flavor_delta=edge.method_flavor_delta,
            )
            print(f"  ✓ {edge.from_id} --[{edge.type.value}]--> {edge.to_id}")

    print("\n✅ Seed complete.\n")


async def main() -> None:
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        await seed(driver)
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
