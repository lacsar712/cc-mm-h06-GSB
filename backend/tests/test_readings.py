"""报警/正常双路径测试。

覆盖四层结论必须一致，禁止报警被旁路刷成正常：
判定 -> 落库行 -> 列表行(含色) -> WebSocket 推送文案。
正常笔（含种子数据东翼-12）同样验证，防止反向误伤。
"""
import pytest
from fastapi.testclient import TestClient

from app.main import Reading, SessionLocal, app
from app.rules import classify


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def token(client):
    def _login(username, password):
        r = client.post("/api/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200
        return r.json()["access_token"]

    return _login


def db_row(reading_id: int) -> Reading:
    db = SessionLocal()
    try:
        return db.get(Reading, reading_id)
    finally:
        db.close()


# ---------- 判定层 ----------

@pytest.mark.parametrize(
    "ch4,level",
    [(1.0, "报警"), (1.4, "报警"), (0.99, "正常"), (0.35, "正常")],
)
def test_classify(ch4, level):
    got_level, got_note = classify(ch4)
    assert got_level == level
    assert got_note  # 两种结论都必须带说明文案


# ---------- 种子数据：东翼正常、回风巷报警，互不误伤 ----------

def test_seed_rows_keep_true_levels(client, token):
    auth = {"Authorization": f"Bearer {token('viewer', 'view123456')}"}
    rows = client.get("/api/readings", headers=auth).json()
    by_site = {r["site"]: r for r in rows}

    east = by_site["东翼-12"]
    assert east["level"] == "正常"
    assert east["css"] == "ok"

    ret = by_site["回风巷"]
    assert ret["level"] == "报警"
    assert ret["css"] == "alarm"


# ---------- 报警笔：落库 / 列表 / 推送三处都是报警 ----------

def test_alarm_reading_stays_alarm_everywhere(client, token):
    auth = {"Authorization": f"Bearer {token('gasman', 'gas123456')}"}

    with client.websocket_connect("/ws/alerts") as ws:
        r = client.post("/api/readings", headers=auth, json={"site": "西翼-7", "ch4_pct": 1.25})
        assert r.status_code == 201
        pushed = ws.receive_json()

    body = r.json()
    # 接口返回
    assert body["level"] == "报警"
    assert body["css"] == "alarm"
    assert body["note"] == "甲烷达到报警线"

    # 落库：不允许被后置刷成正常
    row = db_row(body["id"])
    assert row.level == "报警"
    assert row.note == "甲烷达到报警线"

    # 列表：状态与色
    listed = [x for x in client.get("/api/readings", headers=auth).json() if x["id"] == body["id"]][0]
    assert listed["level"] == "报警"
    assert listed["css"] == "alarm"

    # WebSocket 推送文案
    assert pushed["id"] == body["id"]
    assert pushed["level"] == "报警"
    assert pushed["css"] == "alarm"
    assert pushed["note"] == "甲烷达到报警线"


# ---------- 正常笔：不能被反向误伤成报警 ----------

def test_normal_reading_stays_normal_everywhere(client, token):
    auth = {"Authorization": f"Bearer {token('gasman', 'gas123456')}"}

    with client.websocket_connect("/ws/alerts") as ws:
        r = client.post("/api/readings", headers=auth, json={"site": "东翼-18", "ch4_pct": 0.2})
        assert r.status_code == 201
        pushed = ws.receive_json()

    body = r.json()
    assert body["level"] == "正常"
    assert body["css"] == "ok"
    assert body["note"] == "甲烷低于报警线"

    row = db_row(body["id"])
    assert row.level == "正常"
    assert row.note == "甲烷低于报警线"

    listed = [x for x in client.get("/api/readings", headers=auth).json() if x["id"] == body["id"]][0]
    assert listed["level"] == "正常"
    assert listed["css"] == "ok"

    assert pushed["level"] == "正常"
    assert pushed["css"] == "ok"
    assert pushed["note"] == "甲烷低于报警线"
