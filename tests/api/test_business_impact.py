"""Automated tests for incident business impact, revenue at risk, and SLA credit calculations."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings


def test_subscribers_include_plan_price(client: TestClient) -> None:
    """GET /api/v1/subscribers returns plan_price for every subscriber."""
    resp = client.get("/api/v1/subscribers")
    assert resp.status_code == 200
    data = resp.json()
    assert "subscribers" in data
    assert len(data["subscribers"]) > 0
    for sub in data["subscribers"]:
        assert "plan_price" in sub
        assert isinstance(sub["plan_price"], (int, float))
        assert sub["plan_price"] >= 0.0


def test_business_impact_demo_incident(client: TestClient) -> None:
    """GET /api/v1/incidents/{id}/business-impact returns correct revenue at risk and SLA credits."""
    resp = client.get("/api/v1/incidents/incident-demo-001/business-impact")
    assert resp.status_code == 200
    data = resp.json()

    assert data["incident_id"] == "incident-demo-001"
    assert data["status"] in ("open", "closed")
    assert "affected_subscribers" in data
    assert data["affected_count"] == len(data["affected_subscribers"])
    assert data["monthly_revenue_at_risk"] >= 0.0
    assert data["revenue_at_risk"] == data["monthly_revenue_at_risk"]
    assert data["outage_duration_seconds"] >= 0.0
    assert isinstance(data["outage_duration_formatted"], str)
    assert data["sla_credit_rate_per_hour"] == settings.sla_credit_rate_per_hour
    assert data["estimated_sla_credit_owed"] >= 0.0
    assert isinstance(data["households_by_village"], dict)

    # Check each subscriber has plan_price and village
    for s in data["affected_subscribers"]:
        assert "plan_price" in s
        assert "village" in s
        assert s["plan_price"] >= 0.0


def test_business_impact_lab_scenario(client: TestClient) -> None:
    """Running degrade_link scenario generates incident and computes business impact accurately."""
    # 1. Trigger L3 degradation
    lab_resp = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "degrade_link",
            "target_link_id": "L3",
            "severity": "high",
        },
    )
    assert lab_resp.status_code == 200
    inc_id = lab_resp.json()["incident_id"]
    assert inc_id is not None

    # 2. Query business impact
    resp = client.get(f"/api/v1/incidents/{inc_id}/business-impact")
    assert resp.status_code == 200
    data = resp.json()

    assert data["incident_id"] == inc_id
    assert data["affected_count"] > 0
    assert len(data["affected_subscribers"]) == data["affected_count"]

    # Verify monthly revenue at risk matches sum of individual plan prices
    expected_mrr = sum(s["plan_price"] for s in data["affected_subscribers"])
    assert round(data["monthly_revenue_at_risk"], 2) == round(expected_mrr, 2)

    # Verify households by village counts sum to affected_count
    village_sum = sum(data["households_by_village"].values())
    assert village_sum == data["affected_count"]


def test_business_impact_sla_rate_config(client: TestClient) -> None:
    """Estimated SLA credit scales with configured rate."""
    orig_rate = settings.sla_credit_rate_per_hour
    try:
        settings.sla_credit_rate_per_hour = 0.05
        resp = client.get("/api/v1/incidents/incident-demo-001/business-impact")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sla_credit_rate_per_hour"] == 0.05
    finally:
        settings.sla_credit_rate_per_hour = orig_rate


def test_business_impact_not_found(client: TestClient) -> None:
    """Non-existent incident returns 404."""
    resp = client.get("/api/v1/incidents/incident-nonexistent-9999/business-impact")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_business_impact_unavailable_adapter(client: TestClient) -> None:
    """When dependency adapter is unavailable, endpoint returns HTTP 503."""
    orig_adapter = settings.dependency_adapter
    try:
        settings.dependency_adapter = "unavailable"
        resp = client.get("/api/v1/incidents/incident-demo-001/business-impact")
        assert resp.status_code == 503
        assert "unavailable" in resp.json()["detail"].lower()
    finally:
        settings.dependency_adapter = orig_adapter
