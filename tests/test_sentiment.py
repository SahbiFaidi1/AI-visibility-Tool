from aivis.sentiment import parse_labels, sentiment_score


def test_parse_labels_tolerates_noise_and_case():
    raw = 'Sure! {"tesla": "Positive", "BMW": "negative", "Unknown": "positive", "Kia": "meh"}'
    assert parse_labels(raw, ["Tesla", "BMW", "Kia"]) == {"Tesla": "positive", "BMW": "negative"}


def test_parse_labels_bad_json():
    assert parse_labels("no json here", ["Tesla"]) == {}
    assert parse_labels(None, ["Tesla"]) == {}


def test_sentiment_score():
    assert sentiment_score(["positive", "positive"]) == 100
    assert sentiment_score(["neutral"]) == 50
    assert sentiment_score(["negative", "positive"]) == 50
    assert sentiment_score([]) is None
