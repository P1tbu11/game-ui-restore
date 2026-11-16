#!/usr/bin/env node
'use strict';
/**
 * 包自检：真的铺一遍骨架，再跑 lint / build，确认这个包是能用的。
 *
 *   npm run verify
 *
 * 只测「包本身」——不测设计还原得好不好，那件事没有自动判据。
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const PKG = path.join(__dirname, '..');
const BIN = path.join(PKG, 'bin', 'gui-restore.js');
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'gui-restore-'));
const PROJ = path.join(TMP, 'proj');

// 1×1 全透明 PNG，用来喂 lint 的四角检查
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64'
);

let failed = 0;
function ok(msg) { console.log('  ok   ' + msg); }
function bad(msg, detail) {
  failed++;
  console.log('  FAIL ' + msg);
  if (detail) console.log('       ' + String(detail).trim().split('\n').join('\n       '));
}
function run(args, cwd) {
  return spawnSync(process.execPath, args, { cwd: cwd || PKG, encoding: 'utf8' });
}
function py(args, cwd) {
  return spawnSync('python3', args, { cwd, encoding: 'utf8' });
}

function main() {
  // ---- 准备夹具：一张切图、一个占位字体 ----
  const fxAssets = path.join(TMP, 'fx-assets');
  const fxFonts = path.join(TMP, 'fx-fonts');
  fs.mkdirSync(fxAssets, { recursive: true });
  fs.mkdirSync(fxFonts, { recursive: true });
  fs.writeFileSync(path.join(fxAssets, 'card-1.png'), PNG);
  fs.writeFileSync(path.join(fxFonts, 'demo.woff2'), 'not-a-real-font');

  console.log('铺骨架');
  const init = run([BIN, 'init', PROJ, '--assets', fxAssets, '--fonts', fxFonts]);
  if (init.status !== 0) return bad('init 失败', init.stderr);

  const must = [
    'index.html',
    'data/app.js',
    'scripts/lint_assets.py',
    'scripts/build.py',
    'deploy.manifest.json',
    'AGENTS.md',
    'WORKFLOW.md',
    'PAGE-CONTRACT.md',
    'PROJECT.md',
    path.join('pieces', 'card-1.png'),
    path.join('fonts', 'demo.woff2')
  ];
  const miss = must.filter(function (f) { return !fs.existsSync(path.join(PROJ, f)); });
  if (miss.length) bad('骨架缺文件：' + miss.join(', '));
  else ok('骨架文件齐全（' + must.length + ' 项）');

  if (fs.existsSync(path.join(PROJ, 'pieces', 'README.md'))) ok('pieces 说明随模板带上了');
  else bad('pieces/README.md 没带上');

  // ---- 护栏：不许覆盖已有项目 ----
  const again = run([BIN, 'init', PROJ]);
  if (again.status !== 0 && /已经有 index\.html/.test(again.stderr)) ok('拒绝覆盖已有 index.html');
  else bad('没有拦住覆盖', again.stderr || again.stdout);

  // ---- lint 的第一道门：有字体但没 @font-face，必须报错 ----
  console.log('lint');
  const l1 = py(['scripts/lint_assets.py'], PROJ);
  if (l1.status === 1 && /@font-face/.test(l1.stdout + l1.stderr)) ok('缺 @font-face 时 exit 1');
  else bad('缺 @font-face 却没报错', 'exit=' + l1.status + '\n' + l1.stdout + l1.stderr);

  // ---- 补上 @font-face 后应当全绿 ----
  const htmlPath = path.join(PROJ, 'index.html');
  const rule = '\n<style>@font-face{font-family:"Demo";src:url("fonts/demo.woff2") format("woff2")}</style>\n';
  fs.writeFileSync(htmlPath, fs.readFileSync(htmlPath, 'utf8').replace('</head>', rule + '</head>'));

  const l2 = py(['scripts/lint_assets.py'], PROJ);
  if (l2.status === 0 && /全绿/.test(l2.stdout)) ok('素材齐了之后 lint 通过');
  else bad('素材齐了仍不通过', 'exit=' + l2.status + '\n' + l2.stdout + l2.stderr);

  // ---- build：应当打出包，且文件数对得上 ----
  console.log('build');
  const out = path.join(TMP, 'site.zip');
  const b = py(['scripts/build.py', '--out', out], PROJ);
  if (b.status === 0 && fs.existsSync(out) && fs.statSync(out).size > 0) {
    ok('打包成功（' + (fs.statSync(out).size) + ' 字节）');
  } else {
    bad('打包失败', 'exit=' + b.status + '\n' + b.stdout + b.stderr);
  }

  // ---- 空目录必须自己解释，而不是抛堆栈 ----
  console.log('错误路径');
  const empty = path.join(TMP, 'empty');
  fs.mkdirSync(empty, { recursive: true });
  fs.mkdirSync(path.join(empty, 'scripts'), { recursive: true });
  fs.copyFileSync(path.join(PROJ, 'scripts', 'lint_assets.py'), path.join(empty, 'scripts', 'lint_assets.py'));
  const l3 = py(['scripts/lint_assets.py'], empty);
  if (l3.status === 2 && /不是项目根目录/.test(l3.stdout)) ok('不在项目根时给出人话提示');
  else bad('空目录提示不对', 'exit=' + l3.status + '\n' + l3.stdout + l3.stderr);

  console.log('');
  if (failed) {
    console.log('不通过：' + failed + ' 项。临时目录留在 ' + TMP);
    process.exit(1);
  }
  console.log('全部通过。临时目录：' + TMP);
  fs.rmSync(TMP, { recursive: true, force: true });
}

main();
