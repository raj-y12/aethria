from datetime import datetime, timedelta

from portfolio.feedback import FeedbackLoop


class _FakePortfolioStore:
    def __init__(self):
        self._metrics = []

    def get_all_decisions(self):
        now = datetime.now().isoformat()
        # Mix canonical + legacy decision labels to verify normalization.
        return [
            {
                "partner_agent_id": "partner_v1",
                "decision": "YES",
                "decided_at": now,
            },
            {
                "partner_agent_id": "partner_v1",
                "decision": "INVEST",
                "decided_at": now,
            },
            {
                "partner_agent_id": "partner_v1",
                "decision": "WATCH",
                "decided_at": now,
            },
            {
                "partner_agent_id": "partner_v1",
                "decision": "PASS",
                "decided_at": now,
            },
        ]

    def add_agent_metric(
        self,
        agent_id,
        agent_type,
        metric_name,
        metric_value,
        period_start,
        period_end,
        sample_size,
    ):
        self._metrics.append(
            {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "period_start": period_start,
                "period_end": period_end,
                "sample_size": sample_size,
            }
        )
        return f"metric-{len(self._metrics)}"


def test_partner_metrics_normalizes_legacy_decisions_without_crash():
    store = _FakePortfolioStore()
    feedback = FeedbackLoop(store)
    period_end = datetime.now()
    period_start = period_end - timedelta(days=1)

    metric_ids = feedback._calculate_partner_metrics(period_start, period_end)

    # Regression assertion: no NameError and exactly one metric written.
    assert len(metric_ids) == 1
    assert len(store._metrics) == 1
    metric = store._metrics[0]
    assert metric["metric_name"] == "acceptance_rate"
    # YES + INVEST(normalized to YES) => 2 / 4 = 0.5
    assert metric["metric_value"] == 0.5
