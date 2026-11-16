#!/usr/bin/env python3
"""按 deploy.manifest.json 白名单干净打包，并校验整包体积预算（防网关 413 与漏图）。

用法：
  python3 scripts/build.py [--out /tmp/game-ui-site.zip] [--max-mb 50]
"""
import json
import os
import shutil
import sys
import zipfile

def _resolve_root():
    if "--root" in sys.argv:
        idx = sys.argv.index("--root")
        if idx + 1 < len(sys.argv):
            return os.path.abspath(sys.argv[idx + 1])
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = _resolve_root()
MANIFEST = os.path.join(ROOT, "deploy.manifest.json")
INTAKE = os.path.join(ROOT, "INTAKE.json")
DEFAULT_OUT = "/tmp/game-ui-site.zip"
MARKERS = ("index.html", "deploy.manifest.json")


def preflight():
    missing = [p for p in MARKERS if not os.path.exists(os.path.join(ROOT, p))]
    if not missing:
        return
    print("这里不是项目根目录，无法打包。")
    print(f"脚本定位到的目录：{ROOT}")
    for p in missing:
        print(f"  缺少：{p}")
    print("\n请先在项目根放置 deploy.manifest.json（参考 templates/deploy.manifest.example.json）。")
    sys.exit(2)


def resolve_max_mb():
    if "--max-mb" in sys.argv:
        idx = sys.argv.index("--max-mb")
        return float(sys.argv[idx + 1])
    if os.path.exists(INTAKE):
        try:
            data = json.load(open(INTAKE, encoding="utf-8"))
            return float((data.get("budget") or {}).get("maxTotalPackageMB", 50))
        except Exception:
            pass
    return 50.0


def copy_into(src, dst, excludes):
    if os.path.isfile(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return 1
    count = 0
    for base, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in excludes]
        for f in files:
            if f in excludes:
                continue
            sp = os.path.join(base, f)
            rel = os.path.relpath(sp, src)
            dp = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            shutil.copy2(sp, dp)
            count += 1
    return count


def main():
    preflight()

    out = DEFAULT_OUT
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    max_mb = resolve_max_mb()

    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    includes = manifest.get("include") or []
    excludes = set(manifest.get("exclude") or [".DS_Store"])

    if not includes:
        print("[error] deploy.manifest.json 的 include 为空，拒绝打出空包。")
        sys.exit(1)

    staging = out + ".staging"
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging, exist_ok=True)

    total = 0
    absent = []
    for item in includes:
        src = os.path.join(ROOT, item)
        if not os.path.exists(src):
            absent.append(item)
            continue
        total += copy_into(src, os.path.join(staging, item), excludes)

    if absent:
        shutil.rmtree(staging, ignore_errors=True)
        print("[error] deploy.manifest.json 中以下路径不存在，打包中止：")
        for item in absent:
            print(f"  - {item}")
        sys.exit(1)

    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for base, _, files in sorted(os.walk(staging)):
            for f in sorted(files):
                p = os.path.join(base, f)
                zf.write(p, os.path.relpath(p, staging))

    shutil.rmtree(staging, ignore_errors=True)
    size_mb = os.path.getsize(out) / 1024 / 1024
    print(f"打包完成：{out}（{total} 个文件，{size_mb:.2f} MB / 上限 {max_mb:g} MB）")

    if size_mb > max_mb:
        print(f"[error] 发布包体积 {size_mb:.2f} MB 超过上限 {max_mb:g} MB（易触发网关 413），请压缩视频或清理冗余资源。")
        sys.exit(1)


if __name__ == "__main__":
    main()
