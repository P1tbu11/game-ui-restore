# game-ui-restore

把 Figma 的游戏界面做成可交互、可发布、还能继续改的网页。
这个包是**规则 + 脚本 + 一个能跑的最小骨架**，不是成品页面。

## 为什么不发 zip 了

zip 的问题是没版本号：拿到手的包是第几版、跟上次差什么，全靠人记。
这里用 git tag 管版本，包本身按 npm 的形状写——以后有私有源，一条
`npm publish` 就能转过去，代码不用改。

## 装（走 git）

```bash
# 锁版本
git clone -b v1.0.0 <仓库地址> game-ui-restore
node game-ui-restore/bin/gui-restore.js init my-page

# 或者已经 clone 过，直接跑
node bin/gui-restore.js init ../my-page
```

以后有私有 registry，就换成：

```bash
npx @gameui/game-ui-restore@1.0.0 init my-page
```

## 用

```bash
node bin/gui-restore.js init <目录> \
  --assets ~/Downloads/cutout \   # 切图 → pieces/
  --fonts  ~/Downloads/fonts      # 字体 → fonts/
```

`init` 会拒绝覆盖已有 `index.html` 的目录（除非 `--force`），不会默默盖掉别人的项目。

铺完得到：

```
index.html            能跑的骨架：舞台缩放 + 页签 + 卡片选中
data/app.js           页面/卡片/文案的唯一真源
pieces/  fonts/       空目录，等你的素材（包里故意不带）
scripts/              lint_assets / build / deploy
AGENTS.md ...         规则文档（先读 AGENTS.md）
PROJECT.md            项目说明模板，填完给下一个窗口看
```

然后：

```bash
npm run lint     # 资源体检，不绿不要往下走
npm run dev      # 本地起个静态服务看效果
npm run build    # 打包到 /tmp
npm run deploy   # 上线（需要 with CLI）
```

## 骨架长什么样

不是成品 UI，是一副**可替换的架子**：

- 舞台固定设计尺寸、等比缩放到窗口，坐标一律写设计像素
- 页签和页面由 `data/app.js` 生成，加一页只加一条数据
- 卡片有选中模型，切页不串
- 没上切图时显示虚线占位块，写着「切图位」——它不会假装是游戏 UI

上了切图就把 `img` 字段填上，占位自动消失。

## 包里没有什么

- **切图**：几十 MB 的公司资产，进包就等于公开
- **字体**：商业授权字体，不能随包分发
- **样板项目**：那是一次具体还原的产物，参考价值在 `PAGE-CONTRACT.md` 里

这三样都靠 `--assets` / `--fonts` 由使用者自己带，或者从已有项目复制。

## 版本

语义化版本，tag 打 `v1.0.0` 这种形式：

| 变化 | 版本位 |
|---|---|
| 规则或骨架有不兼容改动（目录、数据字段重命名） | major |
| 加规则、加脚本、修脚本 bug | minor |
| 改文档措辞 | patch |

`npm run verify` 会自己铺一遍骨架、跑 lint 和 build，确认包本身是好的。

## 依赖

- Node ≥ 14（只用内置模块，没有 npm 依赖）
- Python 3（脚本只用标准库）
- 需要取 Figma 时另装 Figma MCP，见 `AGENTS.md`
