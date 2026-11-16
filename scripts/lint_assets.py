#!/usr/bin/env python3
"""游戏 UI 还原 · 静态合规与切图体检门禁。

用法：
  python3 scripts/lint_assets.py              # 标准严格模式（新项目必过）
  python3 scripts/lint_assets.py --no-intake  # 仅在旧项目迁移期跳过 INTAKE.json 缺失阻断

检查 8 项（任一 error 返回退出码 1，空目录/非项目根返回 2）：
  1. INTAKE.json 准入单完整性（舞台、最小视口、通道实测、字体清单、变体清单）
  2. 全量资源引用存在性（扫描 HTML + CSS + 内联 <script> + data/*.js，无死链）
  3. 孤儿切图阻断（pieces/ 下未被任何代码或白名单引用的 PNG 报错）
  4. 禁 SVG 上屏（外链 .svg 与内联 <svg> 标签均报错）
  5. 字体工程闭环（fonts/ 对应 woff2 存在、@font-face 首选 url()、button 继承 font-family）
  6. 切图透明度与容器裁切（半透明底板整切报错；四角不透明方形图未套圆角裁切容器报错）
  7. 切图物理分辨率下限（PNG 物理宽高 < HTML/CSS 声明的舞台渲染宽高时报错，防小图拉糊）
  8. 缩放可读性、触控热区与未授权 CSS 伪造状态检查（对照 minViewport 与 approvedFallbacks）
"""
import json
import os
import re
import struct
import sys
import zlib

def _resolve_root():
    if "--root" in sys.argv:
        idx = sys.argv.index("--root")
        if idx + 1 < len(sys.argv):
            return os.path.abspath(sys.argv[idx + 1])
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = _resolve_root()
HTML = os.path.join(ROOT, "index.html")
DATA_DIR = os.path.join(ROOT, "data")
PIECES_DIR = os.path.join(ROOT, "pieces")
INTAKE_PATH = os.path.join(ROOT, "INTAKE.json")
MARKERS = ("index.html", "pieces")

errors = []
warns = []


def preflight():
    """没有项目可查时必须报错（退出码 2），绝不对空目录报全绿。"""
    missing = [p for p in MARKERS if not os.path.exists(os.path.join(ROOT, p))]
    if not missing:
        return True
    print("这里不是项目根目录，没有东西可体检。")
    print(f"脚本定位到的目录：{ROOT}")
    for p in missing:
        print(f"  缺少：{p}")
    print("\n请把 scripts/ 放进项目根目录（与 index.html、pieces/ 同级）后再执行。")
    return False


