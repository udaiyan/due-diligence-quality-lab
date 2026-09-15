"""The tier-3 E2E matrix.

Six personas × three browsers × four tenants. Every test uses data-testid
selectors. Selector drift is caught by `ddql.ci.selector_sync`.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from ddql.persona import Persona


@pytest.mark.e2e
def test_investigation_run_completes(authed_page: Page, persona: Persona) -> None:
    authed_page.goto("/app/investigations/new")
    authed_page.get_by_test_id("query-input").fill("Northwind Holdings Ltd")
    authed_page.get_by_test_id("run-investigation").click()

    result = authed_page.get_by_test_id("investigation-result")
    expect(result).to_be_visible(timeout=60_000)

    claims = authed_page.get_by_test_id("claim")
    expect(claims.first).to_be_visible()
    for i in range(claims.count()):
        expect(claims.nth(i).get_by_test_id("citation")).to_have_count(
            re.compile(r"[1-9]\d*")
        )


@pytest.mark.e2e
def test_tenant_isolation(authed_page: Page, persona: Persona) -> None:
    authed_page.goto("/app/investigations")
    body = authed_page.content()
    for forbidden in persona.forbidden_tenant_data:
        assert forbidden not in body, (
            f"tenant leak: {persona.id} saw '{forbidden}' in the UI"
        )

    response = authed_page.request.get("/api/investigations?tenant=tenant-us")
    if persona.tenant != "tenant-us":
        assert response.status in (403, 404), (
            f"tenant leak: {persona.id} got {response.status} from tenant-us API"
        )


@pytest.mark.e2e
def test_auditor_is_readonly(authed_page: Page, persona: Persona) -> None:
    if persona.role != "auditor":
        pytest.skip("role-specific test")
    authed_page.goto("/app/investigations/new")
    expect(authed_page.get_by_test_id("run-investigation")).to_be_disabled()