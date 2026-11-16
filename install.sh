#!/usr/bin/env bash
# 一键安装或升级 game-ui-restore 规范与门禁脚本到当前项目目录
# 用法（在目标项目根目录执行）：
#   curl -fsSL https://raw.githubusercontent.com/P1tbu11/game-ui-restore/v3.0.0/install.sh | bash
#   或指定版本：
#   curl -fsSL https://raw.githubusercontent.com/P1tbu11/game-ui-restore/main/install.sh | bash -s -- v3.0.0

set -euo pipefail

REF="${1:-v3.0.0}"
REPO_URL="https://github.com/P1tbu11/game-ui-restore.git"
TARGET_SPEC="spec/game-ui-restore"

TMP_DIR="$(mktemp -d)"
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

echo ">>> 正在拉取 game-ui-restore (${REF}) ..."
git clone --depth 1 --branch "$REF" "$REPO_URL" "$TMP_DIR/repo" >/dev/null 2>&1

mkdir -p "$TARGET_SPEC" scripts
rm -rf "$TARGET_SPEC/scripts" "$TARGET_SPEC/templates"
cp "$TMP_DIR/repo/AGENTS.md" "$TMP_DIR/repo/SPEC.md" "$TMP_DIR/repo/README.md" "$TARGET_SPEC/"
cp -R "$TMP_DIR/repo/scripts" "$TARGET_SPEC/scripts"
cp -R "$TMP_DIR/repo/templates" "$TARGET_SPEC/templates"
cp "$TMP_DIR/repo/scripts/"*.py scripts/
chmod +x scripts/*.py "$TARGET_SPEC/scripts/"*.py

if [ ! -f "INTAKE.json" ]; then
  cp "$TMP_DIR/repo/templates/INTAKE.example.json" INTAKE.json
  echo "  [+] 已生成准入单样板：INTAKE.json（开工前请先填好舞台与变体清单）"
else
  echo "  [=] 保留已有 INTAKE.json"
fi

if [ ! -f "deploy.manifest.json" ]; then
  cp "$TMP_DIR/repo/templates/deploy.manifest.example.json" deploy.manifest.json
  echo "  [+] 已生成打包清单样板：deploy.manifest.json"
else
  echo "  [=] 保留已有 deploy.manifest.json"
fi

echo ""
echo "✅ 安装完成（版本：${REF}）！"
echo "  - 规则文档：${TARGET_SPEC}/AGENTS.md 、 ${TARGET_SPEC}/SPEC.md"
echo "  - 门禁脚本：scripts/lint_assets.py 、 scripts/visual_check.py 、 scripts/build.py"
echo ""
echo "下一步喂给 Agent："
echo "  \"先读 spec/game-ui-restore/AGENTS.md，拉取 Figma 填好 INTAKE.json 后再动代码，收工跑通三条 scripts 门禁。\""
