"""E2E personas. Product concepts, not test fixtures — imported by CI scripts
and by the E2E suite."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Persona:
    id: str
    tenant: str
    role: str
    email: str
    forbidden_tenant_data: tuple[str, ...] = ()


PERSONAS: tuple[Persona, ...] = (
    Persona("analyst_uk", "tenant-uk", "analyst", "analyst.uk@example.com",
            forbidden_tenant_data=("tenant-us", "tenant-eu", "tenant-apac")),
    Persona("analyst_us", "tenant-us", "analyst", "analyst.us@example.com",
            forbidden_tenant_data=("tenant-uk", "tenant-eu", "tenant-apac")),
    Persona("analyst_eu", "tenant-eu", "analyst", "analyst.eu@example.com",
            forbidden_tenant_data=("tenant-uk", "tenant-us", "tenant-apac")),
    Persona("analyst_mena", "tenant-mena", "analyst", "analyst.mena@example.com",
            forbidden_tenant_data=("tenant-uk", "tenant-us", "tenant-eu", "tenant-apac")),
    Persona("analyst_apac", "tenant-apac", "analyst", "analyst.apac@example.com",
            forbidden_tenant_data=("tenant-uk", "tenant-us", "tenant-eu")),
    Persona("manager_uk", "tenant-uk", "manager", "manager.uk@example.com",
            forbidden_tenant_data=("tenant-us", "tenant-eu", "tenant-apac")),
    Persona("auditor_readonly", "tenant-uk", "auditor", "auditor@example.com",
            forbidden_tenant_data=("tenant-us", "tenant-eu", "tenant-apac")),
)


def by_id(persona_id: str) -> Persona:
    for p in PERSONAS:
        if p.id == persona_id:
            return p
    raise KeyError(persona_id)