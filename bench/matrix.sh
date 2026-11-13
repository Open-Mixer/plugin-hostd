#!/bin/bash
# matrix.sh [--json] <document-or-set-directory>...: a matrix run read as one result, by period length (rows, ms) and
# rate (columns), one table per periods value, with each rate's safe minimum period (lib/matrix.py, #48).
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
command -v python3 >/dev/null || { echo "matrix.sh: python3 is needed" >&2; exit 2; }
exec python3 -I "$here/lib/matrix.py" "$@"
