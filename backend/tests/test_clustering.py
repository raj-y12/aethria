from analytics.clustering import ClusterAnalyzer


def test_cluster_analysis_ignores_missing_review_scores(monkeypatch):
    analyzer = ClusterAnalyzer(user_id="test-user")
    monkeypatch.setattr(analyzer, "_write", lambda data: None)

    result = analyzer.analyze(
        [
            {
                "startup_id": "startup-1",
                "scout_info": {"sector": "Fintech"},
                "review_info": {
                    "market_score": None,
                    "product_score": None,
                    "technical_score": None,
                    "execution_score": None,
                },
            }
        ]
    )

    assert result["by_sector"]["Fintech"]["avg_review_score"] is None


def test_cluster_analysis_averages_available_review_scores(monkeypatch):
    analyzer = ClusterAnalyzer(user_id="test-user")
    monkeypatch.setattr(analyzer, "_write", lambda data: None)

    result = analyzer.analyze(
        [
            {
                "startup_id": "startup-1",
                "scout_info": {"sector": "Fintech"},
                "review_info": {
                    "market_score": 8,
                    "product_score": None,
                    "technical_score": 6,
                    "execution_score": None,
                },
            }
        ]
    )

    assert result["by_sector"]["Fintech"]["avg_review_score"] == 7.0


def test_cluster_analysis_ignores_null_confidence_scores(monkeypatch):
    analyzer = ClusterAnalyzer(user_id="test-user")
    monkeypatch.setattr(analyzer, "_write", lambda data: None)

    result = analyzer.analyze(
        [
            {
                "startup_id": "startup-1",
                "scout_info": {"sector": "Fintech", "confidence_score": None},
            }
        ]
    )

    assert result["by_sector"]["Fintech"]["avg_confidence"] == 0
