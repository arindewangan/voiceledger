"""Tests for the brain: offline categorizer + offline insights."""

from server.brain import Brain, offline_categorize


def test_offline_categorizer_cases():
    assert offline_categorize("groceries at BigBasket") == "groceries"
    assert offline_categorize("Swiggy dinner order") == "dining"
    assert offline_categorize("Uber cab to airport") == "transport"
    assert offline_categorize("electricity bill") == "utilities"
    assert offline_categorize("Netflix subscription") == "entertainment"
    assert offline_categorize("Apollo pharmacy") == "health"
    assert offline_categorize("Udemy course") == "education"
    assert offline_categorize("OYO hotel booking") == "travel"
    assert offline_categorize("Myntra shoes") == "shopping"
    assert offline_categorize("some random thing xyz") == "other"
    assert offline_categorize("") == "other"


def test_categorize_falls_back_offline_when_no_model(brain: Brain):
    category, source = brain.categorize("Zomato lunch", 350)
    assert category == "dining"
    assert source == "offline"


def test_insights_empty_ledger(brain: Brain):
    text, source = brain.insights(
        {"total_expense": 0, "by_category": {}}, []
    )
    assert source == "offline"
    assert "haven't logged" in text


def test_insights_within_budget(brain: Brain):
    text, source = brain.insights(
        {"total_expense": 5200, "by_category": {"groceries": 3000, "dining": 2200}},
        [{"category": "dining", "budget": 5000, "spent": 2200,
          "remaining": 2800, "over": False, "pct": 44.0}],
    )
    assert source == "offline"
    assert "5,200" in text or "5200" in text
    assert "within" in text


def test_insights_over_budget(brain: Brain):
    text, _ = brain.insights(
        {"total_expense": 6300, "by_category": {"dining": 4200, "groceries": 2100}},
        [{"category": "dining", "budget": 3000, "spent": 4200,
          "remaining": -1200, "over": True, "pct": 140.0}],
    )
    assert "over budget" in text
    assert "dining" in text


def test_bedrock_unavailable_without_model(brain: Brain):
    assert brain.bedrock_available is False
