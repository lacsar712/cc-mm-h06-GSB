from app.rules import classify


def test_classify_alarm():
    assert classify(1.0) == ("报警", "甲烷达到报警线")
    assert classify(1.4) == ("报警", "甲烷达到报警线")


def test_classify_normal():
    assert classify(0.35) == ("正常", "甲烷低于报警线")
    assert classify(0.99) == ("正常", "甲烷低于报警线")
