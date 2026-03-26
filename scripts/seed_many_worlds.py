#!/usr/bin/env python3
"""
scripts/seed_many_worlds.py

Populates the Rhizome graph with the canonical Everett 1957 → DeWitt 1970
Many-Worlds Interpretation arc, including supporting nodes for the full
intellectual lineage from 1925 to 2025.

Usage (with the backend running on localhost:8000):
    python scripts/seed_many_worlds.py [--base-url http://localhost:8000]

The script is idempotent — nodes that already exist are skipped.
"""

import argparse
import sys

try:
    import httpx
except ImportError:
    sys.exit("httpx is required: pip install httpx")

BASE_URL = "http://localhost:8000"

# ── Node definitions ──────────────────────────────────────────────────────────
NODES = [
    {
        "id": "heisenberg1925",
        "title": "Matrix Mechanics (Heisenberg 1925)",
        "year": 1925,
        "authors": ["Werner Heisenberg"],
        "summary": "First complete formulation of quantum mechanics using matrix algebra.",
        "tier": 1,
        "method_flavor": "Axiomatic",
        "raw_quote": "The present paper seeks to establish a basis for theoretical quantum mechanics founded exclusively upon relationships between quantities which in principle are observable.",
        "provenance": "Heisenberg, W. (1925). Über quantentheoretische Umdeutung kinematischer und mechanischer Beziehungen. Z. Phys. 33, 879–893.",
    },
    {
        "id": "schrodinger1926",
        "title": "Wave Mechanics (Schrödinger 1926)",
        "year": 1926,
        "authors": ["Erwin Schrödinger"],
        "summary": "Wave equation formulation of quantum mechanics; equivalent to matrix mechanics.",
        "tier": 1,
        "method_flavor": "Phenomenological",
        "raw_quote": "I have lately shown that the familiar quantum conditions can be replaced by another postulate.",
        "provenance": "Schrödinger, E. (1926). Quantisierung als Eigenwertproblem. Ann. Phys. 79, 361.",
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
        "id": "vonneumann1932",
        "title": "Von Neumann Measurement Theory (1932)",
        "year": 1932,
        "authors": ["John von Neumann"],
        "summary": "Formalises wavefunction collapse as a projection postulate.",
        "tier": 1,
        "method_flavor": "Axiomatic",
    },
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
        "id": "dewitt1970",
        "title": "Many-Worlds Revival (DeWitt 1970)",
        "year": 1970,
        "authors": ["Bryce DeWitt"],
        "summary": "Coins 'many-worlds interpretation'; resurrects and popularises Everett's thesis.",
        "tier": 1,
        "method_flavor": "Axiomatic",
        "raw_quote": "The universe is constantly splitting into a stupendous number of branches.",
        "provenance": "DeWitt, B. S. (1970). Quantum Mechanics and Reality. Physics Today, 23(9), 30–35.",
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
        "id": "deutsch1985",
        "title": "Quantum Computation (Deutsch 1985)",
        "year": 1985,
        "authors": ["David Deutsch"],
        "summary": "Proposes quantum Turing machine using MWI as foundational justification.",
        "tier": 1,
        "method_flavor": "Axiomatic",
    },
    {
        "id": "zurek2003",
        "title": "Quantum Darwinism (Zurek 2003)",
        "year": 2003,
        "authors": ["Wojciech Zurek"],
        "summary": "Explains how classical reality emerges from quantum redundancy in environments.",
        "tier": 2,
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
    {
        "id": "rovelli_rqm",
        "title": "Relational Quantum Mechanics (Rovelli 1996)",
        "year": 1996,
        "authors": ["Carlo Rovelli"],
        "summary": "Quantum states are relative to observers; no collapse, no many worlds.",
        "tier": 2,
        "method_flavor": "Phenomenological",
    },
]

