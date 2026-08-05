"""Knowledge graph unit tests."""

from __future__ import annotations

from knowledge_graph.engine import KnowledgeGraph


def test_news_and_filing_link_tickers() -> None:
    g = KnowledgeGraph()
    g.ingest_news(
        article_id="n1",
        title="NVIDIA AI demand surges",
        tickers=["NVDA", "MSFT"],
        sectors=["Technology"],
        countries=["US"],
        sentiment_score=0.6,
    )
    g.ingest_filing(
        filing_id="f1",
        title="NVIDIA earnings beat",
        ticker="NVDA",
        filing_type="earnings",
        impact_score=0.5,
    )
    neighbors = g.neighbors("ticker", "NVDA")
    assert any(n["node"]["node_type"] == "news" for n in neighbors)
    assert any(n["node"]["node_type"] == "filing" for n in neighbors)
    related = g.related_tickers("NVDA")
    assert any(r["ticker"] == "MSFT" for r in related)


def test_geo_impacts_channels() -> None:
    g = KnowledgeGraph()
    g.ingest_geo_event(
        event_id="g1",
        title="Oil shipping disruption",
        countries=["SA"],
        channels={"oil": 0.8, "shipping": 0.6},
    )
    impacts = g.neighbors("geo_event", "g1", relationship="IMPACTS")
    tickers = {i["node"]["external_key"] for i in impacts}
    assert "XOM" in tickers
    assert g.stats()["nodes"] >= 3
