# 游戏 UI 高保真还原 · Spec

把 Figma 里的游戏界面还原成可交互、可发布的网页。
这份文档不提供固定版式的 HTML 模板，只提供三样跨项目真正复用的东西：**从 Figma 到页面的施工 SOP** + **不会自欺的决策规则** + **能阻断违规的机器门禁**。

---

## 0. 适用边界

**适用**：从 Figma 还原高保真、带交互状态与演出的游戏 UI（背包、商店、角色养成、抽卡结算、活动主界面、轮盘等）。

**为什么不给页面模板**：网格卡、轮盘、竖屏堆叠没有公用 DOM 结构；硬套页面模板一定在偷偷裁设计稿比例。但**Figma 分块拉取、坐标换算、切图物理纪律、字体防回退、双路视频无缝循环、与原稿叠图对位、白名单打包**与版式无关——这些全部收敛为 SOP、硬规则和脚本门禁。

---

## 1. 开工准入关（`INTAKE.json`）

拿到 Figma 链接后、写第一行代码前，先完成 URL 解析与全局勘探，在项目根生成 `INTAKE.json`。没有它，`lint_assets.py` 直接拒绝通过。

- **URL 解析规则**：`figma.com/design/:fileKey/:name?node-id=12-34` → `nodeId` 必须把 `-` 转成 `:`（即 `12:34`）；若链接含 `/branch/:branchKey/`，一律取 `branchKey` 作为 `fileKey`。

```json
{
  "stage": { "w": 4680, "h": 2160 },
  "minViewport": { "w": 844, "h": 390 },
  "frames": [
    { "key": "main", "nodeId": "5418:10001", "w": 4680, "h": 2160, "factor": 1.0 },
    { "key": "sub",  "nodeId": "5418:20001", "w": 2741, "h": 1265, "factor": 1.7073 }
  ],
  "views": [
    { "key": "main", "query": "?page=main", "figmaRef": "reference/main.png" }
  ],
  "channelCheck": {
    "verifiedAt": "2026-11-16",
    "method": "get_design_context assetPathPrefix",
    "sampleNode": "5418:11205",
    "cornerAlpha": [0, 0, 0, 0]
  },
  "fonts": [
    { "figmaStyle": "HYYouYuan-95J", "family": "HY95", "file": "fonts/HYYouYuan95J.woff2" }
  ],
  "componentSets": [
    { "name": "Card", "nodeId": "5418:11200", "variants": ["selected=off", "selected=on", "locked=true"] }
  ],
  "approvedFallbacks": [
    { "target": "subTab:equipSkin", "missing": "整页暂无设计稿", "decision": "禁用页签并标敬请期待", "approvedBy": "user" }
  ],
  "allowedTranslucent": ["pieces/tex/panel-noise.png"],
  "budget": { "maxSingleVideoMB": 25, "maxTotalPackageMB": 50 }
}
```

**准入四问（缺一不可）**

1. **所有页面的画框尺寸一致吗？** 同一份 Figma 常混着 `4680×2160` 的主画框和被缩成 `0.585x` 的子画框。开工前先锁定主舞台 `stage`，算出每个子画框的换算系数 `factor = 主舞台对应宽 / 子画框宽`。
2. **交互组件有哪些真实变体？** 注意页面画框里摆的只是 `INSTANCE`（实例），必须追溯到主组件集（Component Set）抄全 `variants`。没画 `hover`、没画 `equipped`、或某页签没设计稿，**当场向用户提问**，结论记进 `approvedFallbacks`。
3. **当前取图通道带真 alpha 吗？** 拿一个小透明节点实测四角 `alpha == 0` 并记录日期。
4. **字体精确字重齐了吗？** 对照 Text Style 核对字重（如 `95J` 不能拿 `95W` 静默替代），缺字立刻停下索取。

---

## 2. 从 Figma 到页面的 5 步还原流水线（施工 SOP）

任何 Agent 拿到通过准入的 Figma 节点后，按以下固定顺序把它变成页面：

