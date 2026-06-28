from app.api.routers import health as health_router


def test_health_db_returns_runtime_database_profile(api_client, monkeypatch):
    monkeypatch.setattr(
        health_router,
        "get_database_runtime_profile",
        lambda _db: {
            "mode": "sqlite-fallback",
            "preferred_backend": "oceanbase",
            "active_dialect": "sqlite",
            "using_sqlite_fallback": True,
            "preferred_database_url_masked": "mysql+pymysql://root:***@127.0.0.1:2881/supply_chain?charset=utf8mb4",
            "active_database_url_masked": "sqlite:///./schema/supply_chain.db",
        },
    )

    response = api_client.get("/api/health/db")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "ok"
    assert body["data"]["status"] == "connected"
    assert body["data"]["dialect"] == "sqlite"
    assert body["data"]["database_url_masked"] == "sqlite:///./schema/supply_chain.db"
    assert body["data"]["preferred_database_url_masked"] == "mysql+pymysql://root:***@127.0.0.1:2881/supply_chain?charset=utf8mb4"
    assert body["data"]["mode"] == "sqlite-fallback"
    assert body["data"]["preferred_backend"] == "oceanbase"
