"""Enumerated value sets used across models and schemas.

Stored as plain strings in the database (avoids brittle PostgreSQL enum
migrations) but validated at the Python/schema layer.
"""

from __future__ import annotations

from enum import StrEnum


class Country(StrEnum):
    IE = "IE"
    PK = "PK"
    OTHER = "OTHER"


class Currency(StrEnum):
    EUR = "EUR"
    PKR = "PKR"
    USD = "USD"
    GBP = "GBP"
    SAR = "SAR"


class HouseholdRelationship(StrEnum):
    SELF = "self"
    SPOUSE = "spouse"
    CHILD = "child"
    HOUSEHOLD = "household"


class AccountType(StrEnum):
    CURRENT = "current"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    CASH = "cash"
    INVESTMENT = "investment"
    PENSION = "pension"
    PROPERTY = "property"
    LOAN = "loan"
    RECEIVABLE = "receivable"
    OTHER_ASSET = "other_asset"
    OTHER_LIABILITY = "other_liability"


LIABILITY_ACCOUNT_TYPES = {
    AccountType.CREDIT_CARD,
    AccountType.LOAN,
    AccountType.OTHER_LIABILITY,
}


class TransactionDirection(StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"


class TransactionKind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    INTERNAL_TRANSFER = "internal_transfer"
    CREDIT_CARD_PAYMENT = "credit_card_payment"
    INVESTMENT_PURCHASE = "investment_purchase"
    INVESTMENT_SALE = "investment_sale"
    REFUND = "refund"
    FEE = "fee"
    INTEREST = "interest"
    ADJUSTMENT = "adjustment"
    OPENING_BALANCE = "opening_balance"


# Kinds that must never be counted as discretionary/essential spending.
NON_SPENDING_KINDS = {
    TransactionKind.INTERNAL_TRANSFER,
    TransactionKind.CREDIT_CARD_PAYMENT,
    TransactionKind.INVESTMENT_PURCHASE,
    TransactionKind.OPENING_BALANCE,
}


class TransactionStatus(StrEnum):
    PENDING = "pending"
    BOOKED = "booked"
    REVERSED = "reversed"
    EXCLUDED = "excluded"


class RuleMatchField(StrEnum):
    DESCRIPTION = "description"
    ORIGINAL_DESCRIPTION = "original_description"
    MERCHANT = "merchant"
    COUNTERPARTY = "counterparty"
    AMOUNT = "amount"


class RuleOperator(StrEnum):
    CONTAINS = "contains"
    EQUALS = "equals"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"
    AMOUNT_RANGE = "amount_range"


class ImportStatus(StrEnum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    PREVIEW_READY = "preview_ready"
    IMPORTING = "importing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class CashflowDirection(StrEnum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"


class CashflowStatus(StrEnum):
    PLANNED = "planned"
    RESERVED = "reserved"
    PAID = "paid"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class GoalType(StrEnum):
    EMERGENCY_RESERVE = "emergency_reserve"
    TRAVEL = "travel"
    CAR_PURCHASE = "car_purchase"
    CAR_SETUP = "car_setup"
    EDUCATION = "education"
    HOUSING = "housing"
    INVESTMENT = "investment"
    DEBT_REPAYMENT = "debt_repayment"
    CUSTOM = "custom"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    MET = "met"
    AT_RISK = "at_risk"
    ARCHIVED = "archived"


class AssetClass(StrEnum):
    CASH = "cash"
    STOCK = "stock"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    PENSION = "pension"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    PROPERTY = "property"
    PRIVATE_EQUITY = "private_equity"
    OTHER = "other"


class LiquidityClass(StrEnum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    RESTRICTED = "restricted"
    ILLIQUID = "illiquid"
