from pathlib import Path


def test_evaluation_runs_have_immutable_judgment_audit_column():
    sql = Path(__file__).parents[2].joinpath("supabase/migrations/20260812000002_evaluation_judgment_audit.sql").read_text().lower()
    assert "alter table public.evaluation_runs" in sql
    assert "judgment_audit jsonb" in sql
    assert "evaluation_runs_immutable" in sql


def test_judgment_audit_is_an_optional_evaluation_repository_input():
    from inspect import signature
    from investment_analysis.repository import InvestmentAnalysisRepository

    assert "judgment_audit" in signature(InvestmentAnalysisRepository._publish).parameters
