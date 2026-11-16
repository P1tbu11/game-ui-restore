#!/usr/bin/env node
'use strict';
/**
 * gui-restore —— 游戏 UI 还原脚手架
 *
 *   gui-restore init <目录> [--assets <切图目录>] [--fonts <字体目录>] [--force]
 *   gui-restore -v
 *
 * 只做一件事：把模板（规则 + 脚本 + 骨架）铺到目标目录，
 * 可选地把切图和字体也搬进去。素材不会进包，所以包里只有几百 KB。
 */
const fs = require('fs');
const path = require('path');

const TEMPLATE = path.join(__dirname, '..', 'template');
const SKIP = new Set(['.DS_Store', 'Thumbs.db']);
const VERSION = require(path.join(__dirname, '..', 'package.json')).version;

function log(s) { process.stdout.write(s + '\n'); }
function die(s) { process.stderr.write(s + '\n'); process.exit(1); }

function copyTree(src, dst, filter) {
  let n = 0;
  const st = fs.statSync(src);
  if (st.isFile()) {
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
    return 1;
  }
  fs.mkdirSync(dst, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    if (SKIP.has(name)) continue;
    const s = path.join(src, name);
    const d = path.join(dst, name);
    if (filter && !filter(s, name)) continue;
    if (fs.statSync(s).isDirectory()) n += copyTree(s, d, filter);
    else { fs.copyFileSync(s, d); n++; }
  }
  return n;
}

function parse(argv) {
  const out = { cmd: null, dir: null, assets: null, fonts: null, force: false };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--assets') out.assets = argv[++i];
    else if (a === '--fonts') out.fonts = argv[++i];
    else if (a === '--force') out.force = true;
    else if (a === '-v' || a === '--version') out.cmd = 'version';
    else if (a === '-h' || a === '--help' || a === 'help') out.cmd = 'help';
    else if (!a.startsWith('-')) rest.push(a);
  }
  if (!out.cmd) { out.cmd = rest[0] || 'help'; out.dir = rest[1] || '.'; }
  if (out.cmd === 'init' && rest.length > 2) out.dir = rest[1];
  return out;
}

function usage() {
  log([
    'gui-restore ' + VERSION,
    '',
    '用法：',
    '  gui-restore init <目录> [--assets <切图目录>] [--fonts <字体目录>] [--force]',
    '',
    '  --assets   把这个目录里的切图复制到 <目录>/pieces/',
    '  --fonts    把这个目录里的字复制到 <目录>/fonts/',
    '  --force    目标目录已有 index.html 也覆盖（默认拒绝，防误伤）',
    '',
    '产物：规则文档（AGENTS.md 等）+ 构建脚本 + 能跑的最小骨架。',
    '素材和字体不在包里，必须自己带 —— 这是故意的。'
  ].join('\n'));
}

function main() {
  const opt = parse(process.argv.slice(2));

  if (opt.cmd === 'version') return log(VERSION);
  if (opt.cmd === 'help') return usage();
  if (opt.cmd !== 'init') {
    usage();
    return die('\n未知命令：' + opt.cmd);
  }

  const target = path.resolve(opt.dir);
  const entry = path.join(target, 'index.html');
  if (fs.existsSync(entry) && !opt.force) {
    die('目标目录里已经有 index.html，看起来是个现成项目：\n  ' + target +
        '\n\n换一个空目录，或加 --force 覆盖。我不会默默盖掉别人的东西。');
  }

  fs.mkdirSync(target, { recursive: true });
  const n = copyTree(TEMPLATE, target);
  log('模板已铺开：' + target);
  log('  文件：' + n + ' 个');

  let copied = 0;
  if (opt.assets) {
    const from = path.resolve(opt.assets);
    if (!fs.existsSync(from)) die('\n切图目录不存在：' + from);
    copied += copyTree(from, path.join(target, 'pieces'));
    log('  切图：' + copied + ' 个 → pieces/');
  }
  if (opt.fonts) {
    const from = path.resolve(opt.fonts);
    if (!fs.existsSync(from)) die('\n字体目录不存在：' + from);
    const f = copyTree(from, path.join(target, 'fonts'));
    log('  字体：' + f + ' 个 → fonts/');
  }

  log([
    '',
    '下一步：',
    '  1. 切图放进 pieces/，命名 <模块>-<部件>.png（不透明件整块切，半透明底板按设计值重画）',
    '  2. 字体放进 fonts/，在 index.html 里写 @font-face；找不到就停下来问，不要退回系统黑体',
    '  3. 改 data/app.js：画布尺寸、页签、卡片、文案',
    '  4. 跑 npm run lint —— 不绿不要往下走',
    '  5. npm run dev 本地看，npm run build 打包',
    '',
    '规则先读 AGENTS.md，它比这份提示更重要。'
  ].join('\n'));
}

main();
