from aivis.analysis import MentionDetector, classify_domain, dedupe_citations, domain_of, extract_inline_urls
from aivis.models import Brand, Citation

BRANDS = [
    Brand("Tesla", aliases=["Tesla Motors"], domains=["tesla.com"], is_target=True),
    Brand("Mercedes-Benz", aliases=["Mercedes", "Mercedes Benz"], domains=["mercedes-benz.com"]),
    Brand("Kia", domains=["kia.com"]),
    Brand("VW", aliases=["Volkswagen"], domains=["vw.com"]),
]


def test_detects_whole_words_and_positions():
    text = "For value, Kia is hard to beat. Tesla leads on software, while Mercedes Benz feels premium. Nokia is a phone."
    m = {x.brand: x for x in MentionDetector(BRANDS).detect(text)}
    assert set(m) == {"Kia", "Tesla", "Mercedes-Benz"}
    assert m["Kia"].position == 1 and m["Tesla"].position == 2 and m["Mercedes-Benz"].position == 3
    assert m["Kia"].count == 1  # "Nokia" must not count


def test_alias_and_hyphen_variants_count_once_per_brand():
    text = "Mercedes-Benz, Mercedes and Mercedes Benz are the same maker. Volkswagen (VW) too."
    m = {x.brand: x for x in MentionDetector(BRANDS).detect(text)}
    assert m["Mercedes-Benz"].count == 3
    assert m["VW"].count == 2


def test_case_insensitive_and_markdown_bold():
    text = "1. **tesla** is first.\n2. **KIA** second."
    ms = MentionDetector(BRANDS).detect(text)
    assert [x.brand for x in ms] == ["Tesla", "Kia"]


def test_domain_helpers():
    assert domain_of("https://www.Tesla.com/models?x=1") == "tesla.com"
    assert classify_domain("shop.tesla.com", BRANDS) == "Tesla"
    assert classify_domain("edmunds.com", BRANDS) == "other"


def test_inline_urls_and_dedupe():
    text = "See https://www.edmunds.com/best-evs/ and (https://tesla.com/model3)."
    inline = extract_inline_urls(text)
    assert {c.domain for c in inline} == {"edmunds.com", "tesla.com"}
    merged = dedupe_citations([Citation("https://tesla.com/model3", "tesla.com", kind="cited"), *inline])
    kinds = {c.url.rstrip("/"): c.kind for c in merged}
    assert kinds["https://tesla.com/model3"] == "cited"
    assert len(merged) == 2
