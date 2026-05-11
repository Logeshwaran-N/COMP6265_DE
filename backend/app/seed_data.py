from __future__ import annotations

from typing import Any, Dict, List

SHARED_API_DATA: Dict[str, List[Dict[str, Any]]] = {
    "fruits": [
        {"product": "apple", "market_price": 11.00, "verified_grade": "A", "provider_ref": "S1", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "banana", "market_price": 4.45, "verified_grade": "A", "provider_ref": "S2", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "orange", "market_price": 6.05, "verified_grade": "A", "provider_ref": "S3", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "mango", "market_price": 10.50, "verified_grade": "B", "provider_ref": "S4", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "grapes", "market_price": 5.45, "verified_grade": "B", "provider_ref": "S2", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "pear", "market_price": 3.35, "verified_grade": "B", "provider_ref": "S5", "timestamp": "2026-05-07T08:30:00Z"},
        {"product": "kiwi", "market_price": 7.25, "verified_grade": "A", "provider_ref": "S4", "timestamp": "2026-05-07T08:30:00Z"},
    ],
    "fx_rates": [
        {"symbol": "GBP_INR", "spot_rate": 108.43, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
        {"symbol": "USD_INR", "spot_rate": 83.49, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
        {"symbol": "EUR_INR", "spot_rate": 91.79, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
        {"symbol": "GBP_USD", "spot_rate": 1.30, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
        {"symbol": "EUR_GBP", "spot_rate": 0.84, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
        {"symbol": "EUR_USD", "spot_rate": 1.09, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
        {"symbol": "USD_GBP", "spot_rate": 0.78, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
        {"symbol": "GBP_EUR", "spot_rate": 1.18, "precision": 4, "as_of": "2026-05-07T08:30:00Z"},
    ],
    "orders": [
        {"id": "O-1001", "area": "South East", "contact": "asha@example.com", "amount": 148.20, "demand": 0.82},
        {"id": "O-1002", "area": "London", "contact": "ben@example.com", "amount": 249.99, "demand": 0.92},
        {"id": "O-1003", "area": "Midlands", "contact": "chitra@example.com", "amount": 72.40, "demand": 0.61},
        {"id": "O-1004", "area": "Scotland", "contact": "david@example.com", "amount": 310.00, "demand": 0.87},
        {"id": "O-1005", "area": "Wales", "contact": "ella@example.com", "amount": 42.50, "demand": 0.50},
        {"id": "O-1006", "area": "South West", "contact": "faisal@example.com", "amount": 133.10, "demand": 0.75},
        {"id": "O-1007", "area": "North West", "contact": "gina@example.com", "amount": 91.80, "demand": 0.67},
        {"id": "O-1008", "area": "London", "contact": "hari@example.com", "amount": 420.00, "demand": 0.96},
    ],
}

