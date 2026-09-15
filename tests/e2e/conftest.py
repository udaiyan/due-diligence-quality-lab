"""E2E fixtures: personas, tenants, browsers.

Personas differ in role, tenant, and the data they're entitled to see.
Multi-tenant isolation is a correctness property, tested at every tier.
"""

from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect

from ddql.persona import PERSONAS, Persona


@pytest.fixture(params=PERSONAS, ids=[p.id for p in PERSONAS])
def persona(request: pytest.FixtureRequest) -> Persona:
    return request.param


@pytest.fixture
def authed_page(page: Page, persona: Persona, base_url: str) -> Page:
    state_dir = os.environ.get("DDQL_AUTH_STATE_DIR")
    if state_dir:
        state_file = f"{state_dir}/{persona.id}.json"
        if os.path.exists(state_file):
            page.context.storage_state(path=state_file)
        else:
            _login(page, base_url, persona)
            page.context.storage_state(path=state_file)
    else:
        _login(page, base_url, persona)

    expect(page.get_by_test_id("tenant-badge")).to_have_text(persona.tenant)
    return page


def _login(page: Page, base_url: str, persona: Persona) -> None:
    page.goto(f"{base_url}/login")
    page.get_by_label("Email").fill(persona.email)
    page.get_by_label("Password").fill(os.environ["DDQL_TEST_PASSWORD"])
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(f"{base_url}/app/**")