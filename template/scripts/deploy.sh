#!/usr/bin/env bash
# 打包 + 发布。用法：bash scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python3 scripts/build.py

echo "开始发布…"
with deploy --zip /tmp/bp-site.zip
