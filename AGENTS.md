# 硬规则（Agent 开工必读）

做 Figma 游戏 UI 还原时，**写第一行代码前先过准入关，再按 5 步施工 SOP 推进**。详细判据和细节查 `SPEC.md`，判断只按本文。

---

## 0. 开工准入关（没写完 `INTAKE.json` 不许写 HTML/CSS）

拿到 Figma 链接后，第一步解析 `fileKey` 与 `nodeId`（URL 里 `node-id=1-2` 转为 `1:2`；分支 URL 取 `branch/:branchKey` 作 `fileKey`），在项目根建 `INTAKE.json`，填齐四件事：

1. **舞台与子画框换算**：主舞台 `stage: { w, h }` + 最小目标视口 `minViewport: { w, h }`；每个子页面画框写明 `{ key, nodeId, w, h, factor }`（`factor = 主舞台对应宽 / 子画框宽`）。
2. **组件变体清单**：跳去组件源页列出交互 Component Set 的 `nodeId` 与已存在的 `variants`。**列表里没有的状态或整页缺失设计稿，先向用户提问拿到确认记录，写入 `approvedFallbacks[]` 后才准动工**。
3. **取图通道实测**：拿一个小透明节点实测角落 `alpha == 0`，记录所用通道与日期。
4. **字体清单**：从 Figma Text Style 抄下真实家族名、字重与打包后的 `fonts/*.woff2` 文件名；找不到同字重字体，**立刻停下问用户**，不许拿相近字重或系统字顶替。

---

## 0.5 从 Figma 到页面的 5 步施工 SOP（防爆上下文、防跑偏）

1. **先树后块（严禁整页一把拉）**：先调 `get_metadata` 拿节点树，导出整帧 `get_screenshot` 存 `reference/<view>.png`（不进发布包）；再按大区块（顶栏 / 导航 / 列表 / 详情面板）分批调 `get_design_context`，防止百层画框被静默截断。
2. **三层定栈（背景 / UI / 演出分离）**：`#stage` 加 `isolation: isolate`（锁死内部 `mix-blend-mode` 不穿透舞台）；底层放全幅背景 JPG（`object-fit: cover`）与 `<video>`，中层放 `#screen` UI 层，顶层放全屏演出跳过层。
3. **归档切图与栅格化**：把导出的哈希临时图按语义重命名放进 `pieces/`（纯平铺噪点纹理放 `pieces/tex/`）；矢量图标用无头浏览器 `--default-background-color=00000000` 转透明 PNG。
4. **外绝对、内流式落坐标**：**大区块外框一律 `position: absolute`**，坐标严格取 `(子X - 父X) × factor`、`(子Y - 父Y) × factor`（注意：带投影/外发光的节点以视觉本体 Frame 框定位，勿被 `renderBounds` 外扩带偏）；仅等距重复列表内部用 `flex/grid + 精确 gap`，长列表容器加横向 `overflow-y: auto` 与隐藏滚动条；动态长文案预留 `white-space: nowrap` 或固定行数防撑破绝对定位框。
5. **先对原稿，再锁基线**：首版写完先跑 `visual_check.py --against reference/<view>.png` 生成半透明叠图与像素差异图，修正坐标/字号/行高/描边偏差直至与 Figma 原稿对齐，再跑 `--update` 锁定 `baseline/`。

---

## 1. 组件里没有的状态，不许造（无免责后门）

- 每个交互状态（选中、锁定、装备、hover、登场）都必须指到 `INTAKE.json` 里的一个 `variant` 或一张独立状态切图。
- 指不出来且不在 `approvedFallbacks[]` 里 → **停下来问**。
- **严禁**未经确认用 `box-shadow`（含 `inset`）、`filter: brightness/drop-shadow`、`mix-blend-mode` 自造选中态或点击闪烁，也**严禁**拿别的组件按钮硬塞顶替。
- **没有“标一句占位就能过关”的后门**：未写入 `approvedFallbacks[]` 的自造状态一律视为违规。

