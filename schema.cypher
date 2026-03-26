// ──────────────────────────────────────────────────────────────────────────────
// schema.cypher — Project Rhizome Neo4j 5.20 Schema
//
// Run against a fresh database:
//   cat schema.cypher | docker exec -i rhizome-neo4j cypher-shell -u neo4j -p rhizome-secret
//
// Or via Neo4j Browser at http://localhost:7474
// ──────────────────────────────────────────────────────────────────────────────

// ── Constraints ───────────────────────────────────────────────────────────────

// Each Idea node must have a unique ID (enforces immutability of the key)
CREATE CONSTRAINT idea_id_unique IF NOT EXISTS
  FOR (i:Idea) REQUIRE i.id IS UNIQUE;

// Each Idea must carry a source_hash (provenance fingerprint)
CREATE CONSTRAINT idea_source_hash_exists IF NOT EXISTS
  FOR (i:Idea) REQUIRE i.source_hash IS NOT NULL;

// ── Standard Indexes ──────────────────────────────────────────────────────────

// Year index for fast time-lapse snapshot queries
CREATE INDEX idea_year IF NOT EXISTS
  FOR (i:Idea) ON (i.year);

// Tier index for credibility filtering
CREATE INDEX idea_tier IF NOT EXISTS
  FOR (i:Idea) ON (i.tier);

// Method flavor index for Axiomatic / Phenomenological filtering
CREATE INDEX idea_method_flavor IF NOT EXISTS
  FOR (i:Idea) ON (i.method_flavor);

// Edge timestamp index (enables efficient temporal snapshot queries)
CREATE INDEX edge_timestamp IF NOT EXISTS
  FOR ()-[r:PROPOSES|CONTESTS|REFUTES|CRITIQUES|REFINES|EXTENDS|RESURRECTS|ABANDONS|SUPERSEDES|RESONATES_WITH]-()
  ON (r.timestamp);

// ── Vector Index (Neo4j 5.11+ / APOC) ────────────────────────────────────────
// Stores 1536-dimensional embeddings (OpenAI text-embedding-3-small dimensions).
// Used by Engine 4 (Discovery) for semantic resonance search.

CREATE VECTOR INDEX idea_embedding IF NOT EXISTS
  FOR (i:Idea) ON (i.embedding)
  OPTIONS {
    indexConfig: {
      `vector.dimensions`: 1536,
      `vector.similarity_function`: 'cosine'
    }
  };

// ── Full-text index ───────────────────────────────────────────────────────────
// Enables fast keyword search across title, summary, and raw_quote fields.

CREATE FULLTEXT INDEX idea_text_search IF NOT EXISTS
  FOR (i:Idea) ON EACH [i.title, i.summary, i.raw_quote];
