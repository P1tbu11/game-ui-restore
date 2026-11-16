/* 页面、卡片、文案的唯一真源。
   加一个页签 = 往 pages 里加一条；换素材 = 改 img / 换 pieces 下的文件名。
   不要在这里写样式，样式属于 index.html 的变量区。 */
window.APP_DATA = {
  // 设计画布尺寸（Figma 画框的真实像素）。舞台按它等比缩放到窗口。
  canvas: { w: 2206, h: 946 },

  pages: [
    {
      key: 'page-a',
      title: '页签 A',
      // 每张卡：id（唯一）、name（名称，会显示在右侧信息里）、
      // 可选 img（切图相对路径，见下）、可选 owned（是否已拥有，用来筛锁定态）
      cards: [
        { id: 'a-1', name: '第一套', owned: true },
        { id: 'a-2', name: '第二套', owned: true },
        { id: 'a-3', name: '第三套', owned: false }
      ]
    },
    {
      key: 'page-b',
      title: '页签 B',
      cards: [
        { id: 'b-1', name: '第一件', owned: true },
        { id: 'b-2', name: '第二件', owned: true }
      ]
    }
  ]
};

/* 上了切图之后，每张卡加一个 img 字段，值是 pieces/ 下的相对路径，
   例如 card-1.png（不要写目录前缀，骨架会自动拼到 pieces/ 下）。
   视频同理：加 video 字段，切换选中时光标卡对应那支。 */
