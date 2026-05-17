#!/bin/sh
# Load zotero-import environment variables from this script's directory.
# Usage:
#   . /absolute/path/to/zotero-import/scripts/load_env.sh

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENV_FILE="$SCRIPT_DIR/../.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "zotero-import: .env not found at $ENV_FILE" >&2
  return 1 2>/dev/null || exit 1
fi

. "$ENV_FILE"
