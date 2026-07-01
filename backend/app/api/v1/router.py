"""Aggregate API v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    auth,
    bank_connections,
    budgets,
    categories,
    dashboard,
    exchange_rates,
    exports,
    goals,
    health,
    holdings,
    household,
    imports,
    institutions,
    reports,
    reserves,
    rules,
    scheduled_cashflows,
    transactions,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(budgets.router)
api_router.include_router(household.router)
api_router.include_router(institutions.router)
api_router.include_router(accounts.router)
api_router.include_router(bank_connections.router)
api_router.include_router(transactions.router)
api_router.include_router(categories.router)
api_router.include_router(rules.router)
api_router.include_router(imports.router)
api_router.include_router(scheduled_cashflows.router)
api_router.include_router(goals.router)
api_router.include_router(reserves.router)
api_router.include_router(holdings.router)
api_router.include_router(exchange_rates.router)
api_router.include_router(reports.router)
api_router.include_router(dashboard.router)
api_router.include_router(exports.router)
