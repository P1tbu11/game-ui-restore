#!/usr/bin/env python3
"""无头浏览器多视图截图、Figma 原稿叠图校准 & 像素级防回归门禁（纯标准库，零第三方依赖）。

三种模式：
  1. 与 Figma 原稿叠图校准（首版还原必跑）：
     python3 scripts/visual_check.py --against reference/main.png [--view main]
     自动按原稿长宽比渲染当前页面，生成：
       - baseline/overlay-<view>.png     （50% 原稿 + 50% 页面半透明叠图，肉眼秒看字号/坐标偏了几 px）
       - baseline/figma-diff-<view>.png  （超过容差的像素用亮玫红标出）

  2. 锁定回归基线（与 Figma 原稿对齐无误后执行）：
     python3 scripts/visual_check.py --update

  3. 后续改动防回归（改任何样式或新增页签后必跑）：
     python3 scripts/visual_check.py --check [--views main,sub]
"""
import functools
import http.server
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import zlib


def _resolve_root():
    if "--root" in sys.argv:
        idx = sys.argv.index("--root")
        if idx + 1 < len(sys.argv):
            return os.path.abspath(sys.argv[idx + 1])
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = _resolve_root()
INTAKE_PATH = os.path.join(ROOT, "INTAKE.json")
BASELINE_DIR = os.path.join(ROOT, "baseline")

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome",
    "chromium",
    "chromium-browser",
]


def find_browser():
    for c in CHROME_CANDIDATES:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
        found = shutil.which(c)
        if found:
            return found
    return None


