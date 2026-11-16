#!/usr/bin/env python3
"""按 deploy.manifest.json 收集站点文件并打包。

用法：python3 scripts/build.py [--out /tmp/bp-site.zip]

只打包清单里的东西。项目根目录的截图、参考图、抓取脚本不进包，
避免再次触发 with 网关的 413。
"""
import json
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "deploy.manifest.json")
DEFAULT_OUT = "/tmp/bp-site.zip"
MARKERS = ("index.html", "deploy.manifest.json", os.path.join("data", "app.js"))


def preflight():
    """确认自己在项目根目录。

    这个脚本会跟着规则包单独发给同事，跑错地方时必须说人话，
    不能甩一个 FileNotFoundError 让人去猜。
    """
    missing = [p for p in MARKERS if not os.path.exists(os.path.join(ROOT, p))]
    if not missing:
        return
    print("这里不是项目根目录，没法打包。")
    print(f"脚本定位到的目录：{ROOT}")
    for p in missing:
        print(f"  缺少：{p}")
    print()
    print("scripts/ 和 deploy.manifest.json 要放进项目根目录，与 index.html 同级：")
    print("  <项目根>/index.html")
    print("  <项目根>/deploy.manifest.json")
    print("  <项目根>/scripts/build.py")
    print()
    print("规则包里不含样板间（index.html / data / pieces / fonts / video / export），")
    print("先把脚本复制进真正的项目目录，再执行。")
    sys.exit(2)


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

    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    excludes = set(manifest.get("exclude", []))

    staging = out + ".d"
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging, exist_ok=True)

    total = 0
    absent = []
    for item in manifest["include"]:
        src = os.path.join(ROOT, item)
        if not os.path.exists(src):
            absent.append(item)
            continue
        total += copy_into(src, os.path.join(staging, item), excludes)

    if absent:
        print("清单里有路径在项目里找不到，打包中止：")
        for item in absent:
            print(f"  {item}")
        print("确认 deploy.manifest.json 的 include 与项目实际目录一致。")
        sys.exit(1)

    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(staging):
            for f in files:
                p = os.path.join(base, f)
                z.write(p, os.path.relpath(p, staging))

    size = os.path.getsize(out) / 1024 / 1024
    print(f"打包完成：{out}  {total} 个文件  {size:.1f} MB")
    print(f"临时目录：{staging}")


if __name__ == "__main__":
    main()
