from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_node():
    payload = {
        "id": "test_node",
        "title": "Test Node",
        "year": 2026,
        "authors": ["Chris"],
        "summary": "Temporary test node",
        "tier": 2
    }
    r = client.post("/nodes", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "test_node"
    assert data["tier"] == 2


def test_create_edge():
    # create nodes first
    r_a = client.post("/nodes", json={
        "id": "edge_a",
        "title": "Edge A",
        "year": 2020,
        "authors": ["A"],
        "summary": "A",
        "tier": 2
    })
    assert r_a.status_code == 200

    r_b = client.post("/nodes", json={
        "id": "edge_b",
        "title": "Edge B",
        "year": 2021,
        "authors": ["B"],
        "summary": "B",
        "tier": 2
    })
    assert r_b.status_code == 200

    r = client.post("/edges", json={
        "type": "REFINES",
        "from_id": "edge_a",
        "to_id": "edge_b",
        "timestamp": 2021,
        "rationale": "Testing edge creation"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "REFINES"


def test_snapshot_filters_future_edges():
    # seeded edge everett1957 -> bohr_copenhagen timestamp=1957 should appear for year >= 1957
    r1 = client.get("/nodes/everett1957/neighborhood", params={"year": 1957})
    assert r1.status_code == 200
    edges_1957 = r1.json()["edges"]
    assert any(e["timestamp"] == 1957 for e in edges_1957)

    # create a future edge from everett to qbism at 2099
    r_new = client.post("/edges", json={
        "type": "RESONATES_WITH",
        "from_id": "everett1957",
        "to_id": "qbism",
        "timestamp": 2099,
        "rationale": "Future-only edge"
    })
    assert r_new.status_code == 200

    r2 = client.get("/nodes/everett1957/neighborhood", params={"year": 2025})
    assert r2.status_code == 200
    edges_2025 = r2.json()["edges"]
    assert all(e["timestamp"] <= 2025 for e in edges_2025)
    assert not any(e["timestamp"] == 2099 for e in edges_2025)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