## 2. 不透明静态件整块切；半透明件与动态文本必分层

- **整块切图条件（同时满足）**：内部主体不透明 + 无动态变化的文字/数字 + 无位移变色动画。
  - 方形图（四角不透明）：外层容器**必须**有 `border-radius` + `overflow: hidden`，切图自身不烘圆角、不带外投影；禁止裸 `<img>` 直接加圆角。
  - 异形/圆角透明图：四角 `alpha == 0`，且**物理像素宽高 ≥ 舞台渲染宽高**（严禁把小倍率截图强拉放大）。
- **必须按设计值重画 / 分层**：
  - 半透明底板、空格子、分类底栏 → CSS 底色/圆角 + 独立平铺纹理层（纹理图放到 `pieces/tex/` 或在 `INTAKE.json` 登记 `allowedTranslucent`）。
  - 会随数据或交互变化的名称、等级、拥有数量 → **真 DOM 文本**，严禁烘死在切图里（注意游戏字体常见硬阴影与描边，需按 Figma Effects 还原 `text-shadow` / `-webkit-text-stroke`）。
- **禁 SVG 上屏**：不引 `.svg` 文件，也不写内联 `<svg>`。

## 3. 数值走统一舞台坐标，且受缩放可读与触控红线约束

- 舞台尺寸只从配置/数据读取，只做 `min(vw / stageW, vh / stageH)` 等比缩放（优先 `transform-origin: top left` + 显式居中位移 `tx, ty`，兼容嵌套宿主容器），布局写设计像素（禁用 `vw` / `rem`）。
- **缩放可读红线**：`设计字号 × minScale < 10px` 时必须向用户告警确认；若目标含手机竖屏而设计稿是 16:9/21:9 横屏，必须先向用户确认做“横屏锁定提示”还是索取竖屏稿，严禁自行响应式重排。
- **触控热区红线**：任何可点击元素在 `minScale` 下宽高 `< 44×44 CSS px` 时，必须用透明伪元素（`::after { inset: -Npx }`）外扩热区；`:hover` 必须包在 `@media (hover: hover)` 里，触屏改用 `pointerdown` 反馈，全局禁图像拖拽与文本误选。

## 4. 字体随包且字重精确，按钮显式继承

- `@font-face` 先写打包的 `url("fonts/xxx.woff2")`，再用系统真名 `local()` 兜底；首屏主字体在 `<head>` 加 `preload`（注意 `crossorigin`）。
- 全局重置必须包含 `button, input, select, textarea { font-family: inherit }`。

---

## 视频与重资产纪律（有视频/多页时必守）

- **格式与预载**：大图背景用 JPG（`export/`），透明件用 PNG（`pieces/`）；首屏仅当前激活的 1 支待机片允许 `preload="auto"`（且必带 `muted playsinline` 防移动端拦截），其余视频一律 `preload="metadata"`。
- **循环与切换**：切换一律硬切；无缝循环用主备双 `<video>` 交替，在距离结尾 `0.15s` 且备路 `readyState >= 3` 时从 `0` 帧顶上；切离当前页签立即 `pause()`。
- **全屏演出与打包**：演出隐藏 UI 层，用宏任务隔离触发点击，单击浮出返回箭头；上线只打 `deploy.manifest.json` 白名单文件（`reference/`、`baseline/`、`INTAKE.json` 均不进线上包）。

---

## 验收门禁（四步闭环才准交付）

```bash
python3 scripts/lint_assets.py                                  # 1. 静态合规 / 切图物理分辨率 / 半透明 / 孤儿图 / 字体 / 热区
python3 scripts/visual_check.py --against reference/main.png    # 2. 首版与 Figma 原稿叠图对位（输出 overlay + diff 核验坐标字号）
python3 scripts/visual_check.py --update                        # 3. 原稿对准后锁 baseline/；后续每次改动跑 --check 防回归
python3 scripts/build.py                                        # 4. 按 deploy.manifest.json 干净打包并校验总包体积上限
```