### Step 1 · 先树后块拉设计数据（防大画框截断）
- **严禁直接对整页根画框只调一次 `get_design_context`**：游戏 UI 动辄上千节点，单次拉取会被截断漏掉深层图标与描边参数。
- **标准动作**：
  1. 对目标画框调 `get_screenshot` 存为 `reference/<view>.png`（只做对位标尺，不进发布包）；
  2. 对目标画框调 `get_metadata` 拿到顶层分区节点 ID（如顶栏、左侧页签、中间列表、右侧详情、底部操作栏）；
  3. **逐个分区节点**调用 `get_design_context` 读取精确坐标、字号、色值、圆角、混合模式与原始图层资源；
  4. **把参考输出当数据源，不当终稿代码**：Figma MCP 吐出的 Tailwind / Flex 代码不能原样照抄，必须按第 3–6 章规则转成舞台设计像素与切图分层。

### Step 2 · 搭三层定栈舞台（防混合模式穿透与层级打架）
- `#stage` 必须加 `isolation: isolate`（否则内部面板的 `mix-blend-mode: lighten / overlay` 会直接穿透舞台与宿主黑底混色导致偏色）。
- 固定分三层 `z-index`：
  - `z-index: 0` 背景层（全屏 3D 渲染底图用 `export/*.jpg` + `object-fit: cover`，待机/登场 `<video>` 叠在其上）；
  - `z-index: 2` 主 UI 层 `#screen`（所有业务区块挂在这里，全屏演出时整体切换 `.ui-off`）；
  - `z-index: 3` 演出浮层（如单击才浮出的无文字跳过箭头）。

### Step 3 · 导出归档切图与矢量栅格化
- 按第 6 章四问筛子，把 `get_design_context` 导出的哈希临时图按区域语义重命名归入 `pieces/`（如 `pieces/card-1.png`）；可平铺的半透明材质噪点图单独归入 `pieces/tex/`。
- Figma 里的纯矢量图形/图标（星标、箭头、属性小标），用本地无头 Chrome 带 `--default-background-color=00000000` 渲染成≥舞台尺寸的透明 PNG，落盘后删除临时 SVG。

### Step 4 · 外绝对、内流式落坐标（防 Flex 挤压漂移与阴影偏移）
- **大区块外框一律用 `position: absolute`**：`left = round((节点X - 父容器X) × factor)`，`top = round((节点Y - 父容器Y) × factor)`，显式写死 `width` 和 `height`。**禁止**对顶层分区用自适应 `justify-content: space-between` 猜间距。
- **警惕阴影/发光撑大包围盒**：Figma 带 Drop Shadow 或 Outer Glow 的节点，其渲染导出图尺寸（`renderBounds`）比布局框（`absoluteBoundingBox`）大一圈。若切图带了发光外扩，定位时必须减去外扩边距，让视觉本体对齐布局框。
- **重复项内部用流式 + 精确步进**：网格卡片、属性行内部用 `display: flex / grid` + 设计稿精确 `gap`。装饰点线等重复背景的周期必须取**父项节距的整数分之⼀**（如页签节距 `264px` → 点距 `264 / 3 = 88px`），消除累积误差。
- **滚动与文本溢出防线**：卡片网格或列表若超出可视高度，容器加 `overflow-y: auto; scrollbar-width: none`（隐藏原生丑滚动条）并用 `clip-path` 或内边距留出选中外环余量，防止第 1 张卡的选中外环被 `overflow` 切掉上边缘；单行标题必加 `white-space: nowrap`，多行描述必锁 `width` 与 `line-height`。
- **游戏字体特效还原**：Figma 文字上的 Effects（硬投影如 `0 4px 0 #41403d`、柔光阴影、外描边）必须逐项转成 `text-shadow` 或 `paint-order: stroke fill; -webkit-text-stroke`，裸写纯色字会让游戏 UI 瞬间丧失质感且在亮底上发虚。

