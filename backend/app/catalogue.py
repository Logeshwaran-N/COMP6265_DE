from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List

# Virtual catalogue: users query these virtual schemas, not physical source tables.
# This is the key data integration layer: the same virtual column can be called
# different names in CSV, SQLite and API sources.
CATALOGUE: Dict[str, Dict[str, Any]] = {
    "fruits": {
        "title": "Retail fruit price feed",
        "description": "Multi-source fruit catalogue used to demonstrate duplicated values and trust-aware conflict resolution.",
        "domain": "agri-retail",
        "entity_key": "name",
        "columns": {
            "name": {"type": "string", "pii": False, "price": 1.0, "distinct": 8, "meaning": "Fruit name"},
            "price_gbp": {"type": "number", "pii": False, "price": 2.0, "distinct": 20, "meaning": "Unit price in GBP"},
            "quality_grade": {"type": "string", "pii": False, "price": 1.5, "distinct": 4, "meaning": "Supplier quality grade"},
            "supplier_id": {"type": "string", "pii": False, "price": 1.0, "distinct": 5, "meaning": "Supplier reference"},
            "last_updated": {"type": "date", "pii": False, "price": 0.5, "distinct": 10, "meaning": "Source update timestamp"},
        },
        "price_points": [
            {"name": "fruit_basic_view", "columns": ["name", "price_gbp"], "price": 3.0},
            {"name": "fruit_quality_view", "columns": ["name", "price_gbp", "quality_grade"], "price": 4.0},
            {"name": "fruit_full_view", "columns": ["name", "price_gbp", "quality_grade", "supplier_id", "last_updated"], "price": 5.5},
        ],
        "policy": {
            "permissions": [
                {"roles": ["guest", "analyst", "researcher", "data_steward", "admin"], "purposes": ["research", "planning", "commercial", "internal_audit"], "actions": ["read", "verify"]}
            ],
            "prohibitions": [],
            "duties": ["audit_log", "show_provenance"],
            "max_rows_by_role": {"guest": 25, "analyst": 100, "researcher": 250, "data_steward": 500, "admin": 1000},
        },
        "sources": {
            "fruit_csv": {
                "type": "csv",
                "provider": "local_upload_partner",
                "file": "fruits.csv",
                "row_count": 7,
                "base_trust": 0.42,
                "authority_level": 0.25,
                "freshness_days": 21,
                "access_cost": 0.20,
                "row_scan_cost": 0.004,
                "latency_ms": 18,
                "api_call_cost": 0.0,
                "conflict_risk": 0.75,
                "mapping": {"name": "fruit", "price_gbp": "price", "quality_grade": "grade", "supplier_id": "supplier", "last_updated": "updated"},
            },
            "fruit_db": {
                "type": "sqlite",
                "provider": "warehouse_partner",
                "table": "fruit_prices",
                "row_count": 7,
                "base_trust": 0.77,
                "authority_level": 0.65,
                "freshness_days": 3,
                "access_cost": 0.55,
                "row_scan_cost": 0.009,
                "latency_ms": 35,
                "api_call_cost": 0.0,
                "conflict_risk": 0.40,
                "mapping": {"name": "fruit_name", "price_gbp": "cost_gbp", "quality_grade": "quality_band", "supplier_id": "supplier_code", "last_updated": "last_sync"},
            },
            "fruit_api": {
                "type": "api",
                "provider": "trusted_market_feed",
                "endpoint": "/fruits",
                "row_count": 7,
                "base_trust": 0.93,
                "authority_level": 0.90,
                "freshness_days": 0,
                "access_cost": 1.25,
                "row_scan_cost": 0.015,
                "latency_ms": 85,
                "api_call_cost": 0.80,
                "conflict_risk": 0.15,
                "mapping": {"name": "product", "price_gbp": "market_price", "quality_grade": "verified_grade", "supplier_id": "provider_ref", "last_updated": "timestamp"},
            },
        },
    },
    "fx_rates": {
        "title": "Foreign exchange rate feed",
        "description": "Exchange-rate dataset where source authority matters. Useful for GBP/INR conflict demo.",
        "domain": "finance",
        "entity_key": "pair",
        "columns": {
            "pair": {"type": "string", "pii": False, "price": 1.0, "distinct": 8, "meaning": "Currency pair such as GBP_INR"},
            "rate": {"type": "number", "pii": False, "price": 3.0, "distinct": 500, "meaning": "Exchange rate"},
            "precision": {"type": "number", "pii": False, "price": 1.0, "distinct": 5, "meaning": "Decimal precision supplied by provider"},
            "last_updated": {"type": "date", "pii": False, "price": 1.0, "distinct": 400, "meaning": "Timestamp of the rate"},
        },
        "price_points": [
            {"name": "fx_rate_only", "columns": ["pair", "rate"], "price": 4.0},
            {"name": "fx_full_view", "columns": ["pair", "rate", "precision", "last_updated"], "price": 6.5},
        ],
        "policy": {
            "permissions": [
                {"roles": ["analyst", "researcher", "data_steward", "admin"], "purposes": ["research", "planning", "commercial", "internal_audit"], "actions": ["read", "verify"]}
            ],
            "prohibitions": [
                {"roles": ["guest"], "columns": ["rate", "precision"], "reason": "Guest users can browse metadata only for finance datasets."}
            ],
            "duties": ["audit_log", "show_provenance", "show_authority_reason"],
            "max_rows_by_role": {"guest": 0, "analyst": 100, "researcher": 250, "data_steward": 500, "admin": 1000},
        },
        "sources": {
            "fx_csv": {
                "type": "csv",
                "provider": "manual_uploaded_rates",
                "file": "fx_rates.csv",
                "row_count": 8,
                "base_trust": 0.30,
                "authority_level": 0.20,
                "freshness_days": 14,
                "access_cost": 0.15,
                "row_scan_cost": 0.004,
                "latency_ms": 15,
                "api_call_cost": 0.0,
                "conflict_risk": 0.85,
                "mapping": {"pair": "pair_code", "rate": "value", "precision": "decimals", "last_updated": "updated_at"},
            },
            "fx_db": {
                "type": "sqlite",
                "provider": "gov_authorised_server",
                "table": "fx_official_rates",
                "row_count": 8,
                "base_trust": 0.96,
                "authority_level": 1.00,
                "freshness_days": 1,
                "access_cost": 0.75,
                "row_scan_cost": 0.010,
                "latency_ms": 40,
                "api_call_cost": 0.0,
                "conflict_risk": 0.10,
                "mapping": {"pair": "currency_pair", "rate": "official_rate", "precision": "scale", "last_updated": "published_at"},
            },
            "fx_api": {
                "type": "api",
                "provider": "realtime_fx_provider",
                "endpoint": "/fx_rates",
                "row_count": 8,
                "base_trust": 0.90,
                "authority_level": 0.85,
                "freshness_days": 0,
                "access_cost": 1.40,
                "row_scan_cost": 0.018,
                "latency_ms": 95,
                "api_call_cost": 0.95,
                "conflict_risk": 0.20,
                "mapping": {"pair": "symbol", "rate": "spot_rate", "precision": "precision", "last_updated": "as_of"},
            },
            "fx_live_api": {
                "type": "live_fx_api",
                "provider": "frankfurter_live_reference",
                "endpoint": "https://api.frankfurter.dev/v2/rates",
                "row_count": 8,
                "base_trust": 0.92,
                "authority_level": 0.88,
                "freshness_days": 0,
                "access_cost": 1.75,
                "row_scan_cost": 0.020,
                "latency_ms": 140,
                "api_call_cost": 1.20,
                "conflict_risk": 0.18,
                "mapping": {"pair": "symbol", "rate": "spot_rate", "precision": "precision", "last_updated": "as_of"},
            },
        },
    },
    "fx_history": {
        "title": "Foreign exchange historical rates",
        "description": "Generated daily FX history for analytics, forecasting and bot/model training scenarios. Live APIs are not used for bulk history queries.",
        "domain": "finance-history",
        "entity_key": "history_id",
        "columns": {
            "history_id": {"type": "string", "pii": False, "price": 0.5, "distinct": 9000, "meaning": "Synthetic history row identifier"},
            "date": {"type": "date", "pii": False, "price": 1.0, "distinct": 1100, "meaning": "Observation date"},
            "pair": {"type": "string", "pii": False, "price": 1.0, "distinct": 8, "meaning": "Currency pair such as GBP_INR"},
            "base": {"type": "string", "pii": False, "price": 0.5, "distinct": 4, "meaning": "Base currency"},
            "quote": {"type": "string", "pii": False, "price": 0.5, "distinct": 4, "meaning": "Quote currency"},
            "rate": {"type": "number", "pii": False, "price": 2.5, "distinct": 5000, "meaning": "Historical daily exchange rate"},
            "provider": {"type": "string", "pii": False, "price": 0.5, "distinct": 4, "meaning": "Historical data provider"},
            "quality_tier": {"type": "string", "pii": False, "price": 0.5, "distinct": 3, "meaning": "Quality tier: manual, official or blended"},
        },
        "price_points": [
            {"name": "fx_history_training_view", "columns": ["date", "pair", "rate"], "price": 5.0},
            {"name": "fx_history_full_view", "columns": ["history_id", "date", "pair", "base", "quote", "rate", "provider", "quality_tier"], "price": 9.0},
        ],
        "policy": {
            "permissions": [
                {"roles": ["analyst", "researcher", "data_steward", "admin"], "purposes": ["research", "planning", "commercial", "internal_audit"], "actions": ["read", "verify"]}
            ],
            "prohibitions": [
                {"roles": ["guest"], "columns": ["rate"], "reason": "Guest users can browse metadata only for finance-history datasets."}
            ],
            "duties": ["audit_log", "show_provenance", "show_bulk_query_cost"],
            "max_rows_by_role": {"guest": 0, "analyst": 500, "researcher": 1500, "data_steward": 5000, "admin": 10000},
        },
        "sources": {
            "fx_history_csv": {
                "type": "csv",
                "provider": "manual_uploaded_rates",
                "file": "fx_history.csv",
                "row_count": 8768,
                "base_trust": 0.34,
                "authority_level": 0.25,
                "freshness_days": 14,
                "access_cost": 0.35,
                "row_scan_cost": 0.0025,
                "latency_ms": 55,
                "api_call_cost": 0.0,
                "conflict_risk": 0.55,
                "mapping": {"history_id": "history_id", "date": "date", "pair": "pair", "base": "base", "quote": "quote", "rate": "rate", "provider": "provider", "quality_tier": "quality_tier"},
            },
            "fx_history_db": {
                "type": "sqlite",
                "provider": "gov_authorised_server",
                "table": "fx_history_reference",
                "row_count": 8768,
                "base_trust": 0.94,
                "authority_level": 0.98,
                "freshness_days": 1,
                "access_cost": 0.95,
                "row_scan_cost": 0.006,
                "latency_ms": 60,
                "api_call_cost": 0.0,
                "conflict_risk": 0.12,
                "mapping": {"history_id": "history_id", "date": "observation_date", "pair": "currency_pair", "base": "base_currency", "quote": "quote_currency", "rate": "official_rate", "provider": "provider", "quality_tier": "quality_tier"},
            },
        },
    },
    "orders": {
        "title": "Retail order analytics",
        "description": "Synthetic sensitive dataset for privacy and column-level governance demo.",
        "domain": "retail-analytics",
        "entity_key": "order_id",
        "columns": {
            "order_id": {"type": "string", "pii": False, "price": 1.0, "distinct": 8, "meaning": "Order identifier"},
            "customer_region": {"type": "string", "pii": False, "price": 1.0, "distinct": 5, "meaning": "Region"},
            "customer_email": {"type": "string", "pii": True, "price": 5.0, "distinct": 8, "meaning": "Direct customer identifier"},
            "total_gbp": {"type": "number", "pii": False, "price": 2.0, "distinct": 20, "meaning": "Order value"},
            "demand_score": {"type": "number", "pii": False, "price": 2.5, "distinct": 10, "meaning": "Derived analytics score"},
        },
        "price_points": [
            {"name": "orders_safe_analytics", "columns": ["order_id", "customer_region", "total_gbp", "demand_score"], "price": 6.0},
            {"name": "orders_full_admin", "columns": ["order_id", "customer_region", "customer_email", "total_gbp", "demand_score"], "price": 12.0},
        ],
        "policy": {
            "permissions": [
                {"roles": ["analyst", "researcher", "data_steward", "admin"], "purposes": ["research", "planning", "internal_audit"], "actions": ["read"]},
                {"roles": ["admin"], "purposes": ["internal_audit"], "actions": ["read_sensitive"]}
            ],
            "prohibitions": [
                {"roles": ["guest", "analyst", "researcher", "data_steward"], "columns": ["customer_email"], "reason": "Direct identifiers are restricted to admin/internal audit only."},
                {"roles": ["analyst", "researcher"], "purposes": ["commercial"], "reason": "Commercial use of synthetic order analytics is not allowed in this prototype policy."}
            ],
            "duties": ["audit_log", "mask_sensitive_when_denied"],
            "max_rows_by_role": {"guest": 0, "analyst": 100, "researcher": 250, "data_steward": 500, "admin": 1000},
        },
        "sources": {
            "orders_db": {
                "type": "sqlite",
                "provider": "enterprise_warehouse",
                "table": "orders",
                "row_count": 8,
                "base_trust": 0.85,
                "authority_level": 0.80,
                "freshness_days": 2,
                "access_cost": 0.90,
                "row_scan_cost": 0.012,
                "latency_ms": 45,
                "api_call_cost": 0.0,
                "conflict_risk": 0.20,
                "mapping": {"order_id": "order_id", "customer_region": "region", "customer_email": "email", "total_gbp": "total", "demand_score": "score"},
            },
            "orders_api": {
                "type": "api",
                "provider": "retail_analytics_service",
                "endpoint": "/orders",
                "row_count": 8,
                "base_trust": 0.78,
                "authority_level": 0.70,
                "freshness_days": 0,
                "access_cost": 1.15,
                "row_scan_cost": 0.015,
                "latency_ms": 90,
                "api_call_cost": 0.85,
                "conflict_risk": 0.25,
                "mapping": {"order_id": "id", "customer_region": "area", "customer_email": "contact", "total_gbp": "amount", "demand_score": "demand"},
            },
        },
    },
    "suppliers": {
        "title": "Supplier metadata",
        "description": "Small dimension dataset used to demonstrate a join plan and left-deep optimisation.",
        "domain": "retail-master-data",
        "entity_key": "supplier_id",
        "columns": {
            "supplier_id": {"type": "string", "pii": False, "price": 0.5, "distinct": 5, "meaning": "Supplier reference"},
            "supplier_name": {"type": "string", "pii": False, "price": 1.0, "distinct": 5, "meaning": "Supplier name"},
            "country": {"type": "string", "pii": False, "price": 1.0, "distinct": 4, "meaning": "Supplier country"},
            "rating": {"type": "number", "pii": False, "price": 1.0, "distinct": 5, "meaning": "Supplier quality rating"},
        },
        "price_points": [{"name": "supplier_full", "columns": ["supplier_id", "supplier_name", "country", "rating"], "price": 3.0}],
        "policy": {
            "permissions": [{"roles": ["guest", "analyst", "researcher", "data_steward", "admin"], "purposes": ["research", "planning", "commercial", "internal_audit"], "actions": ["read"]}],
            "prohibitions": [],
            "duties": ["audit_log"],
            "max_rows_by_role": {"guest": 50, "analyst": 100, "researcher": 250, "data_steward": 500, "admin": 1000},
        },
        "sources": {
            "suppliers_db": {
                "type": "sqlite",
                "provider": "enterprise_warehouse",
                "table": "suppliers",
                "row_count": 5,
                "base_trust": 0.88,
                "authority_level": 0.80,
                "freshness_days": 4,
                "access_cost": 0.45,
                "row_scan_cost": 0.006,
                "latency_ms": 30,
                "api_call_cost": 0.0,
                "conflict_risk": 0.10,
                "mapping": {"supplier_id": "supplier_id", "supplier_name": "supplier_name", "country": "country", "rating": "rating"},
            }
        },
    }
}

PROVIDER_ENDORSEMENTS = {
    "gov_authorised_server": ["enterprise_warehouse", "realtime_fx_provider", "frankfurter_live_reference"],
    "trusted_market_feed": ["warehouse_partner", "local_upload_partner"],
    "enterprise_warehouse": ["warehouse_partner", "retail_analytics_service"],
    "realtime_fx_provider": ["gov_authorised_server", "frankfurter_live_reference"],
    "frankfurter_live_reference": ["gov_authorised_server", "realtime_fx_provider"],
    "warehouse_partner": ["local_upload_partner"],
    "retail_analytics_service": ["enterprise_warehouse"],
    "manual_uploaded_rates": [],
    "local_upload_partner": [],
}


def get_catalogue() -> Dict[str, Any]:
    return deepcopy(CATALOGUE)


def list_sources() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for dataset_name, dataset in CATALOGUE.items():
        for source_name, src in dataset["sources"].items():
            item = deepcopy(src)
            item["source_name"] = source_name
            item["dataset"] = dataset_name
            item["dataset_title"] = dataset["title"]
            out.append(item)
    return out


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
