#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../backend"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
