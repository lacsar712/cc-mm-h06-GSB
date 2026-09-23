from fastapi.testclient import TestClient

from app.main import Reading, SessionLocal, app


def login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def db_levels() -> dict[str, str]:
    db = SessionLocal()
    try:
        return {row.site: row.level for row in db.query(Reading).all()}
    finally:
        db.close()


def find(items: list[dict], site: str) -> dict:
    return next(item for item in items if item["site"] == site)


def test_seed_rows_keep_verdict_in_db_and_list():
    """回风巷报警、东翼-12正常：落库状态与列表色必须与判定一致，无旁路字段。"""
    with TestClient(app) as client:
        token = login(client, "gasman", "gas123456")
        rows = client.get("/api/readings", headers={"Authorization": f"Bearer {token}"}).json()

    levels = db_levels()
    assert levels["回风巷"] == "报警"
    assert levels["东翼-12"] == "正常"

    alarm = find(rows, "回风巷")
    assert alarm["level"] == "报警"
    assert alarm["note"] == "甲烷达到报警线"
    assert alarm["css"] == "alarm"
    assert "bypass" not in alarm

    normal = find(rows, "东翼-12")
    assert normal["level"] == "正常"
    assert normal["note"] == "甲烷低于报警线"
    assert normal["css"] == "ok"
    assert "bypass" not in normal


def test_create_alarm_persists_and_pushes_alarm():
    """新上报报警：库里状态、HTTP 返回、WebSocket 推送都必须是报警红。"""
    with TestClient(app) as client:
        token = login(client, "gasman", "gas123456")
        headers = {"Authorization": f"Bearer {token}"}
        with client.websocket_connect("/ws/alerts") as ws:
            r = client.post(
                "/api/readings",
                headers=headers,
                json={"site": "西翼-07", "ch4_pct": 1.4},
            )
            pushed = ws.receive_json()

    assert r.status_code == 201
    body = r.json()
    for payload in (body, pushed):
        assert payload["site"] == "西翼-07"
        assert payload["level"] == "报警"
        assert payload["note"] == "甲烷达到报警线"
        assert payload["css"] == "alarm"
        assert "bypass" not in payload
    assert pushed["id"] == body["id"]

    assert db_levels()["西翼-07"] == "报警"

    with TestClient(app) as client:
        token = login(client, "viewer", "view123456")
        rows = client.get("/api/readings", headers={"Authorization": f"Bearer {token}"}).json()
    row = find(rows, "西翼-07")
    assert row["level"] == "报警"
    assert row["css"] == "alarm"


def test_create_normal_stays_normal():
    """新上报正常：不能被任何后处置误伤，库里与推送都保持正常绿。"""
    with TestClient(app) as client:
        token = login(client, "gasman", "gas123456")
        headers = {"Authorization": f"Bearer {token}"}
        with client.websocket_connect("/ws/alerts") as ws:
            r = client.post(
                "/api/readings",
                headers=headers,
                json={"site": "东翼-13", "ch4_pct": 0.32},
            )
            pushed = ws.receive_json()

    assert r.status_code == 201
    body = r.json()
    for payload in (body, pushed):
        assert payload["level"] == "正常"
        assert payload["note"] == "甲烷低于报警线"
        assert payload["css"] == "ok"
        assert "bypass" not in payload

    assert db_levels()["东翼-13"] == "正常"