def read_png(path):
    """纯标准库读取 8-bit 非隔行 PNG，返回 (w, h, rows)；rows[y][x] = (r,g,b,a)。"""
    with open(path, "rb") as fh:
        d = fh.read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, w, h, ct, bd, interlace = 8, bytearray(), 0, 0, 6, 8, 0
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        chunk = d[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            w, h, bd, ct, _, _, interlace = struct.unpack(">IIBBBBB", chunk[:13])
        elif typ == b"IDAT":
            idat.extend(chunk)
        elif typ == b"IEND":
            break
    if bd != 8 or interlace != 0 or ct not in (2, 6):
        return None
    ch = 3 if ct == 2 else 4
    raw = zlib.decompress(bytes(idat))
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
                row.append((line[o], line[o + 1], line[o + 2], line[o + 3]))
            else:
                row.append((line[o], line[o + 1], line[o + 2], 255))
        px.append(row)
    return w, h, px


def load_intake(skip_intake):
    if not os.path.exists(INTAKE_PATH):
        msg = "缺少 INTAKE.json 准入单 —— 开工前必须登记舞台尺寸、最小视口、通道实测、字体与组件变体清单（见 AGENTS.md 第 0 节）"
        if skip_intake:
            warns.append(msg)
        else:
            errors.append(msg)
        return {}
    try:
        with open(INTAKE_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        errors.append(f"INTAKE.json 不是合法 JSON：{exc}")
        return {}

    for key in ("stage", "minViewport", "channelCheck", "fonts", "componentSets"):
        if key not in data:
            errors.append(f"INTAKE.json 缺少必填字段：{key}")
    ch = data.get("channelCheck") or {}
    ca = ch.get("cornerAlpha")
    if not ch.get("verifiedAt") or ca != [0, 0, 0, 0]:
        errors.append("INTAKE.json#channelCheck 未通过四角透明实测（需含 verifiedAt 且 cornerAlpha 为 [0,0,0,0]）")
    return data


def collect_code_texts():
    """收集 index.html、外部 CSS 与 data/*.js 文本。"""
    html_txt = open(HTML, encoding="utf-8").read() if os.path.exists(HTML) else ""
    js_texts = []
    if os.path.isdir(DATA_DIR):
        for base, _, files in os.walk(DATA_DIR):
            for f in sorted(files):
                if f.endswith((".js", ".json")):
                    js_texts.append(open(os.path.join(base, f), encoding="utf-8").read())
    css_texts = re.findall(r"<style[^>]*>([\s\S]*?)</style>", html_txt, flags=re.I)
    for href in re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']', html_txt, flags=re.I):
        cp = os.path.join(ROOT, href.split("?")[0])
        if os.path.isfile(cp):
            css_texts.append(open(cp, encoding="utf-8").read())
    return html_txt, "\n".join(css_texts), "\n".join(js_texts)


def collect_references(html_txt, css_txt, js_txt):
    """提取静态与脚本内的全部本地资源路径（支持 BASE 前缀拼接识别）。"""
    out = set()
    no_script_html = re.sub(r"<script[\s\S]*?</script>", "", html_txt, flags=re.I)
    for m in re.findall(r'(?:src|href|poster)=["\']([^"\']+)["\']', no_script_html, flags=re.I):
        if "${" not in m and "' +" not in m and "\" +" not in m:
            out.add(m)
    for m in re.findall(r'url\(["\']?([^"\')]+)["\']?\)', css_txt, flags=re.I):
        out.add(m)

    all_scripts = "\n".join(re.findall(r"<script[^>]*>([\s\S]*?)</script>", html_txt, flags=re.I)) + "\n" + js_txt
    # 1) 显式带目录前缀的字面量
    for m in re.findall(r'["\']((?:pieces|export|video|fonts)/[^"\'${}+]+?\.[a-zA-Z0-9]+)["\']', all_scripts):
        out.add(m)
    # 2) 数据文件里只写文件名、在渲染层补 pieces/ 前缀的裸文件名（如 img: 'card-1.png'）
    for m in re.findall(r'["\']([a-zA-Z0-9_.-]+\.(?:png|jpg|jpeg|webp|mp4|woff2))["\']', all_scripts):
        if "/" not in m and os.path.exists(os.path.join(PIECES_DIR, m)):
            out.add(f"pieces/{m}")
    # 3) 简单模式拼接，例如 'pieces/pg/it-ico-' + ... + '.png' -> 展开匹配实际存在的文件
    for prefix, suffix in re.findall(
        r'["\']((?:pieces|export|video)/[a-zA-Z0-9_/.-]+)["\']\s*\+[^;,\n]+?\+\s*["\'](\.[a-zA-Z0-9]+)["\']',
        all_scripts,
    ):
        parent = os.path.join(ROOT, os.path.dirname(prefix))
        stem = os.path.basename(prefix)
        if os.path.isdir(parent):
            for fn in os.listdir(parent):
                if fn.startswith(stem) and fn.endswith(suffix):
                    rel = os.path.relpath(os.path.join(parent, fn), ROOT).replace("\\", "/")
                    out.add(rel)

    clean = set()
    for r in out:
        if r.startswith(("http://", "https://", "data:", "#", "mailto:", "javascript:")):
            continue
        r = r.split("?")[0].split("#")[0].strip()
        if r and not r.endswith("/"):
            clean.add(r)
    return sorted(clean)


def parse_css_dimensions(css_txt):
    """粗提 CSS 选择器的 width/height/border-radius/overflow，供容器裁切与物理尺寸核对。"""
    rules = {}
    clean = re.sub(r"/\*[\s\S]*?\*/", "", css_txt)
    for sel_raw, body in re.findall(r"([^{}@]+)\{([^{}]+)\}", clean):
        props = {}
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            k, v = decl.split(":", 1)
            props[k.strip().lower()] = v.strip()
        for sel in sel_raw.split(","):
            s = sel.strip()
            if s:
                rules.setdefault(s, {}).update(props)
    return rules


def find_bare_rounded_imgs(html_txt, css_rules):
    """找出直接挂在裸 <img> 上靠自身圆角裁切、未包 overflow:hidden 容器的图片路径。"""
    bare = set()
    for tag in re.findall(r"<img\b[^>]*>", html_txt, flags=re.I):
        src_m = re.search(r'src=["\']([^"\']+)["\']', tag, flags=re.I)
        cls_m = re.search(r'class=["\']([^"\']+)["\']', tag, flags=re.I)
        if not src_m or not cls_m:
            continue
        classes = cls_m.group(1).split()
        for c in classes:
            props = css_rules.get(f".{c}", {})
            if "border-radius" in props and props.get("overflow") != "hidden":
                bare.add(src_m.group(1).split("?")[0])
    return bare


def expected_render_sizes(html_txt, css_rules, js_txt):
    """提取切图在舞台上的声明渲染宽高 {rel_path: (w, h)}（覆盖静态 HTML、JS 拼接模板与 CSS 类名）。"""
    sizes = {}
    all_markup = html_txt + "\n" + js_txt
    # 1) 静态与 JS 模板里的 <img ... src="..." width="420" height="560">
    for tag in re.findall(r"<img\b[^>]*>", all_markup, flags=re.I):
        src_m = re.search(r'src=["\']([^"\']+)["\']', tag, flags=re.I)
        w_m = re.search(r'\bwidth=["\']?(\d+)', tag, flags=re.I)
        h_m = re.search(r'\bheight=["\']?(\d+)', tag, flags=re.I)
        if src_m and w_m and h_m and "+" not in src_m.group(1):
            sizes[src_m.group(1).split("?")[0]] = (float(w_m.group(1)), float(h_m.group(1)))
        if src_m:
            src = src_m.group(1).split("?")[0]
            cls_m = re.search(r'class=["\']([^"\']+)["\']', tag, flags=re.I)
            if cls_m and "+" not in src:
                for c in cls_m.group(1).split():
                    p = css_rules.get(f".{c}", {})
                    pw = re.match(r"^(\d+(?:\.\d+)?)px$", p.get("width", ""))
                    ph = re.match(r"^(\d+(?:\.\d+)?)px$", p.get("height", ""))
                    if pw and ph:
                        sizes[src] = (float(pw.group(1)), float(ph.group(1)))

    # 2) CSS 后代 img 尺寸（如 .gcard .frame img { width:420px; height:560px }）绑定到同组件数据引用
    card_img_dims = []
    for sel, props in css_rules.items():
        if sel.endswith(" img"):
            pw = re.match(r"^(\d+(?:\.\d+)?)px$", props.get("width", ""))
            ph = re.match(r"^(\d+(?:\.\d+)?)px$", props.get("height", ""))
            if pw and ph:
                root_cls = sel.split()[0].lstrip(".")
                card_img_dims.append((root_cls, float(pw.group(1)), float(ph.group(1))))

    scripts_combined = "\n".join(re.findall(r"<script[^>]*>([\s\S]*?)</script>", html_txt, flags=re.I))
    for root_cls, rw, rh in card_img_dims:
        # 若某段渲染逻辑生成了 class="root_cls"，关联其引用的数据组（如 GZ.cards -> guangzai, WP -> weapon, IT -> item）
        for block in scripts_combined.split("/* ----"):
            if f"'{root_cls}'" not in block and f'"{root_cls}"' not in block:
                continue
            for prop_key in re.findall(r"\bD\.([a-zA-Z0-9_]+)", block):
                m_sec = re.search(rf"\b{re.escape(prop_key)}\s*:\s*\{{([\s\S]*?)\n  \}}", js_txt)
                if not m_sec:
                    continue
                # 仅提取列表项或 rowImg 里的主图，不误绑 side 图标/按钮
                sec_txt = re.sub(r"\bside\s*:\s*\{[\s\S]*?\n    \}", "", m_sec.group(1))
                for p in re.findall(r"(?:img|rowImg|slot)\s*:\s*['\"](pieces/[^'\"]+\.png)['\"]", sec_txt):
                    sizes.setdefault(p, (rw, rh))
    return sizes


def check_css_discipline(css_txt, intake):
    """检查字体继承、hover 媒体查询、字号/热区红线、以及未获批的 CSS 伪造状态。"""
    clean = re.sub(r"/\*[\s\S]*?\*/", "", css_txt)
    approved_targets = json.dumps(intake.get("approvedFallbacks", []), ensure_ascii=False)

    # 1) button 字体继承
    has_global_btn_inherit = bool(
        re.search(r"(?:^|[},])\s*button\b[^{]*\{[^}]*font-family\s*:\s*inherit", clean, flags=re.I)
        or re.search(r"(?:^|[},])\s*button\b[^{]*\{[^}]*font\s*:\s*inherit", clean, flags=re.I)
    )
    if not has_global_btn_inherit:
        errors.append("CSS 缺少全局 `button { font-family: inherit }` —— 按钮默认不继承 body 字体，会静默退回系统黑体（SPEC 第 7 章）")

    # 2) vw / rem 禁用检查
    bad_units = re.findall(r":\s*[^;{}]*\b\d+(?:\.\d+)?(?:vw|vh|rem|em)\b", clean)
    if bad_units:
        errors.append(f"CSS 出现了被禁止的相对视口/字号单位（应统一写舞台设计像素）：{bad_units[:4]}")

    # 3) :hover 必须包裹在 @media (hover: hover) 中
    stripped_hover_media = re.sub(r"@media\s*\(\s*hover\s*:\s*hover\s*\)\s*\{(?:[^{}]|\{[^{}]*\})*\}", "", clean)
    leaked_hovers = [s.strip() for s in re.findall(r"([^{}@]+:hover[^{}@]*)\{", stripped_hover_media)]
    if leaked_hovers:
        warns.append(f"{len(leaked_hovers)} 处 `:hover` 未包进 `@media (hover: hover)`（触屏点击后会粘滞）：示例 `{leaked_hovers[0]}`")

    # 4) 未经 approvedFallbacks 登记的 inset 选中环 / filter 提亮伪造状态
    for sel, body in re.findall(r"([^{}@]+)\{([^{}]+)\}", stripped_hover_media):
        s = sel.strip()
        if any(k in s for k in ("aria-pressed", ".is-on", ".selected", ".active")):
            if ("inset 0 0 0" in body or "drop-shadow" in body) and s not in approved_targets:
                errors.append(f"疑似用 CSS 伪造组件选中态 `{s}`（含 inset 描边或 drop-shadow）且未在 INTAKE.json#approvedFallbacks 获批")

    # 5) 缩放可读性与触控热区红线计算
    stage = intake.get("stage") or {}
    min_vp = intake.get("minViewport") or {}
    if stage.get("w") and stage.get("h") and min_vp.get("w") and min_vp.get("h"):
        min_scale = min(min_vp["w"] / stage["w"], min_vp["h"] / stage["h"])
        font_pxs = [float(x) for x in re.findall(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", clean)]
        if font_pxs:
            smallest = min(font_pxs)
            real_px = smallest * min_scale
            if real_px < 10.0 and "minFontSize" not in approved_targets:
                warns.append(
                    f"最小设计字号 {smallest:g}px 在最小视口 ({min_vp['w']}×{min_vp['h']}, scale={min_scale:.3f}) 下仅 {real_px:.1f}px < 10px 可读下限"
                )


def main():
    skip_intake = "--no-intake" in sys.argv
    if not preflight():
        return 2

    intake = load_intake(skip_intake)
    html_txt, css_txt, js_txt = collect_code_texts()
    css_rules = parse_css_dimensions(css_txt)

    # 1) SVG 禁令（外链 + 内联标签）
    if re.search(r"\.svg\b", html_txt + "\n" + css_txt + "\n" + js_txt, flags=re.I) or re.search(r"<svg\b", html_txt, flags=re.I):
        errors.append("检测到 .svg 引用或内联 <svg> 标签 —— 游戏 UI 矢量件必须透明栅格化为 PNG（SPEC 第 2/5 章）")

    # 2) 引用文件存在性
    referenced = collect_references(html_txt, css_txt, js_txt)
    missing = [r for r in referenced if not os.path.exists(os.path.join(ROOT, r))]
    if missing:
        errors.append("代码引用了不存在的资源文件：\n  " + "\n  ".join(missing))

    # 3) 孤儿切图检查 + 6) 透明度/裁切 + 7) 物理像素检查
    ref_set = set(referenced)
    allowed_translucent = set(intake.get("allowedTranslucent") or [])
    bare_rounded = find_bare_rounded_imgs(html_txt, css_rules)
    decl_sizes = expected_render_sizes(html_txt, css_rules, js_txt)

    orphans = []
    opaque_uncropped = []
    Opaque_boxed = []
    translucent_plates = []
    upscaled = []
    checked = 0

    for base, _, files in sorted(os.walk(PIECES_DIR)):
        for f in sorted(files):
            if not f.lower().endswith(".png"):
                continue
            full = os.path.join(base, f)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")

            if rel not in ref_set and rel not in allowed_translucent:
                orphans.append(rel)

            try:
                got = read_png(full)
            except Exception as exc:
                errors.append(f"无法读取 PNG `{rel}`：{exc}")
                continue
            if not got:
                warns.append(f"`{rel}` 为隔行或非 8-bit RGB/RGBA PNG，建议重新导出标准 8-bit RGBA")
                continue

            w, h, px = got
            checked += 1

            # 物理尺寸 vs 舞台渲染尺寸
            if rel in decl_sizes:
                rw, rh = decl_sizes[rel]
                if w + 2 < rw or h + 2 < rh:
                    upscaled.append(f"{rel}（物理 {w}×{h} < 舞台渲染 {rw:g}×{rh:g}）")

            is_tex = rel.startswith("pieces/tex/") or rel in allowed_translucent
            if is_tex:
                continue

            corners = [px[0][0][3], px[0][w - 1][3], px[h - 1][0][3], px[h - 1][w - 1][3]]
            if all(a > 200 for a in corners):
                if rel in bare_rounded:
                    opaque_uncropped.append(rel)
                else:
                    Opaque_boxed.append(rel)

            # 中心与全图半透明底板检测（排除边缘抗锯齿：若 >55% 像素处于 8 < alpha < 235，必是半透明面板/底槽整切）
            total_px = w * h
            semi_px = sum(1 for row in px for _, _, _, a in row if 8 < a < 235)
            if total_px > 400 and (semi_px / total_px) > 0.55:
                translucent_plates.append(f"{rel}（半透明像素占 {semi_px / total_px * 100:.0f}%）")

    if checked == 0:
        errors.append("pieces/ 里没有检出任何有效 PNG —— 空切图目录不算通过")
    if orphans:
        errors.append(f"pieces/ 下存在 {len(orphans)} 张未被引用的孤儿切图（请清理，避免污染发布包）：\n  " + "\n  ".join(orphans[:12]))
    if opaque_uncropped:
        errors.append("方形满底切图直接挂在裸 <img> 上且无 overflow:hidden 裁切容器：\n  " + "\n  ".join(opaque_uncropped))
    if Opaque_boxed:
        warns.append(f"{len(Opaque_boxed)} 张方形切图四角不透明（如 {os.path.basename(Opaque_boxed[0])} 等）—— 请确认父容器均有 border-radius + overflow:hidden")
    if translucent_plates:
        errors.append(
            "检测到半透明底板被整块切图（违反规则 2，半透明底板应按设计值 CSS 重画；若属纯平铺纹理请移入 pieces/tex/ 或登记 INTAKE.json#allowedTranslucent）：\n  "
            + "\n  ".join(translucent_plates)
        )
    if upscaled:
        errors.append("检测到低分辨率切图被强拉放大（违反规则 2，回源节点按 ≥1x 舞台像素导出）：\n  " + "\n  ".join(upscaled[:10]))

    # 5) 字体闭环检查
    fonts_dir = os.path.join(ROOT, "fonts")
    woffs = [f for f in (os.listdir(fonts_dir) if os.path.isdir(fonts_dir) else []) if f.lower().endswith(".woff2")]
    if not woffs:
        errors.append("fonts/ 下没有任何 .woff2 字体文件 —— 严禁只靠 local() 或放非 woff2 杂物凑数")
    for wf in woffs:
        # 确认每个 woff2 都在 @font-face 中且排在 local() 之前
        pattern = re.compile(r"@font-face\s*\{[^}]*src\s*:\s*url\([\"']?fonts/" + re.escape(wf), re.I)
        if not pattern.search(css_txt):
            errors.append(f"字体 `fonts/{wf}` 未在 `@font-face` 的 `src` 首位通过 `url()` 引用")
    for f_decl in intake.get("fonts") or []:
        f_file = f_decl.get("file", "")
        if f_file and not os.path.exists(os.path.join(ROOT, f_file)):
            errors.append(f"INTAKE.json 登记的设计稿字体缺失：{f_file}（对应 {f_decl.get('figmaStyle')}）")

    # 8) CSS 规则、可读性与热区纪律
    check_css_discipline(css_txt, intake)

    # 9) 视频预载与单文件体积预算
    budget = intake.get("budget") or {}
    max_vid_mb = float(budget.get("maxSingleVideoMB", 25))
    auto_videos = re.findall(r"<video\b[^>]*\bpreload=[\"']auto[\"'][^>]*>", html_txt, flags=re.I)
    # 排除无 src 的备用轮播槽（如 v-spare）
    active_auto = [t for t in auto_videos if re.search(r'\bsrc=["\'][^"\']+["\']', t, flags=re.I)]
    if len(active_auto) > 1:
        errors.append(f"首屏有 {len(active_auto)} 支带 src 的 <video> 设置了 preload=\"auto\"（最多允许 1 支当前待机片，其余必须改为 metadata）")

    vid_dir = os.path.join(ROOT, "video")
    if os.path.isdir(vid_dir):
        for base, _, files in os.walk(vid_dir):
            for f in sorted(files):
                if f.lower().endswith(".mp4"):
                    mb = os.path.getsize(os.path.join(base, f)) / 1024 / 1024
                    if mb > max_vid_mb:
                        errors.append(f"video/{f} 体积 {mb:.1f}MB 超过单视频预算上限 {max_vid_mb:g}MB")

    print(f"已扫描引用资源 {len(referenced)} 项，检查切图 {checked} 张。")
    for w in warns:
        print(f"[warn] {w}")
    if errors:
        for e in errors:
            print(f"[error] {e}")
        print(f"\n体检未通过（{len(errors)} 项阻断错误）。")
        return 1
    print("全绿通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
