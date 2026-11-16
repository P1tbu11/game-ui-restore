# game-ui-restore

一份无后门的决策 Spec，一套从 Figma 到页面的 5 步施工 SOP，四条可证伪硬规则，加三道零依赖标准库门禁。
**不绑定任何页面模板**——网格背包、扇形轮盘、抽卡演出、竖屏活动页通用。

## 一句话安装到新项目

在目标项目的根目录下直接运行（默认锁 `v3.0.0` 稳定版，不会覆盖你已有的 `INTAKE.json`）：

```bash
curl -fsSL https://raw.githubusercontent.com/P1tbu11/game-ui-restore/v3.0.0/install.sh | bash
```

或者只拉取规范包目录（用 Git Tag 锁版本）：

```bash
git clone --depth 1 -b v3.0.0 https://github.com/P1tbu11/game-ui-restore.git spec/game-ui-restore
```

## 目录结构

```
AGENTS.md                            给 Agent 开工前必读：准入关 + 5 步还原 SOP + 4 条硬规则（精简版）
SPEC.md                              完整还原流水线、坐标换算、切图四问、视频时序与验收标准
install.sh                           一键安装/升级门禁脚本与配置样板到业务项目根目录
templates/
  INTAKE.example.json                开工准入单样板（锁舞台/子画框倍率/通道实测/字体/组件变体清单）
  deploy.manifest.example.json       白名单打包清单样板（隔离 reference/ 与 baseline/，防 413）
  runtime_helpers.js                 可选的零 DOM 纯函数底座（top-left 稳态缩放 / 双路零黑帧视频池 / 防穿透跳过）
scripts/
  lint_assets.py                     门禁 1：准入单 + 动态引用死链 + 孤儿图 + 半透明整切 + 物理像素 + 字体 + 热区/可读性
  visual_check.py                    门禁 2：Figma 原稿半透明叠图校准（--against）+ 独立 Profile 多视图像素回归（--update/--check）
  build.py                           门禁 3：按 deploy.manifest.json 干净打包并卡住总包体积上限
```

## 任何 Agent 接新项目的标准闭环

1. **读规则 & 过准入关**：先读 `AGENTS.md`，解析 Figma URL（`node-id` 的 `-` 转 `:`），拉 `get_metadata` 与 Component Set 填好项目根 `INTAKE.json`；缺变体或字重先问用户。
2. **分块拉取 & 落页面**：导出整帧参考图放 `reference/<view>.png`，按区块分批调 `get_design_context`（防截断），按“外绝对、内流式”落舞台设计像素。
3. **跑四步门禁交付**：

```bash
python3 scripts/lint_assets.py                                # 1. 静态合规与切图物理质量（exit 0）
python3 scripts/visual_check.py --against reference/main.png  # 2. 与 Figma 原稿生成半透明叠图校准位置/字号
python3 scripts/visual_check.py --update                      # 3. 校准通过后锁 baseline/（后续改动跑 --check）
python3 scripts/build.py                                      # 4. 白名单干净打包 + 体积上限检查（exit 0）
```

## 版本策略

看两版差异：`git diff v2.0.0..v3.0.0 -- SPEC.md AGENTS.md`

| 改动性质 | 版本位 |
|---|---|
| 硬规则判据变更、`INTAKE.json` 必填结构或脚本退出码契约变更 | major |
| 新增检查子项、补充踩坑案例、纯函数增强 | minor / patch |