### Step 5 · 先跟 Figma 原稿叠图校准，再锁回归基线
- 首版写完后，先跑 `python3 scripts/visual_check.py --against reference/<view>.png --view <view>`。
- 打开生成的 `baseline/overlay-<view>.png`（50% 半透明叠图）与 `baseline/figma-diff-<view>.png`，逐行核查文字基线、图标中心、圆角与间距是否重合（浏览器与 Figma 字体抗锯齿在边缘有 `1~2px` 细微差异属正常，但整体位移 `> 2px` 必须修回设计值）。
- 对齐无误后，再执行 `python3 scripts/visual_check.py --update` 锁定网页回归基线。

---

## 3. 四条硬规则与证伪判据

每条规则都绑定唯一证伪条件——第三方只需跑脚本或核对 `INTAKE.json` 就能一句话判定违规。

| # | 硬规则 | 一句话证伪条件（满足任一即判违规） |
|---|---|---|
| 1 | **组件里没有的状态，不许造** | 代码中出现未经 `INTAKE.json#approvedFallbacks` 登记的 CSS 伪造状态（`box-shadow` 描边、`filter` 提亮/发光、跨组件借图顶替），或交互态指不到 `componentSets` 里的变体/独立切图。 |
| 2 | **静态不透明件整块切；半透明与动态文本必分层** | ① 切图内部含大面积半透明底板（未登记为独立纹理层）；② 动态业务文本/数量被烘进切图；③ 方形切图外层缺 `border-radius + overflow:hidden`；④ 切图物理像素 `<` 舞台渲染像素；⑤ 页面出现 `.svg` 引用或 `<svg>` 标签。 |
| 3 | **统一设计像素缩放，守住可读与触控下限** | ① 舞台宽高写死在多处或布局混用 `vw`/`rem`；② `minScale` 下正文等效字号 `< 10px` 且未在 `approvedFallbacks` 确认；③ 可点击控件在 `minScale` 下触控热区 `< 44×44 CSS px`；④ `:hover` 未包裹 `@media (hover: hover)`。 |
| 4 | **字体随包、字重精确、控件显式继承** | ① `INTAKE.json#fonts` 任一 `.woff2` 缺失或未在 `@font-face` 首选引用；② 用相近字重冒充且未获批；③ 缺少 `button { font-family: inherit }` 导致按钮回退系统字。 |

---

## 4. 坐标系、跨画框对齐与真机下限

**舞台等比缩放（兼容嵌套宿主容器的写法）**

```js
// transform-origin: top left 配合显式居中偏移 tx/ty，即使外层被宿主 iframe 再套一层缩放也不会漂移
const s = Math.min(window.innerWidth / stage.w, window.innerHeight / stage.h);
const tx = (window.innerWidth - stage.w * s) / 2;
const ty = (window.innerHeight - stage.h * s) / 2;
stageEl.style.transformOrigin = 'top left';
stageEl.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
```

- **单一真源**：`stage.w / stage.h` 从配置或数据注入 CSS 变量与缩放函数，不在 CSS 多处硬编码。
- **缩放可读性下限**：设 `minScale = min(minViewport.w / stage.w, minViewport.h / stage.h)`。例如 `4680×2160` 缩到 `844×390` 手机横屏时 `minScale ≈ 0.1803`，设计稿 `< 56px` 的字在手机上即跌破 `10px`，必须在开工时向用户确认。若设计稿是横屏而用户要在手机打开，必须确认加**竖屏旋转提示遮罩**或另要竖屏稿，严禁自行流式重排。
- **触控热区与防误触**：所有满足 `designSize × minScale < 44` 的可点元素，用 `::after { content: ""; position: absolute; inset: -Npx }` 外扩透明热区；桌面悬停包进 `@media (hover: hover)`，触屏反馈走 `pointerdown`；全局给 UI 层加 `user-select: none; -webkit-user-drag: none` 防止真机长按拖出图片幽灵残影。

---

## 5. 状态与多视图管线（只管生命周期，不管版式）

