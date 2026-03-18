#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

psql "clauseai-db" -f "${ROOT_DIR}/infra/sql/reference_db.sql"
