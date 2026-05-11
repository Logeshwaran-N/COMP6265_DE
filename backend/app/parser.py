from __future__ import annotations

import re
from typing import Optional
from .config import settings
from .errors import InvalidQueryError
from .models import ParsedPredicate, ParsedQuery

_QUERY_RE = re.compile(
    r"^\s*SELECT\s+(?P<select>.+?)\s+FROM\s+(?P<dataset>[a-zA-Z_][\w]*)"
    r"(?:\s+JOIN\s+(?P<join_dataset>[a-zA-Z_][\w]*)\s+ON\s+(?P<join_left>[\w\.]+)\s*=\s*(?P<join_right>[\w\.]+))?"
    r"(?:\s+WHERE\s+(?P<where>.+?))?"
    r"(?:\s+ORDER\s+BY\s+(?P<order_by>[\w\.]+)(?:\s+(?P<order_dir>ASC|DESC))?)?"
    r"(?:\s+LIMIT\s+(?P<limit>\d+))?"
    r"\s*$",
    re.IGNORECASE,
)

_CONDITION_RE = re.compile(r"^\s*(?P<left>[\w\.]+)\s*(?P<op>=|!=|>=|<=|>|<)\s*(?P<right>.+?)\s*$")


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    return value


def parse_query(raw_query: str) -> ParsedQuery:
    if not raw_query or not isinstance(raw_query, str):
        raise InvalidQueryError("Query must be a non-empty string")

    raw = raw_query.strip().rstrip(";")
    if not raw:
        raise InvalidQueryError("Query must be a non-empty string")
    if len(raw) > settings.max_query_length:
        raise InvalidQueryError(f"Query exceeds maximum length of {settings.max_query_length} characters")

    verification_hint = False
    if re.search(r"\bWITH\s+VERIFICATION\b", raw, flags=re.IGNORECASE):
        verification_hint = True
        raw = re.sub(r"\bWITH\s+VERIFICATION\b", "", raw, flags=re.IGNORECASE).strip()

    match = _QUERY_RE.match(raw)
    if not match:
        raise InvalidQueryError(
            "Query format: SELECT col1, col2 FROM dataset "
            "[JOIN dataset2 ON a=b] [WHERE col=value] [LIMIT n] [WITH VERIFICATION]. "
            f"Your query: {raw[:100]}..."
        )

    select_raw = match.group("select").strip()
    select = ["*"] if select_raw == "*" else [c.strip().split(".")[-1] for c in select_raw.split(",") if c.strip()]
    where_obj: Optional[ParsedPredicate] = None
    where_raw = match.group("where")
    if where_raw:
        where_raw = re.sub(r"\s+ORDER\s+BY\s+[\w\.]+(?:\s+(?:ASC|DESC))?\s*$", "", where_raw, flags=re.IGNORECASE)
        where_raw = re.sub(r"\s+LIMIT\s+\d+\s*$", "", where_raw, flags=re.IGNORECASE)
        cond = _CONDITION_RE.match(where_raw)
        if not cond:
            raise InvalidQueryError("WHERE currently supports a single condition such as name = 'apple' or rate > 100.")
        raw_right = cond.group("right").strip()
        was_quoted = (raw_right.startswith("'") and raw_right.endswith("'")) or (raw_right.startswith('"') and raw_right.endswith('"'))
        right_value = _strip_quotes(raw_right)
        right_is_col = (
            not was_quoted
            and bool(re.match(r"^[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)?$", right_value))
            and not re.match(r"^-?\d+(\.\d+)?$", right_value)
        )
        where_obj = ParsedPredicate(
            left=cond.group("left").split(".")[-1],
            op=cond.group("op"),
            right=right_value.split(".")[-1] if right_is_col else right_value,
            right_is_column=right_is_col,
        )

    limit = int(match.group("limit")) if match.group("limit") else None
    order_by = match.group("order_by").split(".")[-1] if match.group("order_by") else None
    order_dir = (match.group("order_dir") or "asc").lower()
    return ParsedQuery(
        raw=raw_query,
        select=select,
        dataset=match.group("dataset").lower(),
        where=where_obj,
        join_dataset=match.group("join_dataset").lower() if match.group("join_dataset") else None,
        join_left=match.group("join_left").split(".")[-1] if match.group("join_left") else None,
        join_right=match.group("join_right").split(".")[-1] if match.group("join_right") else None,
        verification_hint=verification_hint,
        limit=limit,
        order_by=order_by,
        order_dir=order_dir,
    )