# ── Edge definitions ──────────────────────────────────────────────────────────
EDGES = [
    # Founding arc
    {"type": "PROPOSES",  "from_id": "heisenberg1925", "to_id": "schrodinger1926",  "timestamp": 1926, "rationale": "Wave mechanics developed as alternative to matrix mechanics."},
    {"type": "PROPOSES",  "from_id": "schrodinger1926", "to_id": "bohr_copenhagen", "timestamp": 1928, "rationale": "Copenhagen crystallises from the two formalisms."},
    {"type": "REFINES",   "from_id": "vonneumann1932",  "to_id": "bohr_copenhagen", "timestamp": 1932, "rationale": "Von Neumann formalises collapse within the Copenhagen framework."},

    # Everett arc — the core zombie resurrection
    {"type": "CONTESTS",  "from_id": "everett1957",    "to_id": "bohr_copenhagen", "timestamp": 1957, "rationale": "Everett eliminates collapse; directly contests Copenhagen measurement axiom."},
    {"type": "CONTESTS",  "from_id": "everett1957",    "to_id": "vonneumann1932",  "timestamp": 1957, "rationale": "Relative-state formulation bypasses the projection postulate."},
    # 13-year dormancy → resurrection by DeWitt
    {"type": "RESURRECTS","from_id": "dewitt1970",     "to_id": "everett1957",     "timestamp": 1970, "rationale": "DeWitt coins 'many-worlds' and propels Everett's fringe thesis into mainstream."},

    # Decoherence thread
    {"type": "REFINES",   "from_id": "decoherence",    "to_id": "everett1957",     "timestamp": 1970, "rationale": "Decoherence grounds branch-selection without collapse."},
    {"type": "REFINES",   "from_id": "zurek2003",       "to_id": "decoherence",     "timestamp": 2003, "rationale": "Quantum Darwinism extends decoherence to explain classical objectivity."},

    # Bell & computation
    {"type": "EXTENDS",   "from_id": "bell1964",        "to_id": "bohr_copenhagen", "timestamp": 1964, "rationale": "Bell sharpens nonlocality/realism tensions within Copenhagen."},
    {"type": "RESONATES_WITH", "from_id": "deutsch1985","to_id": "everett1957",     "timestamp": 1985, "rationale": "Deutsch grounds quantum computation in MWI parallel worlds."},

    # Rival interpretations contesting MWI
    {"type": "CONTESTS",  "from_id": "qbism",           "to_id": "everett1957",     "timestamp": 2010, "rationale": "QBism rejects ontic multiverse; states are epistemic."},
    {"type": "CONTESTS",  "from_id": "rovelli_rqm",     "to_id": "everett1957",     "timestamp": 1996, "rationale": "RQM achieves observer-relativity without branching universes."},
    {"type": "RESONATES_WITH", "from_id": "rovelli_rqm","to_id": "everett1957",     "timestamp": 1996, "rationale": "Both treat quantum states as relative; different ontologies."},
]


def post(client: "httpx.Client", path: str, payload: dict) -> dict | None:
    r = client.post(path, json=payload)
    if r.status_code in (200, 201):
        return r.json()
    if r.status_code == 400 and "already exists" in r.text:
        print(f"  ↩  SKIP (already exists): {payload.get('id', payload.get('from_id','?'))}")
        return None
    print(f"  ✗  ERROR {r.status_code}: {r.text}")
    return None


def main(base_url: str) -> None:
    print(f"\n🌿 Project Rhizome — MWI seed script\n   Target: {base_url}\n")

    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        # Health check
        try:
            r = client.get("/health")
            r.raise_for_status()
        except Exception as exc:
            sys.exit(f"✗ Backend not reachable at {base_url}: {exc}")

        print("── Nodes ──────────────────────────────────────────────────")
        for node in NODES:
            result = post(client, "/graph/nodes", node)
            if result:
                print(f"  ✓ {result['id']}  [{result.get('method_flavor', '—')}]")

        print("\n── Edges ──────────────────────────────────────────────────")
        for edge in EDGES:
            result = post(client, "/graph/edges", edge)
            if result:
                print(f"  ✓ {edge['from_id']} --[{edge['type']}]--> {edge['to_id']}")

    print("\n✅ Seed complete.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the Rhizome MWI graph.")
    parser.add_argument("--base-url", default=BASE_URL, help="Backend base URL")
    args = parser.parse_args()
    main(args.base_url)
