import pytest

from utils import classify_source_tier


@pytest.mark.parametrize(
    "url",
    [
        "https://postgresql.org/docs/current/",
        "https://www.postgresql.org/docs/current/",
        "https://mongodb.com/docs/manual/",
        "https://docs.mongodb.com/manual/",
        "https://learn.microsoft.com/en-us/azure/",
        "https://docs.aws.amazon.com/AmazonRDS/latest/",
        "https://openai.com/index/engineering/",
        "https://platform.openai.com/docs/",
    ],
)
def test_official_vendor_domains_are_tier_two(url):
    tier, label = classify_source_tier(url)

    assert tier == 2
    assert "非独立验证" in label


@pytest.mark.parametrize(
    "url",
    [
        "https://unknown-blog.example/post",
        "https://mongodb.com.evil.example/docs/",
        "https://amazon.com.fake.example/docs/",
        "https://postgresql.org.attacker.example/docs/",
    ],
)
def test_unknown_and_lookalike_domains_remain_conservative(url):
    tier, label = classify_source_tier(url)

    assert tier == 3
    assert "未识别域名" in label


def test_existing_academic_tier_does_not_regress():
    assert classify_source_tier("https://arxiv.org/abs/1234.5678")[0] == 1


def test_existing_independent_tier_does_not_regress():
    assert classify_source_tier("https://artificialanalysis.ai/models")[0] == 2