def read_png_rgba(path):
    with open(path, "rb") as fh:
        d = fh.read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"不是有效 PNG：{path}")
    pos, idat, w, h, ct, bd = 8, bytearray(), 0, 0, 6, 8
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        chunk = d[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", chunk[:10])
        elif typ == b"IDAT":
            idat.extend(chunk)
        elif typ == b"IEND":
            break
    if bd != 8 or ct not in (2, 6):
        raise ValueError(f"仅支持 8-bit RGB/RGBA PNG：{path}")
    ch = 3 if ct == 2 else 4
    raw = zlib.decompress(bytes(idat))
    stride = w * ch
    prev = bytearray(stride)
    out = []
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
        prev = line
        row = bytearray(w * 4)
        if ch == 4:
            row[:] = line
        else:
            for x in range(w):
                row[x * 4:x * 4 + 4] = bytes((line[x * 3], line[x * 3 + 1], line[x * 3 + 2], 255))
        out.append(row)
    return w, h, out


def resize_nearest(w, h, rows, tw, th):
    """当 Figma 导出截图与浏览器视口分辨率成倍数差异时，重采样到统一尺寸以便叠图比对。"""
    if (w, h) == (tw, th):
        return rows
    out = []
    for y in range(th):
        sy = min(h - 1, int(y * h / th))
        srow = rows[sy]
        drow = bytearray(tw * 4)
        for x in range(tw):
            sx = min(w - 1, int(x * w / tw))
            drow[x * 4:x * 4 + 4] = srow[sx * 4:sx * 4 + 4]
        out.append(drow)
    return out


def write_png_rgba(path, w, h, rows):
    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    raw = bytearray()
    for r in rows:
        raw.append(0)
        raw.extend(r)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


def compare_and_render(ref_path, cur_path, diff_out_path, overlay_out_path=None, channel_tol=8):
    rw, rh, rrows = read_png_rgba(ref_path)
    cw, ch, crows = read_png_rgba(cur_path)
    if (rw, rh) != (cw, ch):
        if overlay_out_path is not None:
            rrows = resize_nearest(rw, rh, rrows, cw, ch)
            rw, rh = cw, ch
        else:
            return 1.0, f"尺寸不一致：基线 {rw}×{rh} vs 当前 {cw}×{ch}"

    changed = 0
    diff_rows = []
    ov_rows = [] if overlay_out_path else None
    for y in range(rh):
        rr, cr = rrows[y], crows[y]
        dr = bytearray(rw * 4)
        orow = bytearray(rw * 4) if overlay_out_path else None
        for x in range(rw):
            o = x * 4
            if overlay_out_path:
                orow[o] = (rr[o] + cr[o]) >> 1
                orow[o + 1] = (rr[o + 1] + cr[o + 1]) >> 1
                orow[o + 2] = (rr[o + 2] + cr[o + 2]) >> 1
                orow[o + 3] = 255
            if (
                abs(rr[o] - cr[o]) > channel_tol
                or abs(rr[o + 1] - cr[o + 1]) > channel_tol
                or abs(rr[o + 2] - cr[o + 2]) > channel_tol
                or abs(rr[o + 3] - cr[o + 3]) > channel_tol
            ):
                changed += 1
                dr[o:o + 4] = b"\xff\x20\x40\xff"
            else:
                dr[o:o + 4] = bytes((cr[o] >> 2, cr[o + 1] >> 2, cr[o + 2] >> 2, 255))
        diff_rows.append(dr)
        if overlay_out_path:
            ov_rows.append(orow)

    ratio = changed / (rw * rh)
    if changed > 0 or overlay_out_path:
        write_png_rgba(diff_out_path, rw, rh, diff_rows)
    if overlay_out_path:
        write_png_rgba(overlay_out_path, rw, rh, ov_rows)
    return ratio, f"差异像素 {changed}/{rw * rh} ({ratio * 100:.2f}%)"


def load_config():
    cfg = {"viewport": (1560, 720), "views": [{"key": "default", "query": ""}], "maxDiffRatio": 0.001}
    if os.path.exists(INTAKE_PATH):
        intake = json.load(open(INTAKE_PATH, encoding="utf-8"))
        st = intake.get("stage") or {}
        if st.get("w") and st.get("h"):
            scale = min(1600.0 / st["w"], 900.0 / st["h"])
            cfg["viewport"] = (round(st["w"] * scale), round(st["h"] * scale))
        if intake.get("views"):
            cfg["views"] = intake["views"]
        if "maxDiffRatio" in intake:
            cfg["maxDiffRatio"] = float(intake["maxDiffRatio"])
    if "--views" in sys.argv:
        raw = sys.argv[sys.argv.index("--views") + 1]
        cfg["views"] = [{"key": k.strip(), "query": f"?page={k.strip()}"} for k in raw.split(",") if k.strip()]
    return cfg


def start_local_server():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

    handler = functools.partial(QuietHandler, directory=ROOT)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port


def capture(browser, url, out_png, vw, vh):
    profile = tempfile.mkdtemp(prefix="gui-restore-chrome-")
    try:
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--mute-audio",
            "--force-device-scale-factor=1",
            f"--user-data-dir={profile}",
            f"--window-size={vw},{vh}",
            "--virtual-time-budget=1200",
            f"--screenshot={out_png}",
            url,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
        if res.returncode != 0 or not os.path.exists(out_png):
            raise RuntimeError(res.stderr.decode("utf-8", "ignore")[-400:])
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def run_against_figma(browser, cfg):
    idx = sys.argv.index("--against")
    ref_arg = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
    ref_path = ref_arg if os.path.isabs(ref_arg) else os.path.join(ROOT, ref_arg)
    if not os.path.isfile(ref_path):
        print(f"[error] 找不到 Figma 原稿截图：{ref_path}")
        return 1

    view_key = cfg["views"][0]["key"]
    query = cfg["views"][0].get("query", "")
    if "--view" in sys.argv:
        view_key = sys.argv[sys.argv.index("--view") + 1]
        matched = [v for v in cfg["views"] if v["key"] == view_key]
        query = matched[0].get("query", f"?page={view_key}") if matched else f"?page={view_key}"

    rw, rh, _ = read_png_rgba(ref_path)
    scale = min(1920.0 / rw, 1080.0 / rh, 1.0)
    vw, vh = max(320, round(rw * scale)), max(240, round(rh * scale))

    os.makedirs(BASELINE_DIR, exist_ok=True)
    httpd, port = start_local_server()
    try:
        cur_png = os.path.join(BASELINE_DIR, f".render-{view_key}.png")
        overlay_png = os.path.join(BASELINE_DIR, f"overlay-{view_key}.png")
        diff_png_path = os.path.join(BASELINE_DIR, f"figma-diff-{view_key}.png")
        capture(browser, f"http://127.0.0.1:{port}/index.html{query}", cur_png, vw, vh)
        # 与 Figma 原稿比对容差设 20（过滤字体渲染引擎边缘抗锯齿，聚焦位移/漏件/错色）
        ratio, detail = compare_and_render(ref_path, cur_png, diff_png_path, overlay_out_path=overlay_png, channel_tol=20)
        os.remove(cur_png)
        print(f"[against-figma] 视图 `{view_key}` vs `{os.path.relpath(ref_path, ROOT)}`：{detail}")
        print(f"  半透明叠图：baseline/overlay-{view_key}.png")
        print(f"  像素差异图：baseline/figma-diff-{view_key}.png")
        return 0
    finally:
        httpd.shutdown()


def main():
    has_against = "--against" in sys.argv
    mode = "--update" if "--update" in sys.argv else ("--check" if "--check" in sys.argv else None)
    if (not has_against and not mode) or not os.path.exists(os.path.join(ROOT, "index.html")):
        print("用法：")
        print("  python3 scripts/visual_check.py --against reference/main.png [--view main]")
        print("  python3 scripts/visual_check.py --update")
        print("  python3 scripts/visual_check.py --check")
        return 2

    browser = find_browser()
    if not browser:
        print("[error] 未找到本机 Chrome / Chromium / Edge，无法执行无头截图门禁。")
        return 1

    cfg = load_config()
    if has_against:
        return run_against_figma(browser, cfg)

    vw, vh = cfg["viewport"]
    os.makedirs(BASELINE_DIR, exist_ok=True)
    httpd, port = start_local_server()
    failures = 0

    try:
        for v in cfg["views"]:
            key = v["key"]
            q = v.get("query", "")
            url = f"http://127.0.0.1:{port}/index.html{q}"
            base_png = os.path.join(BASELINE_DIR, f"{key}.png")

            if mode == "--update":
                capture(browser, url, base_png, vw, vh)
                print(f"[updated] baseline/{key}.png ({vw}×{vh})")
            else:
                if not os.path.exists(base_png):
                    print(f"[error] 缺少基线图 baseline/{key}.png —— 请先与 Figma 原稿校准后执行 --update")
                    failures += 1
                    continue
                tmp_png = os.path.join(BASELINE_DIR, f".cur-{key}.png")
                diff_out = os.path.join(BASELINE_DIR, f"diff-{key}.png")
                capture(browser, url, tmp_png, vw, vh)
                ratio, detail = compare_and_render(base_png, tmp_png, diff_out)
                os.remove(tmp_png)
                if ratio > cfg["maxDiffRatio"]:
                    print(f"[fail] 视图 `{key}` 回归超标：{detail} > 阈值 {cfg['maxDiffRatio']*100:.2f}%（差异图：baseline/diff-{key}.png）")
                    failures += 1
                else:
                    if os.path.exists(diff_out):
                        os.remove(diff_out)
                    print(f"[pass] 视图 `{key}`：{detail}")
    finally:
        httpd.shutdown()

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