1. **状态三问**：每个状态写清**谁触发、谁持有、切走/筛选后怎么回落**（如选中项被筛掉时自动回落首个可见项并收起关联按钮；叠加态层级以设计稿为准）。
2. **多视图互不串状态**：每个独立页签或弹窗各自持有选择状态；缺设计稿的页签按 `approvedFallbacks` 禁用或出明确占位，**严禁把多个页签偷偷指向同一个视图实例**。
3. **持久化用稳定唯一键**：`localStorage` 记忆状态必须用显式唯一 `id`，禁数组下标或重名拼接键。
4. **URL 直达静止态**：所有一级视图或核心弹窗必须支持查询参数直达（如 `?page=weapon`），直达时跳过首次长动画、停在确定性首帧，供 `visual_check.py` 无头截图。

---

## 6. 切图与分层决策树 + 取图通道

拿到任何一个视觉部件，按顺序过四道筛子：

1. **有随数据或交互变化的文字/数字吗？** 有（名称、等级、拥有数 `×10`、货币数）→ **底图与文字必拆层**，严禁把可变数字烘进格子切图。
2. **主体是半透明的，还是会变色/形变的？** 是（`rgba` 半透明底板、空格子框、分类底栏）→ **CSS 重画底色/圆角/描边 + `pieces/tex/` 独立平铺纹理层**，严禁整块切半透明大图；全幅不透明场景底图走 `export/*.jpg`（省 70% 体积），不放 `pieces/`。
3. **方形满底还是透明边角？** 方形满底（四角 `alpha == 255`）必须套 `<span class="frame"><img ...></span>` 由 `.frame` 设 `border-radius + overflow: hidden`，切图自身不烘圆角，严禁裸 `<img>` 自裁圆角。
4. **物理像素够不够？** PNG 物理宽高 **必须 ≥ 主舞台设计像素宽高**，严禁从小倍率子画框切小图强拉放大。

**取图通道（验证基线：2026-11，每次开工必实测）**

| 取图方式 | 透明通道表现 | 适用场景 |
|---|---|---|
| `get_design_context` 原始图层资源 | 保留原始真 alpha | 独立图标、按钮底板、卡片立绘、纹理层（**首选**） |
| 隐藏背景层后导出的纯净 UI 图层 PNG | 保留真 alpha（注意画框缩放倍率） | 成组静态件像素扫描裁切（须保证物理像素 ≥ 舞台像素） |
| `get_screenshot` / 带背景整帧导出 | 透明区压成实色（`alpha=255`） | **严禁做切图**，仅存入 `reference/` 作叠图校准标尺 |
| 无头 Chrome `--default-background-color=00000000` | 保留真 alpha | Figma 矢量图标转高清 PNG（页面内禁引 SVG） |

> 注意：若单张不透明图标外围残留极淡矩形底（`alpha` 约 `1~15`），只对该图标外围透明区做清理；**严禁对全局跑 `alpha ≤ 32` 一刀切清零**，否则会抹空 10% 噪点纹理与柔光边缘。

---

## 7. 字体工程

1. **精确字重 + 首屏预载**：按 Figma Text Style 找齐同字重字体转 `.woff2` 放 `fonts/`；首屏主字体在 `<head>` 加 `<link rel="preload" href="fonts/xxx.woff2" as="font" type="font/woff2" crossorigin>`（注：`file://` 直接双击打开时 `preload crossorigin` 可能报 CORS，验收与预览一律走本地 HTTP 服务）。
2. **加载顺序与控件继承**：`@font-face` 的 `src` 第一位必写 `url("fonts/xxx.woff2")`，后跟系统真名 `local(...)`；CSS Reset 必写 `button, input, select, textarea { font-family: inherit }`。
3. **缺字即停**：找不到同字重字体立刻停下问用户，获批后记入 `INTAKE.json#approvedFallbacks`。

---

## 8. 动效、视频与资产预算

