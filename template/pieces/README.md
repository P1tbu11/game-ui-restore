# pieces/ —— 切图

命名：`<模块>-<部件>.png`，例如 `card-1.png`、`btn-confirm.png`、`ico-star.png`。

三条要求：

1. **不透明件整块切**，外层用 `border-radius` + `overflow:hidden` 收角，切图里不要自己烘圆角。
2. **半透明底板不要切**，按设计值重画；整图导出会把透明区压成实色。
3. **四角 alpha = 0**（除非它就是要被圆角容器裁住的方图）。`npm run lint` 会查。

字号、颜色、圆角一律写设计稿真值，不要目测。
