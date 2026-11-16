#!/usr/bin/env python3
"""资源体检：缺文件 / 切图带底 / 页面引了 SVG / 字体缺失。

用法：python3 scripts/lint_assets.py
退出码 0 = 全绿，1 = 有错误。
"""
import os
import re
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")
DATA = os.path.join(ROOT, "data", "app.js")
ALLOW_OPAQUE = ("texture", "tex", "header", "bg", "tile", "poster")
MARKERS = ("index.html", os.path.join("data", "app.js"), "pieces")

errors = []
warns = []


def preflight():
    """没有项目可查时必须报错，不能对空目录说"全绿"。

    假绿比红灯更贵：它会让人以为体检过了，问题留到线上才发现。
    """
    missing = [p for p in MARKERS if not os.path.exists(os.path.join(ROOT, p))]
    if not missing:
        return True
    print("这里不是项目根目录，没有东西可体检。")
    print(f"脚本定位到的目录：{ROOT}")
    for p in missing:
        print(f"  缺少：{p}")
    print()
    print("scripts/ 要放进项目根目录，与 index.html 同级。")
    print("规则包里只有文档和脚本，不含样板间——先拿到项目目录再跑。")
    return False


def read_png(path):
    """返回 (w, h, rows) ；rows[y][x] = (r,g,b,a)。只支持 8bit、非隔行。"""
    d = open(path, "rb").read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, w, h, ct, bd = 8, b"", 0, 0, 6, 8
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        chunk = d[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", chunk[:10])[:4]
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"IEND":
            break
    if bd != 8 or ct not in (2, 6):
        return None
    ch = 3 if ct == 2 else 4
    raw = zlib.decompress(idat)
    stride = w * ch
    rows = []
    prev = bytearray(stride)
    i = 0
    for _ in range(h):
        f = raw[i]
        i += 1
        line = bytearray(raw[i:i + stride])
        i += stride
        if f == 1:
            for x in range(ch, stride):
                line[x] = (line[x] + line[x - ch]) & 255
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                a = line[x - ch] if x >= ch else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - ch] if x >= ch else 0
                b = prev[x]
                c = prev[x - ch] if x >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        rows.append(line)
        prev = line
    px = []
    for line in rows:
        row = []
        for x in range(w):
            o = x * ch
            if ch == 4:
                row.append(tuple(line[o:o + 4]))
            else:
                row.append((line[o], line[o + 1], line[o + 2], 255))
        px.append(row)
    return w, h, px


def refs():
    out = set()
    if os.path.exists(HTML):
        txt = open(HTML, encoding="utf-8").read()
        # 脚本块里是拼接出来的路径，静态扫不到，先剔掉，避免误报
        txt = re.sub(r"<script[\s\S]*?</script>", "", txt)
        for m in re.findall(r'(?:src|href)="([^"]+)"', txt):
            out.add(m)
        for m in re.findall(r'url\(["\']?([^"\')]+)["\']?\)', txt):
            out.add(m)
    if os.path.exists(DATA):
        txt = open(DATA, encoding="utf-8").read()
        for m in re.findall(r"['\"]((?:pieces|export|video|fonts)/[^'\"]+)['\"]", txt):
            out.add(m)
    keep = []
    for r in out:
        if r.startswith(("http", "data:", "#", "mailto:")):
            continue
        keep.append(r.split("?")[0])
    return sorted(set(keep))


def main():
    if not preflight():
        return 2

    html_txt = open(HTML, encoding="utf-8").read() if os.path.exists(HTML) else ""

    # 1) SVG
    if re.search(r"\.svg", html_txt):
        errors.append("index.html 里引用了 .svg —— 游戏 UI 一律用 PNG")

    # 2) 引用文件是否存在
    missing = []
    for r in refs():
        if r.endswith("/"):
            continue
        if not os.path.exists(os.path.join(ROOT, r)):
            missing.append(r)
    if missing:
        errors.append("引用了但文件不存在：\n  " + "\n  ".join(missing))

    # 3) 切图四角是否透明
    opaque = []
    checked = 0
    for base, _, files in os.walk(os.path.join(ROOT, "pieces")):
        for f in files:
            if not f.lower().endswith(".png"):
                continue
            low = f.lower()
            if any(k in low for k in ALLOW_OPAQUE):
                continue
            p = os.path.join(base, f)
            try:
                got = read_png(p)
            except Exception:
                continue
            if not got:
                continue
            w, h, px = got
            checked += 1
            corners = [px[0][0], px[0][w - 1], px[h - 1][0], px[h - 1][w - 1]]
            if all(c[3] > 200 for c in corners):
                opaque.append(os.path.relpath(p, ROOT))
    # 四角不透明不一定是错：方形切图 + 容器圆角遮罩（border-radius + overflow:hidden）
    # 也是允许的做法。这里只提示，让人确认它确实叠在圆角容器里。
    if opaque:
        names = "、".join(sorted(os.path.basename(f) for f in opaque))
        warns.append(f"{len(opaque)} 张方形切图四角不透明（{names}）—— 需叠在 border-radius + overflow:hidden 的容器里")

    if checked == 0:
        errors.append("pieces/ 里一张 PNG 都没查到 —— 先确认切图是否已导出，空目录不算通过")

    # 4) 字体
    fonts_dir = os.path.join(ROOT, "fonts")
    if not os.path.isdir(fonts_dir) or not os.listdir(fonts_dir):
        errors.append("fonts/ 为空 —— 字体必须随项目打包，不能只靠 local()（见 AGENTS.md 字体流程）")
    elif not re.search(r"@font-face", html_txt):
        errors.append("fonts/ 有文件但 index.html 里没有 @font-face —— 字体不会生效")

    # 5) 视频体积
    for base, _, files in os.walk(os.path.join(ROOT, "video")):
        for f in files:
            if f.lower().endswith(".mp4"):
                mb = os.path.getsize(os.path.join(base, f)) / 1024 / 1024
                if mb > 25:
                    warns.append(f"{f} {mb:.1f}MB —— 首屏别 auto 预载")

    print(f"检查了 {checked} 张切图的四角透明度")
    for w in warns:
        print(f"[warn] {w}")
    if errors:
        for e in errors:
            print(f"[error] {e}")
        print("\n不通过。")
        return 1
    print("全绿。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