1. **预算与预载分级**：单支 MP4 默认 `≤ 25MB`，发布 zip 整包默认 `≤ 50MB`（防网关 `413`）；首屏仅 1 支激活待机片设 `preload="auto"`（必加 `muted playsinline`），其余一律 `preload="metadata"`，切中再 `.load()`。
2. **零黑帧切换与双路循环**：背景视频切换一律硬切（防双层半透明透出黑底）；循环播放禁用原生 `loop`，用隐藏备用 `<video>` 在主路距结尾 `0.15s` 且备路 `readyState >= 3` 时归零接力；切走页签立即 `pause()`。
3. **全屏演出防穿透**：点卡片进登场时加 `.ui-off` 隐藏 UI，用 `setTimeout(..., 0)` 隔离当次点击；演出中首次单击才浮出返回箭头，再点箭头或播完恢复 UI。

---

## 9. 四步验收门禁（对准原稿 + 阻断违规 + 防回归）

```bash
# 1. 静态合规、切图物理分辨率、半透明整切、孤儿图、字体与热区检查（必 exit 0）
python3 scripts/lint_assets.py

# 2. 首版与 Figma 原稿截图叠图校准（产出 baseline/overlay-<view>.png 供核验位置与字号）
python3 scripts/visual_check.py --against reference/main.png --view main

# 3. 原稿核验无误后锁基线；后续每次改动跑 --check 防把旧页面改坏（必 exit 0）
python3 scripts/visual_check.py --update
python3 scripts/visual_check.py --check

# 4. 按 deploy.manifest.json 白名单干净打包并卡住总包体积上限（必 exit 0）
python3 scripts/build.py
```

---

## 10. 常见坑速查表

| 现象 | 根因 | 规范解法 |
|---|---|---|
| 大界面深层图标、描边在还原时漏了 | 对整页根画框单次调 `get_design_context` 被截断 | 先 `get_metadata` 拿分区树，再按区块分批拉取 |
| 带发光/投影的按钮比设计稿往右下偏了几 px | 拿包含阴影外扩的 `renderBounds` 当布局坐标 | 定位以 `absoluteBoundingBox` 为准，减去阴影外扩量 |
| 第一排卡片选中时，选中外环上边缘被切平 | 网格滚动容器 `overflow` 直接贴卡片顶边裁切 | 容器留内边距或外扩 `clip-path` 给外环留余量 |
| 面板里的噪点混合模式把底下背景视频烧亮了 | `#stage` 或面板容器未隔离层叠上下文 | `#stage` 与独立合成面板显式加 `isolation: isolate` |
| 切图四周米色/灰边，或半透明面板发闷发死 | 用了整帧截图当切图；或把半透明底板整块裁了 | 走原始图层真 alpha；半透明底板 CSS 重画 + 纹理拆层 |
| 扣减道具数量后，左侧格子数字没变 | 动态数量被烘死在了格子切图里 | 底图与可变数字拆层，数字用真 DOM 叠放 |
| 子页面卡片发糊、描边发虚 | 从 `0.58x` 子画框切了 `246px` 图强拉到 `420px` | 算清 `factor`，回源节点导出 `≥ 420px` 的真分辨率切图 |
| 手机点不准按钮，或点完一直卡在放大高亮态 | 缩放后热区 `< 44px`；`:hover` 在触屏粘滞 | `::after` 外扩热区；`:hover` 包进 `@media (hover: hover)` |
| 视频循环/切换闪黑，或发布报 `413` | 原生 `loop` 空窗/交叉淡入透底；过程稿混入发布包 | 双路 `<video>` 提前 `0.15s` 接力 + 硬切；只走 `build.py` 打包 |

---

## 11. 规范包交付形态与零版式底座

```
SPEC.md                  完整施工 SOP、决策树与验收标准（本文档）
AGENTS.md                给 Agent 开工前注入上下文的准入关 + 5 步 SOP + 4 条硬规则
templates/               零版式配置样板（INTAKE.example.json + deploy.manifest.example.json + runtime_helpers.js）
scripts/lint_assets.py   静态合规、切图物理分辨率、半透明整切、孤儿图与热区/可读性门禁
scripts/visual_check.py  Figma 原稿叠图校准（--against）+ 独立 Profile 多视图像素回归（--update/--check）
scripts/build.py         清单驱动干净打包与整包体积门禁
```
