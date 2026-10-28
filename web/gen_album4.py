# -*- coding: utf-8 -*-
"""网页相册 v4：仿安卓相册（时间轴 + 相册 + 多选 + 大图操作）。"""
import os
import shutil
import re
import io
import json
import time
import html
import hashlib
import subprocess
import sys

try:
    from trash_page import build_trash_page
except Exception:
    def build_trash_page(_out):
        return 0
    
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

# ---------------- 配置（开源版：路径不再写死） ----------------
# 优先级：环境变量 > 脚本同目录 album_config.json > 默认值
_CFG = {}
try:
    _cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'album_config.json')
    if os.path.exists(_cfg_path):
        _CFG = json.load(io.open(_cfg_path, encoding='utf-8'))
except Exception:
    _CFG = {}

_here = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('ALBUM_ROOT') or _CFG.get('root') or os.path.join(os.path.dirname(_here), 'photos')
FF = os.environ.get('FFMPEG') or _CFG.get('ffmpeg') or 'ffmpeg'

OUT = os.environ.get('ALBUM_OUT') or _CFG.get('out') or os.path.join(ROOT, '相册')
PHOTO_ROOT = os.path.join(ROOT, '05_收件箱', '手机相册')
CAMERA_DIR = os.path.join(ROOT, '05_收件箱', '手机照片')
GALLERY_DIR = os.path.join(PHOTO_ROOT, 'Gallery', 'owner')
RECYCLE = os.path.join(ROOT, '06_回收站')
IMG = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.heic', '.gif'}
VID = {'.mp4', '.mov', '.3gp', '.mkv', '.avi'}
THUMB_W = 480
CREATE_NO_WINDOW = 0x08000000
TEMPLATE_VER = 'v125'
REGENERATED = False

SOURCES = [
    ('相机', CAMERA_DIR, set()),
    ('手机相册', GALLERY_DIR, set()),
    ('手机图片', PHOTO_ROOT, {'Gallery'}),
]

# 这些分组本身就是平铺目录，整体算一个相册，不按子目录拆
FLAT_GROUPS = {'相机'}

CSS = r"""
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:#0d0d0e;color:#ededef;font-family:-apple-system,"HarmonyOS Sans SC","PingFang SC","Microsoft YaHei",sans-serif;
     padding-bottom:66px;overscroll-behavior-y:contain}
body.idx{overflow:hidden}
.viewer .page{display:none!important}
header{position:fixed;top:0;left:0;right:0;height:54px;z-index:20;background:#0d0d0ef7;
       backdrop-filter:blur(16px);display:flex;align-items:center;padding:0 16px;
       border-bottom:1px solid #ffffff0f}
.title{font-size:20px;font-weight:700;letter-spacing:.2px}
main{padding:2px 14px 24px}
.pager{position:fixed;top:54px;bottom:58px;left:0;right:0;width:200%;display:flex;
  transition:transform .26s cubic-bezier(.22,.8,.3,1);will-change:transform;touch-action:pan-y}
.pane-page{width:50%;height:100%;overflow-y:auto;overflow-x:hidden;-webkit-overflow-scrolling:touch}
.pad{padding:2px 14px 26px}
.pane-page .mhead{position:sticky;top:0;z-index:5;background:#0d0d0e;padding:12px 0 9px;margin:0 2px}
body.selmode .pager{top:64px}
.mhead{display:flex;align-items:baseline;justify-content:space-between;margin:20px 2px 9px}
.mhead b{font-size:16px;font-weight:650}
.mhead span{font-size:12.5px;color:#78787d}
.grid{display:grid;grid-template-columns:repeat(var(--cols,3),1fr);gap:3px}
.grid a{display:block;aspect-ratio:1;overflow:hidden;border-radius:6px;background:#17171a;position:relative}
.grid a:active{opacity:.85}
.grid img{width:100%;height:100%;object-fit:cover;display:block;opacity:0;transition:opacity .2s}
.grid img.ld{opacity:1}
.grid .play{position:absolute;right:5px;bottom:5px;background:#000000a8;border-radius:10px;
            padding:0 6px;font-size:10.5px;color:#fff;line-height:16px;backdrop-filter:blur(4px)}
.albums{display:grid;grid-template-columns:repeat(auto-fill,minmax(106px,1fr));gap:11px}
.gtitle{font-size:13px;color:#8e8e93;margin:20px 2px 10px;font-weight:600}
#newalb input{display:block;width:100%;margin:6px 0 14px;padding:11px 13px;border-radius:10px;
  border:1px solid #ffffff1f;background:#1b1b1f;color:#ededef;font-size:15px;outline:none}
#newalb input:focus{border-color:#3a7afe}
.acard.pend{opacity:.55}
.acard.pend .c{color:#7a7a80}
.emptyalb{margin:80px 20px;text-align:center;color:#8a8a90;font-size:14px;line-height:2}
.emptyalb span{font-size:12px;color:#5f5f66}
.acard{display:block;text-decoration:none;color:#ededef;background:transparent;border-radius:12px;overflow:hidden;
       -webkit-touch-callout:none;user-select:none}
.acard img{-webkit-user-drag:none}
.acard.drag-origin{display:none}
.acard.drag-clone{position:fixed;z-index:200;pointer-events:none;margin:0;
  transform-origin:top left;box-shadow:0 12px 30px #000000a8;opacity:.97;
  border-radius:12px;background:#161619}
.sort-placeholder{background:#0a84ff14;border:2px dashed #0a84ff80;
  border-radius:12px;box-sizing:border-box;pointer-events:none}
.acard:active{opacity:.8}
.acard img{width:100%;aspect-ratio:1;object-fit:cover;display:block;border-radius:12px;background:#17171a;
           opacity:0;transition:opacity .2s}
.acard img.ld{opacity:1}
.acard .m{padding:7px 2px 0}
.acard .n{font-size:13.2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:500}
.acard .c{font-size:11.5px;color:#78787d;margin-top:1px}
nav{position:fixed;bottom:0;left:0;right:0;height:58px;background:#161619f2;backdrop-filter:blur(18px);
    border-top:1px solid #ffffff0f;display:flex;z-index:30;padding-bottom:4px}
nav div{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
        gap:3px;font-size:10.5px;color:#6f6f74}
nav div.on{color:#0a84ff}
nav svg{width:23px;height:23px;stroke:currentColor;fill:none;stroke-width:1.8;
        stroke-linecap:round;stroke-linejoin:round}
.bar{position:sticky;top:0;background:#0d0d0ef2;backdrop-filter:blur(16px);padding:13px 14px;
     z-index:20;display:flex;align-items:center;gap:12px;border-bottom:1px solid #ffffff0f}
.bar a{color:#0a84ff;text-decoration:none;font-size:17px;line-height:1}
.bar .t{flex:1;font-size:17px;font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar .n{color:#78787d;font-size:12.5px}
.viewer{position:fixed;inset:0;background:#000;display:none;z-index:99;
        align-items:center;justify-content:center;touch-action:pan-y}
.viewer.on{display:flex}
.viewer .strip{position:absolute;top:0;left:0;height:100%;width:300%;
  display:flex;transform:translateX(-33.33333%);will-change:transform}
.viewer .pane{width:33.33333%;height:100%;flex:none;display:flex;
  align-items:center;justify-content:center;overflow:hidden}
.viewer .pane img,.viewer .pane video{max-width:100%;max-height:100%;object-fit:contain}
.viewer .pane img{touch-action:none;transform-origin:center center;will-change:transform}
.viewer .nav2{position:absolute;top:0;bottom:0;width:34%;display:flex;align-items:center;
              color:#ffffff26;font-size:30px;user-select:none}
.viewer .prev{left:0;justify-content:flex-start;padding-left:8px}
.viewer .next{right:0;justify-content:flex-end;padding-right:8px}
.viewer .page{position:absolute;top:18px;left:0;right:0;text-align:center;color:#a8a8ad;font-size:12.5px;
              letter-spacing:.3px}
.viewer.on{animation:vfade .22s ease}
.viewer img.swl{animation:slideL .26s cubic-bezier(.22,.8,.3,1)}
.viewer img.swr{animation:slideR .26s cubic-bezier(.22,.8,.3,1)}
@keyframes vfade{0%{opacity:0}100%{opacity:1}}
@keyframes slideL{0%{opacity:.25;transform:translateX(30px)}100%{opacity:1;transform:translateX(0)}}
@keyframes slideR{0%{opacity:.25;transform:translateX(-30px)}100%{opacity:1;transform:translateX(0)}}
.viewer .close{position:absolute;top:10px;right:16px;color:#fff;font-size:27px;z-index:3;line-height:1}
.acts{position:absolute;bottom:0;left:0;right:0;display:flex;justify-content:space-around;
  padding:16px 0 30px;background:linear-gradient(to top,#000000e0,#00000000);z-index:3}
.acts .it{display:flex;flex-direction:column;align-items:center;gap:6px;color:#fff;font-size:11px;
  background:none;border:none;padding:6px 10px;border-radius:14px;letter-spacing:.3px}
.acts .it:active{background:#ffffff1f}
.acts .it.danger{color:#ff7a7a}
.acts,.viewer .page{transition:opacity .18s ease}
.viewer.ui-off .acts,.viewer.ui-off .page{opacity:0;pointer-events:none}
.acts svg{width:24px;height:24px;stroke:currentColor;fill:none;stroke-width:1.8;
  stroke-linecap:round;stroke-linejoin:round}
.grid a{box-shadow:inset 0 0 0 0 #0a84ff00;
  transition:box-shadow .22s ease,transform .22s cubic-bezier(.34,1.3,.64,1)}
.grid a::after{content:"";position:absolute;inset:0;background:#0a84ff3d;border-radius:6px;
  opacity:0;transition:opacity .2s ease;pointer-events:none}
.grid a.sel{box-shadow:inset 0 0 0 2.5px #0a84ff;transform:scale(.9);
  animation:selIn .22s cubic-bezier(.34,1.3,.64,1)}
.grid a.sel::after{opacity:1;animation:fadeIn .2s ease}
@keyframes selIn{0%{transform:scale(1)}100%{transform:scale(.9)}}
@keyframes fadeIn{0%{opacity:0}100%{opacity:1}}
@keyframes popIn{0%{opacity:0;transform:scale(.2)}70%{opacity:1;transform:scale(1.15)}100%{opacity:1;transform:scale(1)}}
.grid a .dur{position:absolute;right:4px;bottom:4px;z-index:2;background:#000000b0;
  color:#fff;font-size:10.5px;line-height:1.2;padding:1px 5px;border-radius:5px;letter-spacing:.2px}
#stat{display:flex;align-items:center;gap:5px;font-size:11px;color:#8a8a90;margin-right:8px}
#stat i{width:6px;height:6px;border-radius:50%;background:#3ecf8e;display:block}
#stat.warn i{background:#f0a020}
#stat.warn span{color:#f0a020}
#syncsheet,#newalb{position:fixed;inset:0;z-index:120;display:flex;align-items:flex-end}
#syncsheet .msk,#newalb .msk{position:absolute;inset:0;background:#0008}
#syncsheet .bx,#newalb .bx{position:relative;width:100%;background:#17171a;border-radius:16px 16px 0 0;
  padding:16px 16px 22px;color:#ededef;box-shadow:0 -8px 30px #0006}
#syncsheet h3,#newalb h3{margin:0 0 4px;font-size:15.5px}
#syncsheet p,#newalb p{margin:7px 0;font-size:12.5px;color:#9a9aa0;line-height:1.55}
#syncsheet .btns,#newalb .btns{display:flex;gap:8px;margin-top:14px}
#syncsheet button,#newalb button{flex:1;padding:11px 6px;border-radius:10px;border:1px solid #ffffff1f;
  background:#ffffff10;color:#e6e6ea;font-size:13.5px}
#syncsheet button.main,#newalb button.main{background:#2f6bff22;border-color:#2f6bff66;color:#9dbcff}
#syncsheet label{display:flex;align-items:center;gap:8px;margin-top:12px;font-size:12.5px;color:#9a9aa0}
#stat{cursor:pointer}
#toast{position:fixed;left:50%;bottom:88px;transform:translateX(-50%);background:#000000d0;color:#fff;
  padding:9px 14px;border-radius:10px;font-size:13px;z-index:200;opacity:0;transition:opacity .18s;pointer-events:none}
#toast.on{opacity:1}
#newbar{position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:150;display:flex;gap:10px;
  align-items:center;background:#2f6bff;color:#fff;border-radius:999px;padding:8px 14px;font-size:13px;
  box-shadow:0 6px 20px #2f6bff55;cursor:pointer}
#newbar b{font-weight:600;text-decoration:underline}
#offbar{position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:150;display:flex;gap:10px;
  align-items:center;background:#b3261e;color:#fff;border-radius:999px;padding:8px 14px;font-size:13px;
  box-shadow:0 6px 20px #b3261e55;cursor:pointer}
#upbar{position:fixed;left:50%;top:56px;transform:translateX(-50%);z-index:160;display:none;gap:10px;
  align-items:center;background:#1f7a52;color:#fff;border-radius:999px;padding:8px 14px;font-size:13px;
  box-shadow:0 6px 20px #1f7a5255;max-width:92vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#netov{position:fixed;inset:0;z-index:300;background:#0f0f10f5;display:flex;align-items:center;
  justify-content:center;padding:24px}
#netov .bx{max-width:340px;text-align:center;color:#ededef}
#netov .ic{font-size:38px;line-height:1;margin-bottom:10px}
#netov h3{margin:0 0 8px;font-size:17px}
#netov p{margin:6px 0;font-size:13px;color:#9a9aa0;line-height:1.6}
#netov .cd{color:#6f6f76;font-size:12px}
#netov .btns{margin-top:16px}
#netov button{padding:10px 22px;border-radius:10px;border:1px solid #ffffff2a;background:#ffffff12;
  color:#ededef;font-size:14px}
img.ph{background:#1b1b1f;opacity:.35}
.hact{display:flex;align-items:center;gap:2px}
.hact span{width:32px;height:32px;display:flex;align-items:center;justify-content:center;
  color:#c9c9cf;font-size:13px;font-weight:600;letter-spacing:.2px}
.hact span:active{background:#ffffff14;border-radius:8px}
#sbar{position:fixed;top:0;left:0;right:0;height:54px;z-index:30;display:none;
  align-items:center;gap:9px;padding:0 12px;background:#0d0d0ef7;backdrop-filter:blur(16px)}
#sbar.on{display:flex}
#sbar input{flex:1;background:#1c1c1f;border:1px solid #ffffff14;border-radius:9px;
  color:#ededef;padding:8px 12px;font-size:14px;outline:none;-webkit-appearance:none}
#sbar b{color:#7aa7ff;font-size:14px;font-weight:500}
.chips{display:flex;gap:8px;padding:10px 2px 6px;overflow-x:auto;-webkit-overflow-scrolling:touch}
.chips::-webkit-scrollbar{display:none}
/* 只保留自绘滚动条：把浏览器原生滚动条全部隐藏，否则右边缘会出现两条 */
.pane-page::-webkit-scrollbar,#g::-webkit-scrollbar,body::-webkit-scrollbar,
html::-webkit-scrollbar,#timeline::-webkit-scrollbar,.wrap::-webkit-scrollbar{width:0;height:0;display:none}
.pane-page,#g,body,html,#timeline,.wrap{scrollbar-width:none;-ms-overflow-style:none}
.chips b{flex:none;font-size:12.5px;font-weight:500;color:#b8b8be;background:#ffffff10;
  border:1px solid #ffffff14;border-radius:14px;padding:5px 12px;letter-spacing:.2px}
.chips b.on{color:#0d0d0e;background:#e8e8ec;border-color:#e8e8ec;font-weight:600}
.grid a .fav{position:absolute;left:5px;top:5px;z-index:2;color:#ff5d6c;font-size:13px;
  text-shadow:0 1px 3px #000a}
.otd .mhead{cursor:pointer;align-items:center}
.otd .mhead b{color:#ff8f9a}
.otd .chev{font-style:normal;color:#78787d;font-size:15px;margin-left:6px;transition:transform .18s}
.otd.collapsed .grid{display:none}
.otd.collapsed .chev{transform:rotate(-90deg)}
.trashrow{display:flex;gap:10px;margin:4px 0 10px}
.trashbar{flex:1;display:flex;align-items:center;gap:8px;padding:11px 14px;
  background:#1b1b1f;border:1px solid #ffffff12;border-radius:11px;color:#c9c9cf;
  font-size:13.5px;text-decoration:none}
.trashbar span{flex:1}
.managebar{display:flex;align-items:center;justify-content:center;padding:11px 16px;
  background:#1b1b1f;border:1px solid #ffffff12;border-radius:11px;color:#c9c9cf;
  font-size:13.5px;text-decoration:none}
.albums.edit ~ * #alb-manage, body.albmode #alb-manage{display:none}
body.albmode #alb-new{display:none}   /* 管理模式里不出现「新建」 */
.trashbar b{color:#78787d;font-size:12px;font-weight:500}
.trashbar:active{background:#232327}
.grid a .chk{position:absolute;left:5px;top:5px;width:21px;height:21px;border-radius:50%;
  background:#0a84ff;color:#fff;font-size:12px;line-height:21px;text-align:center;z-index:2;font-weight:700;
  box-shadow:0 1px 4px #0006;
  opacity:0;transform:scale(.3);transition:opacity .18s ease,transform .18s ease}
.grid a.sel .chk{opacity:1;transform:scale(1);animation:popIn .26s cubic-bezier(.34,1.56,.64,1)}
/* 多选模式下批量选中可能几千张，关掉逐个动画/过渡，避免全选后卡住/滑不动 */
body.selmode .grid a,
body.selmode .grid a .chk{transition:none}
body.selmode .grid a.sel,
body.selmode .grid a.sel::after,
body.selmode .grid a.sel .chk{animation:none}
.selbar{position:fixed;top:0;left:0;right:0;z-index:60;background:#161619f5;backdrop-filter:blur(18px);
  display:none;align-items:center;gap:18px;padding:15px 18px;border-bottom:1px solid #ffffff0f}
body.selmode .selbar{display:flex}
body.selmode header,body.selmode nav{display:none}
body.selmode main{padding-top:62px!important}
.selbar .x,.selbar .all{color:#0a84ff;font-size:15.5px}
.selbar .cnt{flex:1;font-size:16px;font-weight:650}
.selactions{position:fixed;bottom:0;left:0;right:0;z-index:60;background:#161619f5;backdrop-filter:blur(18px);
  display:none;border-top:1px solid #ffffff0f;padding-bottom:8px}
body.selmode .selactions{display:flex}
.selactions div{flex:1;display:flex;flex-direction:column;align-items:center;gap:5px;padding:10px 0;
  font-size:11px;color:#d6d6da;letter-spacing:.3px}
.selactions div:active{background:#ffffff12}
.selactions div.danger{color:#ff7a7a}
.selactions svg{width:23px;height:23px;stroke:currentColor;fill:none;stroke-width:1.8;
  stroke-linecap:round;stroke-linejoin:round}
.picker{position:fixed;inset:0;z-index:110;background:#000000b8;display:none;align-items:flex-end}
.picker.on{display:flex}
.picker .sheet{width:100%;max-height:72%;background:#1b1b1e;border-radius:18px 18px 0 0;
  padding:18px 18px 28px;overflow:auto}
.picker h3{font-size:15.5px;margin-bottom:8px;color:#ededef;font-weight:650}
.picker .pl{padding:14px 6px;border-bottom:1px solid #ffffff0f;font-size:15px;color:#ededef}
.picker .pl:active{background:#ffffff12}
.picker .pl small{color:#78787d;font-size:12px;margin-left:7px}
.info{position:fixed;inset:0;z-index:120;background:#000000b8;display:none;align-items:flex-end}
.info.on{display:flex}
.info .sheet{width:100%;max-height:78%;background:#1b1b1e;border-radius:18px 18px 0 0;
  padding:18px 20px 30px;overflow:auto}
.info h3{font-size:16px;margin-bottom:14px;color:#ededef;font-weight:650}
.info .row{display:flex;gap:12px;padding:11px 0;border-bottom:1px solid #ffffff0f;font-size:14px}
.info .row:last-child{border-bottom:none}
.info .k{color:#8e8e93;width:82px;flex:none}
.info .v{flex:1;color:#ededef;word-break:break-all;line-height:1.45}
.info .path{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;color:#a8a8ad}
.acard{position:relative}
.acard .gtag{position:absolute;top:6px;left:6px;z-index:2;background:#000000a8;color:#cfcfd4;
  font-size:10.5px;padding:3px 7px;border-radius:6px;letter-spacing:.3px}
.acard.dragging{transition:none;z-index:9;box-shadow:0 12px 32px #000b}
.acard.dragging .m{opacity:.85}
/* 相册多选：长按进入，右上角打勾 */
.albums .acard .ckb{display:none;position:absolute;right:8px;top:8px;width:22px;height:22px;border-radius:50%;
  border:2px solid #ffffffb0;background:#00000060;z-index:3}
.albums.edit .acard .ckb{display:block}
.albums .acard.sel .ckb{background:#3b82f6;border-color:#3b82f6}
.albums .acard.sel::after{content:'';position:absolute;inset:0;border:2px solid #3b82f6;border-radius:12px;pointer-events:none}
#albbar{position:fixed;left:0;right:0;bottom:0;z-index:120;display:none;align-items:center;gap:14px;
  padding:12px 16px 18px;background:#161618f2;border-top:1px solid #ffffff14;font-size:14px;color:#ededef;
  backdrop-filter:blur(8px)}
#albbar span{padding:6px 4px;color:#c9c9cf}
#albbar b{flex:1;text-align:center;color:#ff7a7a;font-weight:600}
.scrub{position:fixed;right:0;width:24px;z-index:16;display:none;touch-action:none}
.scrub.on{display:block}
/* 拖动滚动条：平时隐形（安卓 WebView 的系统滚动条 CSS 关不掉，两条会重叠），
   手指按住右侧拖动时才显示，拖动功能保留 */
.scrub .thumb{position:absolute;right:4px;width:5px;border-radius:4px;background:#ffffff38;
  min-height:38px;transition:width .12s,background .12s}
.scrub.drag .thumb{width:9px;background:#ffffff7a}
.scrub .bubble{position:absolute;right:24px;transform:translateY(-50%);background:#26262af2;color:#fff;
  padding:7px 12px;border-radius:9px;font-size:13.5px;font-weight:600;white-space:nowrap;
  display:none;box-shadow:0 4px 14px #0007}
.scrub.drag .bubble{display:block}
"""

ICON_SAVE = ('<svg viewBox="0 0 24 24"><path d="M12 3v12"/><path d="M7 10l5 5 5-5"/>'
             '<path d="M4 21h16"/></svg>')
ICON_EDIT = ('<svg viewBox="0 0 24 24"><path d="M12 20h9"/>'
             '<path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/></svg>')
ICON_DEL = ('<svg viewBox="0 0 24 24"><path d="M3 6h18"/><path d="M8 6V4h8v2"/>'
            '<path d="M6 6l1 14h10l1-14"/></svg>')
ICON_DL = ('<svg viewBox="0 0 24 24"><path d="M12 4v11"/>'
             '<path d="M7 11l5 5 5-5"/><path d="M5 20h14"/></svg>')
ICON_FAV = ('<svg viewBox="0 0 24 24"><path d="M12 20s-7-4.6-7-9.4A4.1 4.1 0 0 1 12 7a4.1 4.1 0 0 1 7 3.6C19 15.4 12 20 12 20z"/></svg>')
ICON_INFO = ('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/>'
             '<path d="M12 11v5"/><path d="M12 7.6v.1"/></svg>')
ICON_MOVE = ('<svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>'
             '<path d="M9 13h6"/><path d="M12 10l3 3-3 3"/></svg>')
ICON_SHARE = ('<svg viewBox="0 0 24 24"><circle cx="18" cy="5" r="3"/>'
              '<circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>'
              '<path d="M8.6 10.7l6.8-4.4"/><path d="M8.6 13.3l6.8 4.4"/></svg>')

def scrub_html(top, bottom):
    return ('<div class="scrub" id="scrub" style="top:%s;bottom:%s">'
            '<div class="thumb" id="scrubThumb"></div>'
            '<div class="bubble" id="scrubBubble"></div></div>' % (top, bottom))


VIEWER_HTML = (
    '<div class="viewer" id="viewer">'
    '<div class="page" id="vpage"></div>'
    '<div class="strip" id="strip">'
    '<div class="pane" id="p0"></div><div class="pane" id="p1"></div><div class="pane" id="p2"></div>'
    '</div>'
    '<div class="acts">'
    '<button class="it" id="a-share">%s<span>发送</span></button>'
    '<button class="it" id="a-save">%s<span>保存</span></button>'
    '<button class="it" id="a-move">%s<span>移动</span></button>'
    '<button class="it" id="a-edit">%s<span>编辑</span></button>'
    '<button class="it" id="a-fav">%s<span id="afavtxt">收藏</span></button>'
    '<button class="it" id="a-info">%s<span>信息</span></button>'
    '<button class="it danger" id="a-del">%s<span>删除</span></button>'
    '</div></div>' % (ICON_SHARE, ICON_SAVE, ICON_MOVE, ICON_EDIT, ICON_FAV, ICON_INFO, ICON_DEL))

SELECT_HTML = (
    '<div class="selbar"><span class="x" id="sel-cancel">取消</span>'
    '<span class="cnt" id="selcnt">已选 0 项</span>'
    '<span class="all" id="sel-all">全选</span></div>'
    '<div class="selactions">'
    '<div id="sel-share">%s发送</div>'
    '<div id="sel-dl">%s下载</div>'
    '<div id="sel-move">%s移动</div>'
    '<div id="sel-fav">%s收藏</div>'
    '<div class="danger" id="sel-del">%s删除</div>'
    '</div>'
    '<div class="picker" id="picker"><div class="sheet"><h3>移动到相册</h3>'
    '<div id="picker-list"></div></div></div>'
    '<div class="info" id="info"><div class="sheet"><h3>照片信息</h3>'
    '<div id="info-body"></div></div></div>' % (ICON_SHARE, ICON_DL, ICON_MOVE, ICON_FAV, ICON_DEL))

VIEWER_JS = r"""
// 弱网/断网：图片加载失败给出可见反馈，而不是一个破图标
document.addEventListener('error', function(e){
  var t=e.target;
  if(!t || t.tagName!=='IMG') return;
  if(t.dataset && t.dataset.__rt){ t.classList.add('ph'); return; }
  if(t.closest && t.closest('#viewer')){
    if(t.dataset) t.dataset.__rt='1';
    var src=t.getAttribute('src')||'';
    if(window.__toast) __toast('这张图加载失败，正在重试…');
    setTimeout(function(){ t.src=src+(src.indexOf('?')<0?'?':'&')+'_r='+Date.now(); }, 900);
  }else{
    t.classList.add('ph');
  }
}, true);
window.__curList=null; window.__curIdx=0; window.__curEl=null;
function __abs(u){ try{ return new URL(u, location.origin).href; }catch(e){ return u; } }
// 删除后到生成器重建（≤1 分钟）之间，页面可能还缓存着已被删的条目；
// 用 localStorage 记住删除的 URL，页面加载时过滤掉，避免刷新后又出现/重复删 404。
window.__hiddenMedia=(function(){
  var KEY='nas_hidden_media';
  function load(){
    try{
      var a=JSON.parse(localStorage.getItem(KEY)||'[]'), now=Date.now(), out=[];
      for(var i=0;i<a.length;i++){ if(a[i]&&a[i].u&&(now-a[i].t)<10*60*1000) out.push(a[i]); }
      if(out.length!==a.length){ try{ localStorage.setItem(KEY,JSON.stringify(out)); }catch(e){} }
      return out;
    }catch(e){ return []; }
  }
  function save(a){ try{ localStorage.setItem(KEY,JSON.stringify(a)); }catch(e){} }
  function set(){ var m={}, a=load(); for(var i=0;i<a.length;i++) m[a[i].u]=1; return m; }
  function add(urls){
    if(!urls||!urls.length) return;
    var a=load(), m={}, now=Date.now();
    for(var i=0;i<a.length;i++) m[a[i].u]=1;
    for(var j=0;j<urls.length;j++){
      var u=urls[j];
      if(u&&!m[u]){ a.push({u:u,t:now}); m[u]=1; }
    }
    save(a);
  }
  return {load:load,set:set,add:add};
})();
window.__hideMedia=function(urls){ try{ window.__hiddenMedia.add(urls); }catch(e){} };
window.__hiddenSet=function(){ try{ return window.__hiddenMedia.set(); }catch(e){ return {}; } };

// 移动的“乐观状态”：生成器 ≤1 分钟才重建，期间用 localStorage 记录
// {src,dest,name,thumb,ts,isVid,fsize}，首页重算相册卡片、目标/源相册页动态增删。
window.__movedMedia=(function(){
  var KEY='nas_moved_media';
  function load(){
    try{
      var a=JSON.parse(localStorage.getItem(KEY)||'[]'), now=Date.now(), out=[];
      for(var i=0;i<a.length;i++){
        if(a[i]&&a[i].src&&a[i].dest&&(now-(a[i].t||0))<90*1000) out.push(a[i]);
      }
      // 同一个 src 只保留最后一次目标；A→B→C 的 src 不同，两条都保留
      var latest={}, res=[];
      for(var k=0;k<out.length;k++) latest[out[k].src]=out[k];
      for(var m=0;m<out.length;m++){ if(latest[out[m].src]===out[m]) res.push(out[m]); }
      if(res.length!==a.length){ try{ localStorage.setItem(KEY,JSON.stringify(res)); }catch(e){} }
      return res;
    }catch(e){ return []; }
  }
  function save(a){ try{ localStorage.setItem(KEY,JSON.stringify(a)); }catch(e){} }
  function add(list){
    if(!list||!list.length) return;
    var a=load(), now=Date.now();
    for(var i=0;i<list.length;i++){
      var e=list[i];
      if(!e||!e.src||!e.dest) continue;
      // 同一个源只保留最新目标；A→B→C 的源不同，两条都保留
      for(var j=a.length-1;j>=0;j--){
        if(a[j].src===e.src){ a.splice(j,1); }
      }
      e.t=e.t||now;
      a.push(e);
    }
    save(a);
  }
  return {load:load,add:add};
})();
window.__movesGet=function(){ try{ return window.__movedMedia.load(); }catch(e){ return []; } };
window.__movesAdd=function(list){ try{ window.__movedMedia.add(list); }catch(e){} };
function __paneEl(i, it, auto){
  var el=document.getElementById('p'+i);
  if(!it){ el.innerHTML=''; return; }
  if(it[1]===1){
    el.innerHTML='<video src="'+it[0]+'" controls playsinline disableRemotePlayback '+
      (auto?'autoplay':'preload="metadata"')+'></video>';
    try{
      if(window.navigator && navigator.mediaSession && window.MediaMetadata){
        navigator.mediaSession.metadata=new MediaMetadata({title:'',artist:'',album:''});
      }
    }catch(e){}
    if(auto){
      var v=el.querySelector('video');
      if(v){
        v.muted=false;
        var p=v.play();
        if(p&&p.catch) p.catch(function(){ v.muted=true; v.play().catch(function(){}); });
      }
    }
  }else{
    el.innerHTML='<img src="'+it[0]+'" alt="">';
  }
}
function __stopVideos(){
  document.querySelectorAll('#strip video').forEach(function(v){ try{ v.pause(); }catch(e){} });
}
function __setPos(px, anim){
  var st=document.getElementById('strip');
  st.style.transition=anim?'transform .28s cubic-bezier(.22,.8,.3,1)':'none';
  st.style.transform='translateX(calc(-33.33333% + '+px+'px))';
}
window.__renderPanes=function(){
  var l=window.__curList; if(!l||!l.length) return;
  var n=l.length, i=window.__curIdx;
  __stopVideos();
  if(window.__resetZoom) window.__resetZoom(false);     // 换图后缩放归位
  __paneEl(0, n>1?l[(i-1+n)%n]:null, false);
  __paneEl(1, l[i], true);
  __paneEl(2, n>1?l[(i+1)%n]:null, false);
  document.getElementById('vpage').textContent=(i+1)+' / '+n;
  __setPos(0,false);
  // 记录当前项路径 + 同步收藏按钮状态
  try{
    var itc=l[i];
    window.__curFull=itc?(new URL(itc[0],location.origin).pathname):null;
    var fb=document.getElementById('a-fav'), ft=document.getElementById('afavtxt');
    var on=window.__favHas?window.__favHas(window.__curFull):false;
    if(ft) ft.textContent=on?'已收藏':'收藏';
    if(fb) fb.style.color=on?'#ff5d6c':'';
  }catch(e){}

  // 预加载左右相邻图，翻页不再等网络
  try{
    [-1,1].forEach(function(d){
      var it2=l[(i+d+n)%n];
      if(it2 && it2[1]!==1){ var pre=new Image(); pre.src=it2[0]; }
    });
  }catch(e){}
};
window.__renderViewer=function(k){
  var l=window.__curList; if(!l||!l.length) return;
  window.__curIdx=(k+l.length)%l.length;
  window.__renderPanes();
};
window.__openViewer=function(list,start,el){
  window.__curList=list; window.__curEl=el||null;
  window.__curIdx=start||0;
  var v=document.getElementById('viewer');
  if(!v.classList.contains('on')){
    try{ history.pushState({v:1},'','#v'); }catch(e){}
    v.classList.add('on');
    v.classList.remove('ui-off');            // 每次打开都先显示操作栏
    try{ if(window.Android&&window.Android.setViewer) window.Android.setViewer(true); }catch(e){}
  }
  window.__renderPanes();
};
window.__closeViewer=function(){
  var v=document.getElementById('viewer');
  if(!v||!v.classList.contains('on')) return false;
  // 详情页的「移动」面板是叠在大图上的；App 的 onKeyDown 在 state=pk 时会调到这里，
  // 此时只关移动面板，大图保持，下一次返回才关大图。
  var pk=document.getElementById('picker');
  if(pk&&pk.classList.contains('on')){
    if(history.state&&history.state.pk) history.back();
    else pk.classList.remove('on');
    return true;
  }
  __stopVideos();
  v.classList.remove('on');
  var inf=document.getElementById('info'); if(inf) inf.classList.remove('on');
  try{ if(window.Android&&window.Android.setViewer) window.Android.setViewer(false); }catch(e){}
  return true;
};
window.__onDeleted=function(isMove){
  var list=window.__curList; if(!list) return;
  var u=list[window.__curIdx]?list[window.__curIdx][0]:null;
  list.splice(window.__curIdx,1);
  if(!isMove&&u) window.__afterMediaDeleted([u]);
  if(window.__curEl&&window.__curEl.parentNode){ window.__curEl.parentNode.removeChild(window.__curEl); window.__curEl=null; }
  if(!list.length){ window.__closeViewer(); if(history.state&&history.state.v) history.back(); return; }
  if(window.__curIdx>=list.length) window.__curIdx=list.length-1;
  window.__renderPanes();
};
window.__onMsg=function(t){ try{ alert(t); }catch(e){} };
window.__curUrl=function(){
  var l=window.__curList;
  return (l&&l[window.__curIdx])? __abs(l[window.__curIdx][0]) : null;
};
(function(){
  var v=document.getElementById('viewer');
  if(!v||v.__bound) return; v.__bound=1;
  var sx=0, sy=0, dx=0, dragging=false, decided=false, swiped=false;

  function N(){ return window.__curList?window.__curList.length:1; }
  function W(){ return window.innerWidth; }

  // ===== 缩放：双指捏合 / 双击放大还原 / 放大后单指平移 =====
  var zoom={s:1,tx:0,ty:0}, pinch=null, panning=false, panPt=null;
  var lastTapT=0, lastTapX=0, lastTapY=0;
  function curImg(){
    var p=document.getElementById('p1');
    return p?p.querySelector('img'):null;
  }
  function applyZoom(anim){
    var im=curImg(); if(!im) return;
    im.style.transition=anim?'transform .18s ease':'none';
    im.style.transform='translate('+zoom.tx.toFixed(1)+'px,'+zoom.ty.toFixed(1)+'px) scale('+zoom.s.toFixed(3)+')';
  }
  function clampPan(){
    var im=curImg(); if(!im||zoom.s<=1) return;
    var r=im.getBoundingClientRect();
    var w=r.width/zoom.s, h=r.height/zoom.s;
    // 图片尚未布局（rect 为 0）时按视口估算，否则边界会被算成 0、平移失效
    if(!w||!h||w<2||h<2){ w=W(); h=window.innerHeight; }
    var mx=Math.max(0,(w*zoom.s-W())/2);
    var my=Math.max(0,(h*zoom.s-window.innerHeight)/2);
    zoom.tx=Math.max(-mx,Math.min(mx,zoom.tx));
    zoom.ty=Math.max(-my,Math.min(my,zoom.ty));
  }
  function resetZoom(anim){ zoom={s:1,tx:0,ty:0}; applyZoom(anim); }
  window.__resetZoom=resetZoom;
  window.__zoomState=function(){ return {s:zoom.s,tx:zoom.tx,ty:zoom.ty}; };
  function dist2(t){
    var dx=t[0].clientX-t[1].clientX, dy=t[0].clientY-t[1].clientY;
    return Math.sqrt(dx*dx+dy*dy);
  }
  function mid2(t){ return {x:(t[0].clientX+t[1].clientX)/2, y:(t[0].clientY+t[1].clientY)/2}; }

  function slideTo(dir){
    var n=N();
    if(n<2){ __setPos(0,true); return; }
    __setPos(dir>0?-W():W(), true);
    var done=false;
    function finish(){
      if(done) return; done=true;
      window.__curIdx=(window.__curIdx+dir+n)%n;
      window.__renderPanes();
    }
    document.getElementById('strip').addEventListener('transitionend', finish, {once:true});
    setTimeout(finish, 340);
  }

  // 左右切换只留给滑动（用户要求）：不再有点击左右区域换图
  // 单指轻点：切换「显示操作栏 / 沉浸看大图」（用户要求：图2 ↔ 图3）
  var tapTimer=null;
  function toggleViewerUi(){
    var el=document.getElementById('viewer'); if(!el) return;
    el.classList.toggle('ui-off');
  }
  window.__toggleViewerUi=toggleViewerUi;

  v.addEventListener('touchstart',function(e){
    if(e.touches.length>=2){                       // 双指：进入缩放，取消轮播
      if(!curImg()) return;
      if(e.cancelable) e.preventDefault();
      dragging=false; panning=false;
      pinch={d0:dist2(e.touches), s0:zoom.s, m:mid2(e.touches), tx0:zoom.tx, ty0:zoom.ty};
      return;
    }
    var t=e.touches[0]; if(!t) return;
    if(zoom.s>1.01){                               // 已放大：单指平移
      panning=true; dragging=false;
      panPt={x:t.clientX,y:t.clientY,tx:zoom.tx,ty:zoom.ty};
      return;
    }
    sx=t.clientX; sy=t.clientY; dx=0; dragging=true; decided=false; swiped=false;
    __setPos(0,false);
  },{passive:false});

  v.addEventListener('touchmove',function(e){
    if(pinch && e.touches.length>=2){               // 捏合缩放
      if(e.cancelable) e.preventDefault();
      var ns=pinch.s0*(dist2(e.touches)/pinch.d0);
      ns=Math.max(1,Math.min(5,ns));
      var mm=mid2(e.touches);
      zoom.s=ns;
      zoom.tx=pinch.tx0+(mm.x-pinch.m.x);
      zoom.ty=pinch.ty0+(mm.y-pinch.m.y);
      clampPan(); applyZoom(false);
      return;
    }
    if(panning){                                    // 放大态平移
      var tp=e.touches[0]; if(!tp) return;
      if(e.cancelable) e.preventDefault();
      zoom.tx=panPt.tx+(tp.clientX-panPt.x);
      zoom.ty=panPt.ty+(tp.clientY-panPt.y);
      clampPan(); applyZoom(false);
      return;
    }
    if(!dragging) return;
    var t=e.touches[0]; if(!t) return;
    var ax=t.clientX-sx, ay=t.clientY-sy;
    if(!decided){
      if(Math.abs(ax)<8 && Math.abs(ay)<8) return;
      decided=true;
      if(Math.abs(ay)>Math.abs(ax)*1.2){ dragging=false; return; }
    }
    if(e.cancelable) e.preventDefault();
    dx=ax; swiped=true;
    if(N()<=1) dx=dx*0.25;
    __setPos(dx,false);
  },{passive:false});

  v.addEventListener('touchend',function(e){
    if(pinch){                                      // 捏合结束
      if(e.touches.length>=1) return;               // 还有手指按着，等全松
      pinch=null;
      if(zoom.s<1.02) resetZoom(true); else { clampPan(); applyZoom(true); }
      return;
    }
    if(panning){                                    // 平移结束
      panning=false;
      var ct0=e.changedTouches&&e.changedTouches[0];
      var moved=ct0?(Math.abs(ct0.clientX-panPt.x)+Math.abs(ct0.clientY-panPt.y)):999;
      var nowp=Date.now();
      if(moved<10 && ct0){
        if(nowp-lastTapT<300){ lastTapT=0; resetZoom(true); return; }   // 双击还原
        lastTapT=nowp; lastTapX=ct0.clientX; lastTapY=ct0.clientY;
      }
      if(zoom.s<1.02) resetZoom(true); else applyZoom(true);
      return;
    }
    // 双击放大（未放大时）
    var ct=e.changedTouches&&e.changedTouches[0];
    if(!swiped && ct){
      var now=Date.now();
      if(now-lastTapT<300 && Math.abs(ct.clientX-lastTapX)<30 && Math.abs(ct.clientY-lastTapY)<30){
        lastTapT=0;
        if(tapTimer){ clearTimeout(tapTimer); tapTimer=null; }   // 双击时不切换界面
        if(zoom.s>1.2){ resetZoom(true); }
        else if(curImg()){
          var ns2=2.5;
          zoom.s=ns2;
          zoom.tx=-(ns2-1)*(ct.clientX-W()/2);
          zoom.ty=-(ns2-1)*(ct.clientY-window.innerHeight/2);
          clampPan(); applyZoom(true);
        }
        dragging=false; return;
      }
      lastTapT=now; lastTapX=ct.clientX; lastTapY=ct.clientY;
      // 单击稍等一下再切换，避免和双击放大抢
      if(tapTimer) clearTimeout(tapTimer);
      tapTimer=setTimeout(function(){
        tapTimer=null;
        if(zoom.s<=1.01) toggleViewerUi();
      },280);
    }
    if(!dragging) return;
    dragging=false;
    var th=Math.min(90, W()*0.22);
    if(N()>1 && dx<=-th) slideTo(1);
    else if(N()>1 && dx>=th) slideTo(-1);
    else __setPos(0,true);
  },{passive:true});

  document.getElementById('a-fav').onclick=function(e){
    e.stopPropagation();
    var fp=window.__curFull;
    if(!fp||!window.__favToggle) return;
    var on=window.__favToggle(fp);
    var ft=document.getElementById('afavtxt');
    if(ft) ft.textContent=on?'已收藏':'收藏';
    this.style.color=on?'#ff5d6c':'';
    if(navigator.vibrate){ try{ navigator.vibrate(10); }catch(e){} }
    // 筛选条的收藏计数立即同步（否则要等下次重渲染）
    try{
      var cb=document.querySelector('.chips b[data-m="fav"]');
      if(cb) cb.textContent='收藏 '+Object.keys(FAV).length;
    }catch(e){}
    // 列表里的红心同步（下次渲染生效；这里顺手更新当前格子）
    try{
      var a=document.querySelector('.grid a[data-full="'+fp.replace(/"/g,'\\"')+'"]');
      if(a){ var ex=a.querySelector('.fav'); if(on&&!ex){ var sp=document.createElement('span'); sp.className='fav'; sp.textContent='♥'; a.appendChild(sp); } else if(!on&&ex){ ex.remove(); } }
    }catch(e){}
  };
  document.getElementById('a-info').onclick=function(e){ e.stopPropagation(); window.__showInfo(); };
  document.getElementById('a-save').onclick=function(e){
    e.stopPropagation();
    var u=window.__curUrl(); if(!u) return;
    if(window.Android&&window.Android.save) window.Android.save(u);
    else alert('当前环境不支持保存，请更新 App');
  };
  document.getElementById('a-move').onclick=function(e){
    e.stopPropagation();
    var u=window.__curUrl(); if(!u) return;
    var it=(window.__curList&&window.__curList[window.__curIdx])||null;
    var path=it?it[0]:null, ex=null;
    var meta=(window.__DATA&&window.__DATA.albums)||window.__ALBUMS||[];
    if(path) meta.forEach(function(a){
      if(a.p && path.indexOf(a.p+'/')===0 && (!ex||a.p.length>ex.length)) ex=a.p;
    });
    if(window.__openMovePicker) window.__openMovePicker([u], ex);
    else alert('当前环境不支持移动，请更新 App');
  };
  document.getElementById('a-edit').onclick=function(e){
    e.stopPropagation();
    var u=window.__curUrl(); if(!u) return;
    if(window.Android&&window.Android.edit) window.Android.edit(u);
    else alert('当前环境不支持编辑，请更新 App');
  };
  document.getElementById('a-share').onclick=function(e){
    e.stopPropagation();
    var u=window.__curUrl(); if(!u) return;
    if(window.Android&&window.Android.shareMany) window.Android.shareMany(JSON.stringify([u]));
    else alert('当前环境不支持发送，请更新 App');
  };
  document.getElementById('a-del').onclick=function(e){
    e.stopPropagation();
    var u=window.__curUrl(); if(!u) return;
    if(!confirm('移到回收站？30 天后自动清理。')) return;
    window.__softDelete([u], true);
  };
  document.getElementById('info').onclick=function(e){
    if(e.target!==this) return;
    // 关信息面板只回退 nf 这一层，大图保持打开；pushState 失败时才直接移除。
    if(history.state&&history.state.nf) history.back(); else this.classList.remove('on');
  };

  window.__showInfo=function(){
    var inf=document.getElementById('info');
    if(inf&&inf.classList.contains('on')) return;
    var l=window.__curList; if(!l||!l.length) return;
    var it=l[window.__curIdx]; if(!it) return;
    function dec(u){ try{ return decodeURIComponent(u); }catch(e){ return u; } }
    function esc(x){ return String(x).replace(/[&<>"]/g,function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
    function fmtSize(n){
      if(!n) return '\u2014';
      if(n<1024) return n+' B';
      if(n<1048576) return (n/1024).toFixed(1)+' KB';
      if(n<1073741824) return (n/1048576).toFixed(1)+' MB';
      return (n/1073741824).toFixed(2)+' GB';
    }
    function fmtDate(ts){
      if(!ts) return '\u2014';
      var d=new Date(ts*1000), p=function(x){ return x<10?'0'+x:''+x; };
      return d.getFullYear()+'\u5e74'+(d.getMonth()+1)+'\u6708'+d.getDate()+'\u65e5 '+
             p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds());
    }
    var full=it[0], isVid=it[1]===1, size=it[2], album=it[3], ts=it[4];
    var name=dec(String(full).split('/').pop());
    var dim='\u2014';
    var pane=document.getElementById('p1');
    if(pane){
      if(isVid){
        var vv=pane.querySelector('video');
        if(vv&&vv.videoWidth) dim=vv.videoWidth+' \u00d7 '+vv.videoHeight;
      }else{
        var im=pane.querySelector('img');
        if(im&&im.naturalWidth) dim=im.naturalWidth+' \u00d7 '+im.naturalHeight;
      }
    }
    var rows=[
      ['\u6587\u4ef6\u540d', esc(name)],
      ['\u7c7b\u578b', isVid?'\u89c6\u9891':'\u56fe\u7247'],
      ['\u5c3a\u5bf8', dim],
      ['\u5927\u5c0f', fmtSize(size)],
      ['\u65f6\u95f4', fmtDate(ts)],
      ['\u6240\u5c5e\u76f8\u518c', esc(album||'\u2014')],
      ['NAS \u4f4d\u7f6e', '<span class="path">'+esc(dec(full))+'</span>']
    ];
    document.getElementById('info-body').innerHTML=rows.map(function(r){
      return '<div class="row"><div class="k">'+r[0]+'</div><div class="v">'+r[1]+'</div></div>';
    }).join('');
    document.getElementById('info').classList.add('on');
    try{ history.pushState({nf:1},'','#nf'); }catch(e){}
  };

  v.onclick=function(e){
    if(swiped){ swiped=false; return; }
    if(e.target===v){
      if(history.state&&history.state.v) history.back(); else window.__closeViewer();
    }
  };
})();
"""

SCRUB_JS = r"""
(function(){
  var el=document.getElementById('scrub');
  if(!el||el.__bound) return; el.__bound=1;
  var thumb=document.getElementById('scrubThumb'), bub=document.getElementById('scrubBubble');
  var scroller=null, dragging=false;

  function S(){
    var h=scroller?scroller.scrollHeight:document.documentElement.scrollHeight;
    var c=scroller?scroller.clientHeight:(window.innerHeight||0);
    if(h<=c) h=c;                       // 内容不足一屏时不显示
    return {h:h,c:c,max:Math.max(1,h-c),real:(scroller?scroller.scrollHeight:document.documentElement.scrollHeight)};
  }
  function curTop(){
    return scroller?scroller.scrollTop:(window.pageYOffset||document.documentElement.scrollTop||0);
  }
  function go(v){ if(scroller) scroller.scrollTop=v; else window.scrollTo(0,v); }

  function sync(){
    var s=S();
    if(s.real<=s.c+8){ el.classList.remove('on'); return; }
    el.classList.add('on');
    var H=el.clientHeight, th=Math.max(38, H*s.c/s.real);
    var ratio=curTop()/s.max;
    thumb.style.height=th+'px';
    thumb.style.top=(Math.max(0,Math.min(H-th, ratio*(H-th))))+'px';
  }
  window.__syncScrub=sync;
  window.__bindScrub=function(sc){
    scroller=sc||null;
    if(scroller){ scroller.addEventListener('scroll',sync,{passive:true}); }
    else { window.addEventListener('scroll',sync,{passive:true}); }
    sync();
  };

  function label(){
    var heads=document.querySelectorAll('.mhead b');
    var base=scroller?scroller.getBoundingClientRect().top:0;
    var cur='';
    for(var i=0;i<heads.length;i++){
      var r=heads[i].getBoundingClientRect();
      if(r.top-base<=70) cur=heads[i].textContent; else break;
    }
    return cur||(heads[0]?heads[0].textContent:'');
  }

  function at(clientY){
    var r=el.getBoundingClientRect();
    var th=thumb.offsetHeight;
    var ratio=(clientY-r.top-th/2)/Math.max(1,r.height-th);
    ratio=Math.max(0,Math.min(1,ratio));
    var s=S();
    go(ratio*s.max);
    var t=label();
    bub.textContent=t||'';
    bub.style.top=Math.round(ratio*(r.height-th)+th/2)+'px';
  }
  function start(e){
    dragging=true; el.classList.add('drag');
    if(e.cancelable) e.preventDefault();
    at(e.touches?e.touches[0].clientY:e.clientY);
  }
  function move(e){
    if(!dragging) return;
    if(e.cancelable) e.preventDefault();
    at(e.touches?e.touches[0].clientY:e.clientY);
  }
  function end(){ if(!dragging) return; dragging=false; el.classList.remove('drag'); }

  el.addEventListener('touchstart',start,{passive:false});
  el.addEventListener('touchmove',move,{passive:false});
  el.addEventListener('touchend',end,{passive:true});
  el.addEventListener('touchcancel',end,{passive:true});
  el.addEventListener('mousedown',start);
  document.addEventListener('mousemove',move);
  document.addEventListener('mouseup',end);
})();
"""

SELECT_JS = r"""
(function(){
  var lb=document.getElementById('selcnt');
  if(!lb||lb.__bound) return; lb.__bound=1;
  var timer=null, pressing=null;
  var dragMode=false, startA=null, lastA=null, movedInSel=false;
  var dragStartPt=null;
  var axis=null, lastY=0;

  var selCount=0;
  var totalCells=0;   // 进选择模式时缓存一次总格数，避免全选时每次 mark 都重查 DOM（2389 张会卡死）
  function items(){ return Array.prototype.slice.call(document.querySelectorAll('.grid a.sel')); }
  function update(){
    if(!totalCells) totalCells=document.querySelectorAll('.grid:not([data-otd]) a[data-full]').length;
    document.getElementById('selcnt').textContent='已选 '+selCount+' 项';
    document.getElementById('sel-all').textContent =
      (totalCells>0 && selCount>=totalCells) ? '全不选' : '全选';
  }
  function mark(a,on){
    if(!a) return;
    var want=(on===undefined)? !a.classList.contains('sel') : on;
    var isSel=a.classList.contains('sel');
    if(want && !isSel){
      a.classList.add('sel'); selCount++;
      if(!a.querySelector('.chk')){var s=document.createElement('span');s.className='chk';s.textContent='✓';a.appendChild(s);}
    }else if(!want && isSel){
      a.classList.remove('sel'); if(selCount>0) selCount--;
    }
    update();
  }
  function clearAll(){
    document.querySelectorAll('.grid a.sel').forEach(function(a){ a.classList.remove('sel'); });
    selCount=0; update();
  }
  window.__exitSel=function(useHistory){
    if(useHistory && history.state && history.state.sel){ history.back(); return; }
    document.body.classList.remove('selmode');
    anchorEl=null; anchorGrid=null; dragSet=[]; allCells=null; cellTops=null;
    totalCells=0;
    clearAll(); update();
  };
  window.__onBulkDone=function(msg){
    var pend=window.__pendingDelete; window.__pendingDelete=null;
    if(pend && (!msg || msg.indexOf('失败')<0)) window.__afterMediaDeleted(pend);
    document.querySelectorAll('.grid a.sel').forEach(function(a){ if(a.parentNode) a.parentNode.removeChild(a); });
    totalCells=0;
    if(history.state && history.state.sel){ history.back(); }
    else{ document.body.classList.remove('selmode'); clearAll(); update(); }
    if(msg) setTimeout(function(){ alert(msg); }, 60);
  };
  // 删除后立即重算本页数据/相册卡片；相册内页清空时回相册列表。
  window.__afterMediaDeleted=function(urls){
    if(!urls||!urls.length) return;
    window.__hideMedia(urls);
    if(window.__albumItems){
      var hid=window.__hiddenSet?window.__hiddenSet():{};
      window.__albumItems=window.__albumItems.filter(function(it){ return !hid[it[0]]; });
      var acnt=document.getElementById('acnt');
      if(acnt) acnt.textContent=window.__albumItems.length+' 项';
      if(window.__albumItems.length===0){
        setTimeout(function(){ location.href='/相册/index.html#albums'; },350);
      }
    }
    if(window.__applyHiddenIndex) window.__applyHiddenIndex();
  };
  // 移动出当前相册后，数量/空相册立刻更新（移动不写 hidden，目标相册仍保留）。
  // 移动后清理 DOM：移除已移走的格子、同步 data-list/data-i，避免点开错图
  window.__paintIndexMoved=function(set){
    if(!set) return;
    if(window.paintIndexHidden) window.paintIndexHidden(set);   // 首页时间轴（内页没有这个函数）
    document.querySelectorAll('#g .grid').forEach(function(g){   // 相册内页
      var list=[]; try{ list=JSON.parse(g.getAttribute('data-list')||'[]'); }catch(e){}
      var kept=list.filter(function(it){ return !set[it[0]]; });
      if(kept.length!==list.length) g.setAttribute('data-list',JSON.stringify(kept));
      Array.prototype.slice.call(g.querySelectorAll('a[data-full]')).forEach(function(a){
        if(set[a.getAttribute('data-full')] && a.parentNode) a.parentNode.removeChild(a);
      });
      Array.prototype.slice.call(g.querySelectorAll('a[data-full]')).forEach(function(a){
        var f=a.getAttribute('data-full');
        for(var i=0;i<kept.length;i++){ if(kept[i][0]===f){ a.setAttribute('data-i',i); break; } }
      });
    });
  };
  window.__afterMediaMoved=function(list){
    if(!list||!list.length) return;
    var entries=[], set={};
    for(var i=0;i<list.length;i++){
      var e=list[i];
      if(typeof e==='string'){
        var u=e;
        try{ u=new URL(u,location.origin).pathname; }catch(err){}
        set[u]=1;
        continue;
      }
      if(!e||!e.src) continue;
      entries.push(e);
      set[e.src]=1;
    }
    if(entries.length) window.__movesAdd(entries);
    if(window.__albumItems){
      window.__albumItems=window.__albumItems.filter(function(it){ return !set[it[0]]; });
      var acnt=document.getElementById('acnt');
      if(acnt) acnt.textContent=window.__albumItems.length+' 项';
      if(window.__albumItems.length===0){
        setTimeout(function(){ location.href='/相册/index.html#albums'; },350);
      }
    }
    if(window.__paintIndexMoved) window.__paintIndexMoved(set);
    if(window.__applyHiddenIndex) window.__applyHiddenIndex();
  };
  var anchorEl=null, anchorGrid=null, anchorIdx=0, dragSet=[];
  var rangeAnchor=null;          // 本次手指按下的那张，作为区间锚点
  var justEntered=false;         // 长按刚成立，吞掉随后补发的 click
  var DRAG_THRESH=14;             // 超过这个位移才认为是拖动（过滤手指抖动）
  function enterSel(a){
    document.body.classList.add('selmode');
    justEntered=true;
    anchorEl=a; anchorGrid=a.parentNode;
    anchorIdx=Array.prototype.indexOf.call(anchorGrid.children, a);
    dragSet=[]; allCells=null; totalCells=0;
    mark(a,true);
    try{ history.pushState({sel:1},'','#sel'); }catch(e){}
    if(navigator.vibrate){ try{ navigator.vibrate(12); }catch(e){} }
  }

  function applyWant(want){
    for(var i=0;i<dragSet.length;i++){
      if(want.indexOf(dragSet[i])<0) mark(dragSet[i],false);
    }
    for(var j=0;j<want.length;j++){
      if(want[j]!==anchorEl) mark(want[j],true);
    }
    dragSet=want.slice();
  }

  // 系统相册的拖选规则：以长按那张为起点、当前手指所在为终点，
  // 在「阅读顺序」上取两者之间的全部照片（含跨月份分区）。
  var allCells=null;

  function selectRange(curA){
    var base=rangeAnchor||anchorEl;
    if(!base||!curA) return;
    if(!allCells){
      allCells=Array.prototype.slice.call(document.querySelectorAll('.grid:not([data-otd]) a[data-full]'));
    }
    var ai=allCells.indexOf(base), ci=allCells.indexOf(curA);
    if(ai<0||ci<0) return;
    var lo=Math.min(ai,ci), hi=Math.max(ai,ci);
    applyWant(allCells.slice(lo,hi+1));
  }

  // WebDAV MOVE。Android 的 HttpURLConnection 不允许 MOVE 方法（会抛 ProtocolException），
  // 所以移动改由网页 fetch 直接发 MOVE；dufs 支持，且不依赖 App 版本。
  function moveToAlbum(ps, destDir, targetName, cb){
    var ok=0, fail=0, conflict=0, cancelled=0, lastStatus=0, moved={}, entries=[];
    var headBlocked=false;   // 服务端不支持 HEAD 时直接失败关闭，绝不退化为无保护 MOVE
    function step(i){
      if(i>=ps.length){ done(); return; }
      var src=ps[i];
      var name=String(src).split('/').pop();
      var dest=location.origin + destDir + '/' + name;
      var destPath=destDir + '/' + name;
      var srcPath=src;
      try{ srcPath=new URL(src,location.origin).pathname; }catch(e){}
      var srcAbs=new URL(src,location.origin).href;
      if(dest===srcAbs){ fail++; step(i+1); return; }   // 已经在目标相册，不能把自己移给自己
      if(headBlocked){ cancelled++; step(i+1); return; } // 已确认无 HEAD，后续也绝不 MOVE
      var info=null;
      if(window.__albumItems){
        for(var ai=0;ai<window.__albumItems.length;ai++){
          var it=window.__albumItems[ai];
          if(it[0]===srcPath){ info={thumb:it[3],ts:it[2],isVid:it[1],fsize:it[4]}; break; }
        }
      }
      if(!info && window.DATA && window.DATA.photos){
        for(var pi=0;pi<window.DATA.photos.length;pi++){
          var pp=window.DATA.photos[pi];
          if(pp[1]===srcPath){ info={thumb:pp[0],ts:pp[2],isVid:pp[3],fsize:pp[5]}; break; }
        }
      }
      // 2026-10-24 实测：dufs 0.47.0 忽略 Overwrite / If-None-Match，
      // MOVE 带 Overwrite:F 到已存在路径仍会 204 覆盖。HEAD 预检是唯一防线；
      // Overwrite:F 仅对标准 WebDAV 服务端有效，保留为防御性参数。
      // HEAD 与 MOVE 之间仍有毫秒级 TOCTOU，无法在协议层完全消除。
      function doMove(){
        fetch(src,{method:'MOVE',credentials:'same-origin',
          headers:{'Destination':dest,'Overwrite':'F'}}).then(function(r){
          if(r.ok){
            ok++; moved[srcPath]=1;
            entries.push({
              src:srcPath, dest:destPath, name:targetName,
              thumb:(info&&info.thumb)||'', ts:(info&&info.ts)||0,
              isVid:(info&&info.isVid)?1:0, fsize:(info&&info.fsize)||0
            });
          }
          else if(r.status===412||r.status===409){ conflict++; }
          else { fail++; lastStatus=r.status; }
          step(i+1);
        }).catch(function(){ fail++; step(i+1); });
      }
      fetch(dest,{method:'HEAD',credentials:'same-origin',cache:'no-store'}).then(function(r){
        var st=r.status;
        if(st===404){ doMove(); }
        else if(st===200||st===204){ conflict++; step(i+1); }
        else if(st===405||st===501){
          headBlocked=true; fail++; lastStatus=st; step(i+1);   // 不降级，不覆盖
        }
        else { fail++; lastStatus=st; step(i+1); }             // 401/403/5xx：失败关闭
      }).catch(function(){ fail++; step(i+1); });             // 网络错误：不冒险 MOVE
    }
    function done(){
      if(ok){
        document.querySelectorAll('.grid a.sel').forEach(function(a){
          if(moved[a.getAttribute('data-full')]){ a.parentNode.removeChild(a); }
        });
        if(history.state&&history.state.sel) history.back();
        else window.__exitSel(false);
        if(window.__afterMediaMoved) window.__afterMediaMoved(entries);
      }
      if(cb){ try{ cb(ok,fail,moved,conflict,cancelled); }catch(e){} }
      var msg='已移动 '+ok+' 项'+(targetName?'到「'+targetName+'」':'');
      if(conflict) msg+='；目标已存在同名文件 '+conflict+' 项（未覆盖）';
      if(fail) msg+='；失败 '+fail+' 项'+(lastStatus?'（HTTP '+lastStatus+'）':'');
      if(headBlocked){
        if(cancelled) msg+='；服务端不支持冲突检测，后续 '+cancelled+' 项已取消（未覆盖任何文件）';
        else if(ok>0) msg+='；服务端不支持冲突检测，该项已取消（未覆盖任何文件）';
        else msg+='；当前服务不支持冲突检测，已取消移动（未覆盖任何文件）';
      }
      setTimeout(function(){ alert(msg); },80);
    }
    step(0);
  }

  // 软删除：MOVE 到 06_回收站/<时间戳-随机>/，30 天后由生成器清理
  // 复用 __onDeleted / __onBulkDone 的 UI 更新，失败不假装成功

  // 删除后立刻把文件名写进 deleted_client.json，避免「删完 1 分钟内又被传回来」
  window.__recordDeleted=function(names){
    if(!names||!names.length) return;
    fetch('/相册/deleted_client.json?_='+Date.now(),{cache:'no-store',credentials:'same-origin'})
      .then(function(r){ return r.ok?r.json():{}; })
      .catch(function(){ return {}; })
      .then(function(o){
        o=(o&&typeof o==='object')?o:{};
        var t=Math.floor(Date.now()/1000), add=0;
        names.forEach(function(n){ if(n && !o[n]){ o[n]=t; add++; } });
        if(!add) return null;
        return fetch('/相册/deleted_client.json',{method:'PUT',credentials:'same-origin',
          headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});
      }).catch(function(){});
  };
  window.__softDelete=function(ps, single){
    if(!ps||!ps.length) return;
    if(window.__delBusy) return;                    // 防连点：上一次删除没结束前忽略
    window.__delBusy=1;
    var ok=0, fail=0, lastStatus=0, doneMap={}, finished=false;
    var d=new Date(), p2=function(x){ return x<10?'0'+x:''+x; };
    var tag=''+d.getFullYear()+p2(d.getMonth()+1)+p2(d.getDate())+'-'+
            p2(d.getHours())+p2(d.getMinutes())+p2(d.getSeconds())+'-'+
            Math.random().toString(36).slice(2,6);
    var dir='/06_回收站/'+tag;
    // HTTP 头(Destination)不能含非 ASCII：中文目录必须先编码，否则 fetch 直接抛错
    var dirEnc=encodeURI(dir);
    // 先建批次目录并写入原路径清单，恢复时才知道该回到哪个相册
    var metaBody={items:ps.map(function(u){
      var nm=String(u).split('/').pop();
      var sp=u; try{ sp=new URL(u,location.origin).pathname; }catch(e){}
      return {name:nm, src:sp};
    })};
    var started=false;
    function begin(){ if(started) return; started=true; step(0); }
    fetch(dirEnc,{method:'MKCOL',credentials:'same-origin'})
      .catch(function(){})
      .then(function(){
        return fetch(dirEnc+'/_meta.json',{method:'PUT',credentials:'same-origin',
          headers:{'Content-Type':'application/json'},body:JSON.stringify(metaBody)})
          .catch(function(){});
      })
      .then(begin, begin);
    setTimeout(begin, 1200);      // 兜底：MKCOL/PUT 卡住也要保证最终会删
                                  // 注意：曾在这里多写了一行 step(0)，导致 MOVE 跑两遍、成功提示弹两次
    function step(i){
      if(i>=ps.length){ finish(); return; }
      var src=ps[i], name=String(src).split('/').pop();
      var dest=location.origin+dirEnc+'/'+name;
      var srcPath=src; try{ srcPath=new URL(src,location.origin).pathname; }catch(e){}
      if(doneMap[srcPath]){ step(i+1); return; }
      fetch(src,{method:'MOVE',credentials:'same-origin',
        headers:{'Destination':dest,'Overwrite':'F'}}).then(function(r){
        if(r.ok){ ok++; doneMap[srcPath]=1; }
        else { fail++; lastStatus=r.status; }
        step(i+1);
      }).catch(function(){ fail++; step(i+1); });
    }
    function finish(){
      if(finished) return; finished=true; window.__delBusy=0;
      var okList=ps.filter(function(u){
        try{ return !!doneMap[new URL(u,location.origin).pathname]; }catch(e){ return !!doneMap[u]; }
      });
      try{ window.__recordDeleted(okList.map(function(u){ return String(u).split('/').pop(); })); }catch(e){}
      var msg='已移入回收站 '+ok+' 项（30 天后自动清理）';
      if(fail) msg+='；失败 '+fail+' 项'+(lastStatus?'（HTTP '+lastStatus+'）':'');
      if(ok && single){
        window.__onDeleted(false);                 // 内部会调 __afterMediaDeleted 写 hidden 并重算
        setTimeout(function(){ alert(msg); },90);
      }else if(ok){
        window.__pendingDelete=okList;
        window.__onBulkDone('');                   // 空消息：不弹窗，由下面统一提示
        setTimeout(function(){ alert(msg); },90);
      }else{
        setTimeout(function(){ alert(msg); },90);
      }
    }
  };
  function openMovePicker(ps, mode, excludeP){
    if(!ps||!ps.length) return;
    var box=document.getElementById('picker-list');
    var groups={},order=[];
    var meta=(window.__DATA&&window.__DATA.albums)||(window.__ALBUMS||[]);
    meta.forEach(function(a){
      if(!a.p) return;
      if(window.__CURP && a.p===window.__CURP) return;   // 不列出当前所在相册
      if(excludeP && a.p===excludeP) return;             // 详情页单张移动时排除它所在相册
      if(!groups[a.g]){groups[a.g]=[];order.push(a.g);}
      groups[a.g].push(a);
    });
    if(!order.length){ alert('没有可移动的目标相册'); return; }
    var h='';
    order.forEach(function(g){
      h+='<div style="color:#78787d;font-size:12px;margin:14px 6px 2px">'+g+'</div>';
      groups[g].forEach(function(a){
        h+='<div class="pl" data-p="'+a.p+'">'+a.n+'<small>'+a.c+' 项</small></div>';
      });
    });
    box.innerHTML=h;
    box.querySelectorAll('.pl').forEach(function(el){
      el.onclick=function(){
        var dest=el.getAttribute('data-p');
        var tname=el.childNodes.length?el.childNodes[0].textContent:'';
        history.back();                    // 先关面板，popstate 后历史状态回到上一层
        var tries=0;
        var wait=setInterval(function(){
          tries++;
          if(!document.getElementById('picker').classList.contains('on')||tries>20){
            clearInterval(wait);
            moveToAlbum(ps,dest,tname,function(ok,fail,moved){
              if(mode==='single'&&ok) window.__onDeleted(true);
            });
          }
        },25);
      };
    });
    document.getElementById('picker').classList.add('on');
    try{ history.pushState({pk:1},'','#pk'); }catch(e){}
  }
  // 大图详情页的单张「移动」入口：ps 只有当前这张
  window.__openMovePicker=function(urls,excludeP){ openMovePicker(urls,'single',excludeP); };

  document.getElementById('sel-cancel').onclick=function(){
    if(history.state&&history.state.sel) history.back(); else window.__exitSel(false);
  };
  document.getElementById('sel-all').onclick=function(){
    var list=Array.prototype.slice.call(document.querySelectorAll('.grid:not([data-otd]) a[data-full]'));
    var anyUnsel=list.some(function(a){ return !a.classList.contains('sel'); });
    list.forEach(function(a){ mark(a, anyUnsel); });
  };
  document.getElementById('sel-share').onclick=function(){
    var ps=items().map(function(a){ return a.getAttribute('data-full'); });
    if(!ps.length) return;
    if(window.Android&&window.Android.shareMany) window.Android.shareMany(JSON.stringify(ps));
    else alert('当前环境不支持发送，请更新 App');
  };
  document.getElementById('sel-dl').onclick=function(){
    var ps=items().map(function(a){ return a.getAttribute('data-full'); });
    if(!ps.length) return;
    if(!confirm('确定把选中的 '+ps.length+' 项下载到手机相册？')) return;
    if(window.Android&&window.Android.saveMany) window.Android.saveMany(JSON.stringify(ps));
    else alert('当前环境不支持，请更新 App');
  };
  document.getElementById('sel-del').onclick=function(){
    var ps=items().map(function(a){ return a.getAttribute('data-full'); });
    if(!ps.length) return;
    if(!confirm('把选中的 '+ps.length+' 项移到回收站？30 天后自动清理。')) return;
    window.__softDelete(ps, false);
  };
  document.getElementById('sel-fav').onclick=function(){
    var ps=items().map(function(a){ return a.getAttribute('data-full'); });
    if(!ps.length) return;
    var all=ps.every(function(u){ return window.__favHas && window.__favHas(u); });
    if(window.__favBulk) window.__favBulk(ps, !all);
    // 列表里的红心同步
    ps.forEach(function(u){
      var a=document.querySelector('.grid a[data-full="'+u.replace(/"/g,'\\"')+'"]');
      if(!a) return;
      var ex=a.querySelector('.fav');
      if(!all && !ex){ var sp=document.createElement('span'); sp.className='fav'; sp.textContent='♥'; a.appendChild(sp); }
      else if(all && ex){ ex.remove(); }
    });
    if(navigator.vibrate){ try{ navigator.vibrate(10); }catch(e){} }
    setTimeout(function(){ alert((all?'已取消收藏 ':'已收藏 ')+ps.length+' 项'); },60);
  };
  document.getElementById('sel-move').onclick=function(){
    var ps=items().map(function(a){ return a.getAttribute('data-full'); });
    if(!ps.length) return;
    openMovePicker(ps,'selection');
  };
  document.getElementById('picker').onclick=function(e){
    if(e.target===this){ history.back(); }
  };

  var tx=0, ty=0;
  var HOLD_MS=500;                       // 长按阈值：够久避免误触，又不用等太久
  var EDGE=170;                           // 距离屏幕上下边缘多近开始自动滚动
  var lastPt=null, scrollTimer=null;

  window.__cancelPress=function(){ if(timer){ clearTimeout(timer); timer=null; } pressing=null; };

  function startPress(a,x,y){
    if(document.body.classList.contains('selmode')) return;
    pressing=a; tx=x||0; ty=y||0; clearTimeout(timer);
    timer=setTimeout(function(){
      if(!pressing) return;
      var el=pressing;
      pressing=null;
      enterSel(el);
      // 长按成立后，手指不抬起也立即进入可拖动状态
      dragMode=true; startA=el; lastA=el; movedInSel=false;
      rangeAnchor=el; dragStartPt={x:tx,y:ty}; lastY=ty;
      lastPt={x:tx,y:ty};
      // 注意：这里不要启动边缘自动滚动。长按本身不移动手指，
      // 若此时就滚动，会按“内容坐标→行”的映射把选区扩到整行（首行尤其明显）。
      // 自动滚动等第一次真正的 touchmove 再启动。
    },HOLD_MS);
  }

  function scrollStep(){
    if(!lastPt) return 0;
    var h=window.innerHeight, y=lastPt.y;
    if(y<EDGE) return -Math.max(6, Math.round((EDGE-y)/4));
    if(y>h-EDGE) return Math.max(6, Math.round((y-(h-EDGE))/4));
    return 0;
  }

  // 滚动容器：主界面是当前面板；相册内页仍是 window
  function activeScroller(){
    var t=document.getElementById('pg-timeline'), a=document.getElementById('pg-albums');
    if(t&&a) return (window.curTab==='albums')?a:t;
    return null;
  }
  function tickScroll(){
    var st=scrollStep();
    if(!st || !document.body.classList.contains('selmode')){ stopScroll(); return; }
    var sc=activeScroller();
    if(sc) sc.scrollBy(0, st); else window.scrollBy(0, st);
    if(lastPt){
      var a=null;
      if(sc){
        // offsetTop 在不同月份 section 里会重置，不能跨 section 二分。
        // 进边缘自动滚动时缓存一次「内容坐标下的绝对 top」，再按行 + 最近 x 选格。
        if(!scrollCells || scrollCells.length!==document.querySelectorAll('.grid:not([data-otd]) a[data-full]').length){
          var baseTop=sc.getBoundingClientRect().top - sc.scrollTop;
          scrollCells=Array.prototype.slice.call(document.querySelectorAll('.grid:not([data-otd]) a[data-full]'));
          scrollTops=scrollCells.map(function(c){ return c.getBoundingClientRect().top - baseTop; });
        }
        var contentY=lastPt.y - sc.getBoundingClientRect().top + sc.scrollTop;
        var lo=0, hi=scrollTops.length-1, ans=0;
        while(lo<=hi){
          var mid=(lo+hi)>>1;
          if(scrollTops[mid]<=contentY){ ans=mid; lo=mid+1; } else { hi=mid-1; }
        }
        a=scrollCells[ans]||null;
        if(a){
          var rowTop=scrollTops[ans], best=a, bestD=1e9, k;
          for(k=ans;k>=0 && Math.abs(scrollTops[k]-rowTop)<3;k--){
            var rl=scrollCells[k].getBoundingClientRect();
            var dl=Math.abs(rl.left+rl.width/2-lastPt.x);
            if(dl<bestD){ bestD=dl; best=scrollCells[k]; }
          }
          for(k=ans+1;k<scrollCells.length && Math.abs(scrollTops[k]-rowTop)<3;k++){
            var rr=scrollCells[k].getBoundingClientRect();
            var dr=Math.abs(rr.left+rr.width/2-lastPt.x);
            if(dr<bestD){ bestD=dr; best=scrollCells[k]; }
          }
          a=best;
        }
      }else{
        var el=document.elementFromPoint(lastPt.x, lastPt.y);
        a=el&&el.closest?el.closest('.grid a[data-full]'):null;
      }
      if(a && a!==lastA){ movedInSel=true; lastA=a; selectRange(a); }
    }
  }
  function startScroll(){ if(!scrollTimer){ scrollCells=null; scrollTops=null; scrollTimer=setInterval(tickScroll,16); } }
  function stopScroll(){ if(scrollTimer){ clearInterval(scrollTimer); scrollTimer=null; } }
  function maybeScroll(){ if(scrollStep()!==0) startScroll(); else stopScroll(); }

  var cellTops=null;
  var scrollCells=null, scrollTops=null;
  function __cellAtY(contentY){
    if(!allCells) allCells=Array.prototype.slice.call(document.querySelectorAll('.grid:not([data-otd]) a[data-full]'));
    if(!cellTops||cellTops.length!==allCells.length){
      cellTops=allCells.map(function(c){ return c.offsetTop; });
    }
    var lo=0, hi=cellTops.length-1, ans=0;
    while(lo<=hi){
      var mid=(lo+hi)>>1;
      if(cellTops[mid]<=contentY){ ans=mid; lo=mid+1; } else { hi=mid-1; }
    }
    return allCells[ans]||null;
  }

  document.addEventListener('touchstart',function(e){
    justEntered=false;
    var a=e.target.closest && e.target.closest('.grid a[data-full]');
    if(!a) return;
    if(document.body.classList.contains('selmode')){
      dragMode=true; startA=a; lastA=a; movedInSel=false;
      rangeAnchor=a; dragStartPt=null;
      var p0=e.touches[0];
      if(p0){
        lastPt={x:p0.clientX,y:p0.clientY};
        dragStartPt={x:p0.clientX,y:p0.clientY};
        lastY=p0.clientY;
      }
      return;                                  // 单击不要触发区间选择
    }
    var pt=e.touches[0];
    startPress(a, pt?pt.clientX:0, pt?pt.clientY:0);
  },{passive:true});

  document.addEventListener('touchmove',function(e){
    var t=e.touches[0];
    if(timer && t){
      if(Math.abs(t.clientX-tx)>10 || Math.abs(t.clientY-ty)>10) window.__cancelPress();
    }
    if(!document.body.classList.contains('selmode')||!dragMode) return;
    if(t) lastPt={x:t.clientX,y:t.clientY};
    // 选模式下接管所有手势：竖滑=浏览列表，横滑=延伸选区（系统相册方案）
    if(e.cancelable) e.preventDefault();
    if(!axis){
      if(!dragStartPt){ dragStartPt={x:lastPt.x,y:lastPt.y}; return; }
      var ddx=Math.abs(lastPt.x-dragStartPt.x), ddy=Math.abs(lastPt.y-dragStartPt.y);
      if(Math.max(ddx,ddy)<DRAG_THRESH) return;   // 手指抖动，不算
      axis=(ddy>ddx*1.15)?'v':'h';                // 方向锁：一旦确定本次触摸不再改变
      if(axis==='h'){ movedInSel=true; if(rangeAnchor) mark(rangeAnchor,true); }
      // 竖滑时保留本次触摸起点的 y，第一次 move 就能把整段位移滚掉，
      // 否则快速上滑只有 1-2 个 touchmove 时会“滑了没反应”。
      lastY=(axis==='v'&&dragStartPt)?dragStartPt.y:lastPt.y;
    }
    if(axis==='v'){                               // 竖滑：手动滚动列表
      var scv=activeScroller();
      var dy=lastPt.y-lastY;
      if(scv) scv.scrollTop-=dy;
      else window.scrollBy(0,-dy);                // 相册内页没有 .pane-page，用 window
      lastY=lastPt.y;
      return;
    }
    if(lastPt){                                   // 横滑：延伸选区
      var el=document.elementFromPoint(lastPt.x,lastPt.y);
      var a=el&&el.closest?el.closest('.grid a[data-full]'):null;
      if(!a){                                     // 被覆盖层挡住时按内容坐标兜底
        var scf=(typeof activeScroller==='function')?activeScroller():null;
        if(scf){
          var prf=scf.getBoundingClientRect();
          a=__cellAtY(lastPt.y-prf.top+scf.scrollTop);
        }
      }
      if(a && a!==lastA){ lastA=a; selectRange(a); }
    }
    maybeScroll();
  },{passive:false});

  function endTouch(){
    window.__cancelPress();
    stopScroll();
    dragMode=false; lastA=null; dragSet=[]; lastPt=null;
    dragStartPt=null; rangeAnchor=null; axis=null; cellTops=null;
    setTimeout(function(){ movedInSel=false; }, 50);
  }
  document.addEventListener('touchend',endTouch,{passive:true});
  document.addEventListener('touchcancel',endTouch,{passive:true});

  document.addEventListener('click',function(e){
    if(!document.body.classList.contains('selmode')) return;
    var a=e.target.closest && e.target.closest('.grid a[data-full]');
    if(!a) return;
    e.preventDefault(); e.stopPropagation();
    if(justEntered){ justEntered=false; return; }  // 长按后补发的 click，忽略
    if(movedInSel) return;   // 拖动产生的合成点击，忽略
    mark(a);
  },true);

  // 注意：不要在这里绑定 mousedown。安卓 WebView 的点击会补发合成鼠标事件，
  // 合成 mousedown 会重新起一个没人清理的长按计时器，导致点开照片后误入多选。

  // 返回手势分级：信息面板 > 大图 > 移动面板 > 多选，逐层退出。
  // 信息面板叠在大图上面（z-index 120 > 99），必须先判断 info；
  // 否则 popstate 会把大图一起关掉，并留下一条 {v:1}，表现为之后有一次“空返回”。
  // 注意：Android WebView 的 popstate 事件里 e.state 常为 null，
  // 所以这里不读 e.state，而是按「当前哪个层开着」来判断。
  window.addEventListener('popstate',function(){
    var nf=document.getElementById('info');
    if(nf&&nf.classList.contains('on')){ nf.classList.remove('on'); return; }
    var pk=document.getElementById('picker');
    if(pk&&pk.classList.contains('on')){ pk.classList.remove('on'); return; }
    var v=document.getElementById('viewer');
    if(v&&v.classList.contains('on')){ window.__closeViewer(); return; }
    var ss=document.getElementById('syncsheet');
    if(ss){ closeSyncSheet(); return; }
    if(document.body.classList.contains('albmode')){ if(window.__exitAlbumEdit) __exitAlbumEdit(false); return; }
    if(document.body.classList.contains('selmode')){ window.__exitSel(false); return; }
    var sb=document.getElementById('sbar');
    if(sb&&sb.classList.contains('on')){ if(window.__closeSearch) window.__closeSearch(); return; }
    if(window.__tabPushed && window.__curTab==='albums'){
      window.__tabPushed=0;
      window.__curTab='timeline';
      try{ history.replaceState(null,'',location.pathname+location.search); }catch(e){}
      if(window.__switchTab) window.__switchTab('timeline');
      return;
    }
  });
  update();
})();
"""

INDEX_JS = r"""
var DATA=null,TL=null,DUR={},STATUS=null,Q='',COLS=3,MODE='all',FAV={},OTD=[],SIM=[];
var TVER='TVER_PLACEHOLDER';   // 模板版本：拼在相册链接后面，避免手机缓存旧页面
var BIG_MIN=50*1024*1024;
function q(s){return document.querySelector(s);}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function cell(p,idx){
  var dv=DUR[p[1]]; if(dv && dv.length===2) dv=dv[1];   // durations.json 的值是 [mtime, 时长]
  var d=(p[3]===1 && dv)?'<span class="dur">'+dv+'</span>':'';
  return '<a href="#" data-i="'+idx+'" data-full="'+p[1]+'">'+
    '<img loading="lazy" alt="" src="'+p[0]+'">'+
    (p[3]===1?'<span class="play">▶</span>':'')+d+
    (FAV[p[1]]?'<span class="fav">♥</span>':'')+'</a>';
}
function favLoad(){
  try{ FAV=JSON.parse(localStorage.getItem('nas_fav')||'{}')||{}; }catch(e){ FAV={}; }
}
function favSave(){
  try{ localStorage.setItem('nas_fav',JSON.stringify(FAV)); }catch(e){}
}
function favHas(full){ return !!FAV[full]; }
function favToggle(full){
  if(!full) return false;
  if(FAV[full]) delete FAV[full]; else FAV[full]=1;
  favSave();
  return !!FAV[full];
}
window.__favHas=favHas; window.__favToggle=favToggle;
window.__favBulk=function(urls,want){
  if(!urls||!urls.length) return;
  for(var i=0;i<urls.length;i++){
    var u=urls[i]; if(!u) continue;
    if(want) FAV[u]=1; else delete FAV[u];
  }
  favSave();
  var cb=document.querySelector('.chips b[data-m="fav"]');
  if(cb) cb.textContent='收藏 '+Object.keys(FAV).length;
};
function applyCols(n){
  COLS=n;
  document.documentElement.style.setProperty('--cols',n);
  try{ localStorage.setItem('nas_cols',n); }catch(e){}
  var b=document.getElementById('cols'); if(b) b.textContent=n;
}
function renderStat(){
  var el=document.getElementById('stat'); if(!el) return;
  var sp=el.querySelector('span');
  if(!STATUS||!STATUS.generated){ el.classList.add('warn'); if(sp) sp.textContent='—'; return; }
  var mins=Math.floor((Date.now()/1000-STATUS.generated)/60);
  el.classList.toggle('warn', mins>=10);
  if(sp) sp.textContent = mins<1?'刚刚':(mins<60?mins+'分钟前':Math.floor(mins/60)+'小时前');
}
// ===== 同步（把手机上的 Syncthing 拉起来，回来后自动刷新）=====
function __toast(m){
  var t=document.getElementById('toast');
  if(!t){ t=document.createElement('div'); t.id='toast'; document.body.appendChild(t); }
  t.textContent=m; t.classList.add('on');
  clearTimeout(t.__tm); t.__tm=setTimeout(function(){ t.classList.remove('on'); },2200);
}
function closeSyncSheet(){ var d=document.getElementById('syncsheet'); if(d&&d.parentNode) d.parentNode.removeChild(d); }
function closeSyncSheetBack(){
  if(history.state&&history.state.ss){ history.back(); return; }   // 交给 popstate 收尾
  closeSyncSheet();
}
function checkNewPhotos(manual){
  fetch('/相册/photos.json?_='+Date.now(),{cache:'no-store',credentials:'same-origin'})
    .then(function(r){ return r.ok?r.json():null; })
    .then(function(d){
      if(!d||!d.photos) return;
      var now=(DATA&&DATA.photos)?DATA.photos.length:0;
      if(d.photos.length!==now){ location.reload(); return; }
      if(manual) __toast('已是最新，没有新照片');
    }).catch(function(){ if(manual) __toast('检查失败，请检查网络'); });
}
window.__afterSyncReturn=function(){ startWaitPoll(); };
window.__syncFail=function(m){ alert(m||'打不开 Syncthing'); };
// 自动刷新可能形成循环（比如 status.json 没拿到），加个保险：3 分钟内最多刷 5 次
function __safeReload(){
  var n=0, t=0;
  try{ n=+(sessionStorage.getItem('nas_rl_n')||0); t=+(sessionStorage.getItem('nas_rl_t')||0); }catch(e){}
  if(Date.now()-t > 180000) n=0;
  n++;
  try{ sessionStorage.setItem('nas_rl_n', String(n));
       sessionStorage.setItem('nas_rl_t', String(Date.now())); }catch(e){}
  if(n>5){ showNewBar(); return; }
  location.reload();
}
// 同步后不等你手动刷新：每 3 秒问一次 status.json（92 字节），生成器一跑完就自动重载
var __pollTimer=null, __pollUntil=0, __baseGen=0, __polled=false;
function startWaitPoll(){
  var gen=(STATUS&&STATUS.generated)||0;
  __baseGen=gen;
  __pollUntil=Date.now()+3*60*1000;
  try{ sessionStorage.setItem('nas_sync_at', String(Date.now())); }catch(e){}
  if(!__polled){ __polled=true; __toast('正在等待新照片（相册每分钟刷新一次）'); }
  if(__pollTimer) clearInterval(__pollTimer);
  __pollTimer=setInterval(function(){
    if(Date.now()>__pollUntil){ clearInterval(__pollTimer); __pollTimer=null; return; }
    if(document.hidden) return;
    fetch('/相册/status.json?_='+Date.now(),{cache:'no-store',credentials:'same-origin'})
      .then(function(r){ return r.ok?r.json():null; })
      .then(function(d){
        if(!d) return; __pollFails=0;
        var now=(DATA&&DATA.photos)?DATA.photos.length:0;
        if(!__baseGen){ __baseGen=d.generated||0; return; }
        if(typeof d.photos==='number' && now && d.photos>now){
          __safeReload();
        }
      }).catch(function(){ __pollFails=(__pollFails||0)+1;
        if(__pollFails>=2 && typeof showOffBar==='function') showOffBar(); });
  },3000);
}
document.addEventListener('visibilitychange',function(){
  if(document.hidden) return;
  var at=0; try{ at=+(sessionStorage.getItem('nas_sync_at')||0); }catch(e){}
  if(at && Date.now()-at < 10*60*1000) startWaitPoll();
});
function openSyncSheet(){
  if(document.getElementById('syncsheet')) return;
  var mins=(STATUS&&STATUS.generated)?Math.floor(Date.now()/1000-STATUS.generated):-1;
  var ago=mins<0?'—':(mins<1?'刚刚':(mins<60?mins+' 分钟前':Math.floor(mins/60)+' 小时前'));
  var n=(DATA&&DATA.photos)?DATA.photos.length:0;
  var d=document.createElement('div'); d.id='syncsheet';
  d.innerHTML='<div class="msk"></div><div class="bx">'
    +'<h3>手机照片上传</h3>'
    +'<p>相册更新：'+ago+'　当前 '+n+' 张照片/视频</p>'
    +'<p style="color:#7a7a80">打开相册会自动把手机里的新照片补传上来，传完自动刷新；也可以手动点下面按钮。</p>'
    +'<div class="btns"><button class="main" id="sy-up">上传新照片</button>'
    +'<button id="sy-c">关闭</button></div>'
    +'<div class="btns" style="margin-top:8px"><button id="sy-re">刷新列表</button></div>'
    +'<p id="sy-srv" style="margin-top:14px;font-size:12px;color:#7a7a80">服务器：'+(function(){
        try{ return location.protocol+'//'+location.host; }catch(e){ return '—'; }})()+'</p>'
    +'<div class="btns" style="margin-top:6px"><button id="sy-srv2">修改服务器地址</button></div>'
    +'</div>';
  document.body.appendChild(d);
  try{ if(!(history.state&&history.state.ss)) history.pushState({ss:1},'','#ss'); }catch(e){}
  d.querySelector('.msk').onclick=closeSyncSheetBack;
  document.getElementById('sy-c').onclick=closeSyncSheetBack;
  document.getElementById('sy-re').onclick=function(){ closeSyncSheet(); checkNewPhotos(true); };
  var srvBtn=document.getElementById('sy-srv2');
  if(srvBtn) srvBtn.onclick=function(){
    if(window.Android&&window.Android.openSetup){
      try{ window.Android.openSetup(); }catch(e){}
      closeSyncSheet();
    }else{
      __toast('只有在「我的相册」App 里才能改，浏览器请直接改地址栏');
    }
  };
  var upBtn=document.getElementById('sy-up');
  if(upBtn) upBtn.onclick=function(){
    if(!(window.Android&&window.Android.startUploadAll)){ __toast('请用「我的相册」App 打开'); return; }
    closeSyncSheet();
    var r='';
    try{ r=window.Android.startUploadAll(); }catch(e){}
    if(r==='perm') __upChip('需要相册权限，请在弹出的窗口里点允许', true);
    else __upChip('正在检查手机相册…', true);
  };
  try{
    if(window.Android&&window.Android.uploadStatus){
      var us=JSON.parse(window.Android.uploadStatus()||'{}');
      if(us && us.state && us.state!=='idle'){
        var pu=document.createElement('p');
        pu.style.fontSize='11.5px'; pu.style.opacity='.6';
        pu.textContent='上次上传：'+(us.state==='done'
          ? ('新传 '+(us.added||0)+' · 跳过 '+(us.skip||0)+' · 失败 '+(us.fail||0))
          : ('状态 '+us.state));
        d.querySelector('.bx').appendChild(pu);
      }
    }
  }catch(e){}
}
window.__openSyncSheet=openSyncSheet;
// ===== 手机相册上传（App 1.15 起，替代 Syncthing）=====
var __upHideTimer=null;
function __upChip(txt, keep, onTap){
  var el=document.getElementById('upbar');
  if(!el){ el=document.createElement('div'); el.id='upbar'; document.body.appendChild(el); }
  el.textContent=txt; el.style.display='flex';
  el.style.cursor = onTap ? 'pointer' : 'default';
  el.onclick = onTap || null;
  if(__upHideTimer){ clearTimeout(__upHideTimer); __upHideTimer=null; }
  if(!keep) __upHideTimer=setTimeout(function(){ var e=document.getElementById('upbar'); if(e) e.remove(); }, 5000);
}
function __cancelUpload(){
  try{ if(window.Android&&window.Android.cancelUpload){ window.Android.cancelUpload(); __upChip('正在停止…', true); } }catch(e){}
}
window.__upProg=function(s){
  if(!s) return;
  if(s.state==='listing'||s.state==='checking'){ __upChip('正在对比 NAS 上已有的照片…', true); return; }
  if(s.state==='uploading'){
    __upChip('上传中 '+Math.min(s.done+1, s.total)+'/'+s.total+(s.cur?(' · '+s.cur):'')+'（点这里停止）',
             true, __cancelUpload); return;
  }
  if(s.state==='done'){
    if(s.media===0){ __upChip('没读到手机相册（权限或媒体库问题）', false); return; }
    var added=s.added||0;
    if(!added && !(s.fail||0)){          // 没有新照片、也没失败：安静收工，不打扰
      var b=document.getElementById('upbar'); if(b) b.remove();
      return;
    }
    var msg = added ? ('已上传 '+added+' 张') : '没有新照片，已是最新';
    if(s.skip) msg += '，跳过 '+s.skip+' 张已在 NAS';
    if(s.fail) msg += '，失败 '+s.fail+' 张';
    if(s.cap && added >= s.cap) msg += '（本次先传 '+s.cap+' 张，剩下的下次继续）';
    __upChip(msg, false);
    if(added>0) startWaitPoll();
    return;
  }
  if(s.state==='error'){ __upChip('上传出错了，稍后再试', false); }
};
window.__upPerm=function(ok){
  if(ok) __upChip('已获得相册权限，开始上传…', true);
  else __upChip('没有相册权限：去系统设置→应用→我的相册→权限里允许', false);
};
function startAutoUpload(){
  var on='1';
  try{ on=localStorage.getItem('nas_autoupload')||'1'; }catch(e){}
  if(on!=='1') return;
  if(!(window.Android&&window.Android.startUploadAll)) return;
  var last=0;
  try{ last=+(sessionStorage.getItem('nas_up_at')||0); }catch(e){}
  if(Date.now()-last < 60*1000) return;
  try{ sessionStorage.setItem('nas_up_at', String(Date.now())); }catch(e){}
  setTimeout(function(){
    try{
      var r=window.Android.startUploadAll();
      if(r==='perm') __upChip('需要相册权限，请在弹出的窗口里允许…', true);
      else if(r==='busy') __upChip('正在上传中…', true);
      else __upChip('正在检查手机相册…', true);
    }catch(e){}
  }, 1500);
}
window.__syncStatus=function(){};   // Syncthing 已弃用，这里留空实现
// 打开相册时自动唤起（默认关，开了也要 5 分钟内只触发一次，避免返回后刷新又弹）
// 空闲也盯着服务端：Syncthing 在后台传完、生成器跑完，相册自己跟上
var __idleTimer=null, __lastGen=0, __lastN=0;
function startIdlePoll(){
  __lastGen=(STATUS&&STATUS.generated)||0;
  __lastN=(DATA&&DATA.photos)?DATA.photos.length:0;
  if(__idleTimer) return;
  __idleTimer=setInterval(function(){
    if(document.hidden) return;
    fetch('/相册/status.json?_='+Date.now(),{cache:'no-store',credentials:'same-origin'})
      .then(function(r){ return r.ok?r.json():null; })
      .then(function(d){
        if(!d) return; __pollFails=0;
        if(typeof d.photos!=='number'){ __lastGen=d.generated||__lastGen; return; }
        if(!__lastN){ __lastN=d.photos; __lastGen=d.generated||__lastGen; return; }
        // 只有「多出新照片」才刷新；数量不变或变少都不打扰你
        var grew=(d.photos>__lastN);
        __lastN=d.photos;
        __lastGen=d.generated||__lastGen;
        if(!grew) return;
        var tl=document.getElementById('timeline');
        var vw=document.getElementById('viewer');
        var safe=!(vw&&vw.classList.contains('on'))
              && !document.body.classList.contains('selmode')
              && !document.getElementById('syncsheet')
              && (!tl||tl.scrollTop<200);
        if(safe) __safeReload(); else showNewBar();
      }).catch(function(){ __pollFails=(__pollFails||0)+1;
        if(__pollFails>=3 && typeof showOffBar==='function') showOffBar(); });
  },60000);
}
// App 上传完新照片后会调用：等生成器把新图写进 photos.json，再刷新（否则刷新了也看不见）
window.__afterUploadDone=function(n){
  n=+n||0;
  if(n<=0) return;
  var base=(window.DATA&&window.DATA.photos)?window.DATA.photos.length:0;
  var t0=Date.now();
  function busy(){
    var v=document.getElementById('viewer');
    return (v&&v.classList.contains('on'))||!!document.getElementById('syncsheet')
        ||document.body.classList.contains('selmode')||document.body.classList.contains('albmode');
  }
  function tick(){
    if(Date.now()-t0>30000){ showNewBar(n); return; }   // 生成器一分钟一轮，等太久就先给提示条
    fetch('photos.json?_='+Date.now(),{cache:'no-store',credentials:'same-origin'})
      .then(function(r){ return r.ok?r.json():null; })
      .then(function(d){
        if(d&&d.photos&&d.photos.length>base){
          if(busy()){ showNewBar(n); return; }        // 正在看图/操作：只提示，不打断
          try{ __toast('已同步 '+n+' 张新照片'); }catch(e){}
          setTimeout(function(){ location.reload(); }, 450);
          return;
        }
        setTimeout(tick, 2500);
      })
      .catch(function(){ setTimeout(tick, 2500); });
  }
  setTimeout(tick, 1200);
};
function showNewBar(n){
  if(document.getElementById('newbar')) return;
  var d=document.createElement('div'); d.id='newbar';
  d.innerHTML='<span>相册有更新</span><b>点击刷新</b>';
  d.onclick=function(){ location.reload(); };
  document.body.appendChild(d);
  setTimeout(function(){ if(document.getElementById('newbar')) d.remove(); },8000);
}
function bindGrids(root){
  root.querySelectorAll('.grid').forEach(function(g){
    if(g.__bound) return; g.__bound=1;
    g.addEventListener('click',function(e){
      if(window.__cancelPress) window.__cancelPress();
      if(document.body.classList.contains('selmode')) return;
      var a=e.target.closest('a'); if(!a) return; e.preventDefault();
      var items=JSON.parse(g.getAttribute('data-list'));
      // 按路径精确匹配：移动/删除后 data-i 可能与列表错位，用 data-i 会打开成另一张
      var full0=a.getAttribute('data-full'), idx0=-1;
      for(var k0=0;k0<items.length;k0++){ if(items[k0][0]===full0){ idx0=k0; break; } }
      if(idx0<0){
        alert('这张照片已不在当前列表（可能刚被移走），刷新后会消失。\n为避免误操作，已取消打开。');
        return;
      }
      // 首页 data-list 只有 [full,isVid]；从 DATA.photos 补齐 size/album/ts，信息面板不再显示 undefined
      var by=window.__photoByFull||{};
      var viewItems=items.map(function(it){
        var p=by[it[0]];
        return p ? [it[0], it[1], p[5], p[4], p[2]] : [it[0], it[1], 0, '', 0];
      });
      __openViewer(viewItems, idx0, a);
    });
  });
  root.querySelectorAll('img').forEach(function(im){
    if(im.complete) im.classList.add('ld');
    else im.onload=function(){ im.classList.add('ld'); };
  });
}
function renderOtd(){
  var slot=document.getElementById('otd-slot'); if(!slot) return;
  if(!(MODE==='all' && !Q && OTD && OTD.length)){ slot.innerHTML=''; return; }
  var list=OTD.map(function(p){ return [p[1],p[3]]; });
  var openOtd=false;
  try{ openOtd=localStorage.getItem('nas_otd_open')==='1'; }catch(e){}
  slot.innerHTML='<section class="otd'+(openOtd?'':' collapsed')+'">'
    +'<div class="mhead" id="otd-head"><b>那年今日</b><span>'+OTD.length+' 项</span>'
    +'<i class="chev">\u203a</i></div>'
    +'<div class="grid" data-otd="1" data-list=\''+JSON.stringify(list)+'\'>'
    +OTD.map(function(p,idx){ return cell(p,idx); }).join('')+'</div></section>';
  bindGrids(slot);
  var oh=document.getElementById('otd-head');
  if(oh) oh.onclick=function(e){
    e.stopPropagation();
    var sec=slot.querySelector('.otd'); if(!sec) return;
    var now=sec.classList.toggle('collapsed');
    try{ localStorage.setItem('nas_otd_open', now?'0':'1'); }catch(e){}
    if(navigator.vibrate){ try{ navigator.vibrate(8); }catch(e){} }
  };
}
function renderSim(tl){
  if(!SIM.length){
    tl.innerHTML='<div class="chips"><b data-m="all">全部</b><b data-m="sim" class="on">相似 0</b></div>'
      +'<p style="color:#8a8a90;padding:24px 8px;font-size:13px">没有找到连拍/相似照片。</p>';
    TL={order:[],mode:'sim'};
    renderOtd();
    tl.querySelectorAll('.chips b').forEach(function(b){
      b.onclick=function(){ MODE=b.getAttribute('data-m'); renderTimeline(true); };
    });
    return;
  }
  var h='<div class="chips"><b data-m="all" class="">全部</b>'
    +'<b data-m="sim" class="on">相似 '+SIM.length+'</b></div>';
  SIM.forEach(function(g,gi){
    var list=g.map(function(p){ return [p[1],p[3]]; });
    h+='<section><div class="mhead"><b>相似组 '+(gi+1)+'</b><span>'+g.length+' 张</span></div>'
      +'<div class="grid" data-list=\''+JSON.stringify(list)+'\'>'
      +g.map(function(p,idx){ return cell(p,idx); }).join('')+'</div></section>';
  });
  tl.innerHTML=h;
  TL={order:[],mode:'sim'};
  bindGrids(tl);
  renderOtd();
  tl.querySelectorAll('.chips b').forEach(function(b){
    b.onclick=function(){ MODE=b.getAttribute('data-m'); renderTimeline(true); };
  });
}
function renderTimeline(force){
  if(TL && !force) return;
  var tl=q('#timeline');
  if(force) tl.innerHTML='';
  if(MODE==='sim'){ renderSim(tl); return; }
  var groups={},order=[];
  var src=DATA.photos;
  if(MODE==='fav'){ src=DATA.photos.filter(function(p){ return !!FAV[p[1]]; }); }
  else if(MODE==='big'){ src=DATA.photos.filter(function(p){ return (p[5]||0)>=BIG_MIN; })
                                       .sort(function(a,b){ return (b[5]||0)-(a[5]||0); }); }
  if(Q){
    src=DATA.photos.filter(function(p){
      try{ return decodeURIComponent(p[1]).toLowerCase().indexOf(Q)>=0; }catch(e){ return false; }
    });
  }
  if(!src.length){
    var emptyMsg = Q ? '没有匹配「'+Q+'」的照片'
                : (MODE==='fav' ? '还没有收藏。点开照片，按底部的「收藏」。'
                : (MODE==='big' ? '没有超过 50MB 的文件。' : '没有照片'));
    tl.innerHTML='<p style="color:#8a8a90;padding:24px 8px;font-size:13px">'+emptyMsg+'</p>';
    TL={order:[],q:Q,mode:MODE}; renderOtd(); return;
  }
  src.forEach(function(p){
    var d=new Date(p[2]*1000),k=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0');
    if(!groups[k]){groups[k]=[];order.push(k);}
    groups[k].push(p);
  });
  var html='';
  order.forEach(function(k){
    var arr=groups[k];
    var y=k.split('-')[0],m=parseInt(k.split('-')[1],10);
    var list=arr.map(function(p){return [p[1],p[3]];});
    html+='<section><div class="mhead"><b>'+y+'年'+m+'月</b><span>'+arr.length+' 项</span></div>'+
      '<div class="grid" data-list=\''+JSON.stringify(list)+'\'>'+
      arr.map(function(p,idx){return cell(p,idx);}).join('')+'</div></section>';
  });
  // 顶部：筛选 chips（全部 / 收藏 / 大文件）
  var favN=Object.keys(FAV).length;
  var bigN=DATA.photos.filter(function(p){ return (p[5]||0)>=BIG_MIN; }).length;
  html='<div class="chips">'
    +'<b data-m="all" class="'+(MODE==='all'?'on':'')+'">全部</b>'
    +'<b data-m="fav" class="'+(MODE==='fav'?'on':'')+'">收藏 '+favN+'</b>'
    +'<b data-m="big" class="'+(MODE==='big'?'on':'')+'">大文件 '+bigN+'</b>'
    +'<b data-m="sim" class="'+(MODE==='sim'?'on':'')+'">相似 '+SIM.length+'</b>'
    +'</div>'+html;

  tl.innerHTML=html;
  TL={order:order,mode:MODE,q:Q};
  bindGrids(tl);
  renderOtd();
  tl.querySelectorAll('.chips b').forEach(function(b){
    b.onclick=function(){ MODE=b.getAttribute('data-m'); renderTimeline(true); };
  });
}
function renderAlbums(){
  var box=q('#albums');
  if(box.__done) return; box.__done=1;
  var trashN=(window.__TRASH_N||0);
  box.innerHTML='<div class="trashrow">'
    +'<a class="trashbar" href="/相册/回收站.html">'
    +'<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" '
    +'stroke-linecap="round"><path d="M4 7h16"/><path d="M9 7V5h6v2"/><path d="M6 7l1 13h10l1-13"/></svg>'
    +'<span>回收站</span><b>'+(trashN?trashN+' 项':'清空')+'</b></a>'
    +'<a class="managebar" id="alb-manage">管理</a>'
    +'<a class="managebar" id="alb-new">新建</a></div>'
    +'<div class="albums">'+applyAlbumPending(DATA.albums).map(function(a){
    var ahref=a.pending ? 'javascript:void(0)' : ('/相册/'+encodeURIComponent(a.g)+'/'+encodeURIComponent(a.n)+'/index.html?v='+TVER);
    return '<a class="acard'+(a.pending?' pend':'')+'" data-g="'+esc(a.g)+'" data-n="'+esc(a.n)+'" data-p="'+esc(a.p||'')+'" href="'+ahref+'">'+
      '<i class="ckb"></i>'+
      (a.cv?'<img loading="lazy" alt="" src="'+a.cv+'">':'<div style="aspect-ratio:1"></div>')+
      '<span class="gtag">'+esc(a.g)+'</span>'+
      '<div class="m"><div class="n">'+esc(a.n)+'</div><div class="c">'+(a.pending?'生成中…':a.c+' 项')+'</div></div></a>';
  }).join('')+'</div>';
  var mb=document.getElementById('alb-manage');
  if(mb) mb.onclick=function(){ __enterAlbumEdit(null); };
  var nb=document.getElementById('alb-new');
  if(nb) nb.onclick=openNewAlbum;
  bindGrids(box);
  initAlbumSort(box);
  // 回收站数量现场取：生成器每分钟才重建，删完立刻看这里会显示旧数字
  function setTrashN(n){
    var b=box.querySelector('.trashbar b');
    if(b) b.textContent = n>0 ? n+' 项' : '清空';
    window.__TRASH_N=n;
  }
  try{
    fetch('/06_回收站/?json&_='+Date.now(),{credentials:'same-origin',cache:'no-store'})
      .then(function(r){ return r.ok?r.json():null; })
      .then(function(d){
        if(!d||!d.paths) return;
        var dirs=d.paths.filter(function(p){
          return p.path_type==='Dir' && /^\d{8}-\d{6}-[a-z0-9]{4}$/.test(p.name); });
        if(!dirs.length){ setTrashN(0); return; }
        return Promise.all(dirs.map(function(p){
          return fetch('/06_回收站/'+encodeURIComponent(p.name)+'/?json&_='+Date.now(),
                       {credentials:'same-origin',cache:'no-store'})
            .then(function(r){ return r.ok?r.json():null; }).catch(function(){ return null; });
        })).then(function(all){
          var n=0, miss=false;
          all.forEach(function(a){
            if(!a){ miss=true; return; }
            n+=(a.paths||[]).filter(function(f){
              return f.path_type==='File' && f.name!=='_meta.json'; }).length;
          });
          if(!miss) setTrashN(n);
        });
      }).catch(function(){});
  }catch(e){}
}
var curTab='timeline';
function applyPager(dx, anim, idx){
  var p=document.getElementById('pager');
  var i=(idx===undefined)?(curTab==='albums'?1:0):idx;
  p.style.transition=anim?'transform .26s cubic-bezier(.22,.8,.3,1)':'none';
  p.style.transform='translateX(calc(-'+(i*50)+'% + '+(dx||0)+'px))';
}
function saveScroll(){
  try{
    var t=document.getElementById('pg-timeline'), a=document.getElementById('pg-albums');
    if(t) sessionStorage.setItem('nas_tl', t.scrollTop);
    if(a) sessionStorage.setItem('nas_alb', a.scrollTop);
  }catch(e){}
}
function restoreScroll(t){
  try{
    var el=document.getElementById(t==='albums'?'pg-albums':'pg-timeline');
    var v=sessionStorage.getItem(t==='albums'?'nas_alb':'nas_tl');
    if(el&&v) el.scrollTop=parseInt(v,10)||0;
  }catch(e){}
}
window.__switchTab=function(t){ switchTab(t); };
function goTab(t, anim){
  if(t===curTab) return;
  if(t==='albums'){
    try{ history.pushState({tab:'albums'},'','#albums'); window.__tabPushed=1; }catch(e){}
  }else if(t==='timeline'){
    window.__tabPushed=0;
    try{ history.replaceState(null,'',location.pathname+location.search); }catch(e){}   // 别把 #albums 留着，刷新会跳回相册
  }
  switchTab(t, anim);
}
window.__goTab=goTab;
function switchTab(t, anim){
  curTab=t; window.__curTab=t;
  try{sessionStorage.setItem('nas_tab',t);}catch(e){}
  q('#b-timeline').classList.toggle('on',t==='timeline');
  q('#b-albums').classList.toggle('on',t==='albums');
  q('#title').textContent=t==='timeline'?'照片':'相册';
  if(t==='timeline'){ renderTimeline(); window.__bindScrub && window.__bindScrub(document.getElementById('pg-timeline')); }
  else { renderAlbums(); window.__bindScrub && window.__bindScrub(document.getElementById('pg-albums')); }
  applyPager(0, anim!==false);
  restoreScroll(t);
}
(function(){
  var pg=document.getElementById('pager');
  ['pg-timeline','pg-albums'].forEach(function(id){
    var el=document.getElementById(id);
    if(el) el.addEventListener('scroll',saveScroll,{passive:true});
  });
  if(!pg) return;
  var sx=0, sy=0, dx=0, dragging=false, decided=false;
  pg.addEventListener('touchstart',function(e){
    if(document.body.classList.contains('album-sorting')){ dragging=false; return; }
    if(document.body.classList.contains('selmode')) return;
    var t=e.touches[0]; if(!t) return;
    sx=t.clientX; sy=t.clientY; dx=0; dragging=true; decided=false;
  },{passive:true});
  pg.addEventListener('touchmove',function(e){
    if(document.body.classList.contains('album-sorting')){ dragging=false; return; }
    // 长按进多选后，之前按下的 dragging 仍然为 true，必须立刻收手，否则整页会被推走
    if(document.body.classList.contains('selmode')){
      if(dragging){ dragging=false; dx=0; applyPager(0,true); }
      return;
    }
    if(!dragging) return;
    var t=e.touches[0]; if(!t) return;
    var ax=t.clientX-sx, ay=t.clientY-sy;
    if(!decided){
      if(Math.abs(ax)<10 && Math.abs(ay)<10) return;
      decided=true;
      if(Math.abs(ay)>Math.abs(ax)){ dragging=false; return; }
    }
    dx=ax;
    // 边界锁死：已经在第一页就不再允许右滑，最后一页不再允许左滑（不出黑边）
    if(curTab==='timeline') dx=Math.min(dx,0);
    if(curTab==='albums')   dx=Math.max(dx,0);
    var W=window.innerWidth;
    dx=Math.max(-W,Math.min(W,dx));
    applyPager(dx, false);
  },{passive:true});
  // 双指捏合切换网格密度（张开=图更大列更少，捏合=列更多）；选模式/拖动排序时不响应
  var pinch0=0, pinchDone=false;
  function _d2(t){ var dx=t[0].clientX-t[1].clientX, dy=t[0].clientY-t[1].clientY;
    return Math.sqrt(dx*dx+dy*dy); }
  function _hap(){ if(navigator.vibrate){ try{ navigator.vibrate(10); }catch(e){} } }
  pg.addEventListener('touchstart',function(e){
    if(e.touches.length<2) return;
    if(document.body.classList.contains('selmode')||document.body.classList.contains('album-sorting')){
      pinch0=0; return;
    }
    pinch0=_d2(e.touches); pinchDone=false; dragging=false;   // 双指时取消左右滑 Tab
    if(e.cancelable) e.preventDefault();
  },{passive:false});
  pg.addEventListener('touchmove',function(e){
    if(!pinch0||e.touches.length<2||pinchDone) return;
    if(e.cancelable) e.preventDefault();
    var r=_d2(e.touches)/pinch0;
    if(r>1.25){ applyCols(Math.max(3,COLS-1)); pinchDone=true; _hap(); }
    else if(r<0.78){ applyCols(Math.min(5,COLS+1)); pinchDone=true; _hap(); }
  },{passive:false});
  pg.addEventListener('touchend',function(e){
    if(!e.touches||e.touches.length<2) pinch0=0;
  },{passive:true});

  pg.addEventListener('touchend',function(e){
    if(document.body.classList.contains('album-sorting')){ dragging=false; return; }
    if(document.body.classList.contains('selmode')){
      if(dragging){ dragging=false; dx=0; applyPager(0,true); }
      return;
    }
    if(!dragging) return;
    dragging=false;
    var th=Math.min(80, window.innerWidth*0.18);
    if(dx<=-th && curTab==='timeline') goTab('albums', true);
    else if(dx>=th && curTab==='albums') goTab('timeline', true);
    else applyPager(0, true);
  },{passive:true});
})();
/* 相册长按拖动排序：浮动副本 + 占位槽；目标卡片平滑让位（FLIP 动画），
   拖到上下边缘自动滚动；拖动期间锁住左右翻页，避免整页跟着滑。 */
/* 相册多选：长按进入 → 可勾选、可拖动排序、可批量删除 */
function __albumSelCards(){
  return Array.prototype.slice.call(document.querySelectorAll('#albums .acard.sel'));
}
function __albumBarUpdate(){
  var bar=document.getElementById('albbar'); if(!bar) return;
  var n=__albumSelCards().length;
  var del=bar.querySelector('b');
  if(del){ del.textContent='删除选中('+n+')'; del.style.opacity=n?1:.4; }
}
function __toggleAlbumCard(card){
  if(!card) return;
  card.classList.toggle('sel');
  __albumBarUpdate();
}
function __exitAlbumEdit(useHistory){
  if(useHistory && history.state && history.state.asel){ history.back(); return; }
  document.body.classList.remove('albmode');
  var box=document.getElementById('albums'); if(box) box.classList.remove('edit');
  Array.prototype.forEach.call(document.querySelectorAll('#albums .acard.sel'),function(c){c.classList.remove('sel');});
  var bar=document.getElementById('albbar'); if(bar) bar.style.display='none';
}
window.__exitAlbumEdit=__exitAlbumEdit;
// ---------------- 新建相册 ----------------
function closeNewAlbum(){ var d=document.getElementById('newalb'); if(d&&d.parentNode) d.parentNode.removeChild(d); }
function openNewAlbum(){
  if(document.getElementById('newalb')) return;
  var d=document.createElement('div'); d.id='newalb';
  d.innerHTML='<div class="msk"></div><div class="bx"><h3>新建相册</h3>'
    +'<p style="color:#7a7a80">取个名字（可以和手机里的相册同名）。空相册会一直保留。</p>'
    +'<input id="na-name" type="text" maxlength="20" placeholder="例如：家人、旅行、证件">'
    +'<div class="btns"><button class="main" id="na-ok">创建</button><button id="na-c">取消</button></div></div>';
  document.body.appendChild(d);
  d.querySelector('.msk').onclick=closeNewAlbum;
  document.getElementById('na-c').onclick=closeNewAlbum;
  document.getElementById('na-ok').onclick=function(){
    var v=(document.getElementById('na-name').value||'').trim();
    if(!v){ __toast('名字不能为空'); return; }
    var bad='\\/:*?"<>|', hasBad=false;
    for(var bi=0;bi<v.length;bi++){ if(bad.indexOf(v.charAt(bi))>=0){ hasBad=true; break; } }
    if(hasBad){ __toast('名字里不能有 \\ / : * ? " < > |'); return; }
    __createAlbum(v);
  };
  setTimeout(function(){ var i=document.getElementById('na-name'); if(i) i.focus(); }, 60);
}
// 「生成中」卡片 → 真相册（就地替换，不刷新页面）
function __albumPendingDone(name, c){
  var g=document.querySelector('#albums .albums');
  if(g){
    var el=Array.prototype.filter.call(g.children, function(x){
      return x.getAttribute('data-n')===name;
    })[0];
    if(el){
      el.classList.remove('pend');
      el.href='/相册/'+encodeURIComponent('手机图片')+'/'+encodeURIComponent(name)
        +'/index.html?v='+TVER;
      var cc=el.querySelector('.c'); if(cc) cc.textContent=(c||0)+' 项';
    }
  }
  try{   // 从待生效清单里摘掉，避免下次刷新又变成「生成中」
    var a=_pl(ADD_KEY).filter(function(x){ return x.n!==name; });
    localStorage.setItem(ADD_KEY, JSON.stringify(a));
  }catch(e){}
}
function __createAlbum(name){
  var dir='/05_收件箱/手机相册/'+name, dirEnc=encodeURI(dir);
  fetch(dirEnc+'/?json',{cache:'no-store',credentials:'same-origin'})
    .then(function(r){ return r.ok?r.json():null; })
    .catch(function(){ return null; })
    .then(function(j){ return !!(j && j.dir_exists); })
    .then(function(exists){
      if(exists){ __toast('已经有同名相册了'); return; }
      return fetch(dirEnc,{method:'MKCOL',credentials:'same-origin'})
        .then(function(r){
          if(!r.ok && r.status!==405) throw new Error('HTTP '+r.status);
          return fetch('/相册/albums.json?_='+Date.now(),{cache:'no-store',credentials:'same-origin'})
            .then(function(x){ return x.ok?x.json():{}; }).catch(function(){ return {}; })
            .then(function(reg){
              reg=reg||{}; reg[name]=Math.floor(Date.now()/1000);
              return fetch('/相册/albums.json',{method:'PUT',credentials:'same-origin',
                headers:{'Content-Type':'application/json'},body:JSON.stringify(reg)});
            });
        })
        .then(function(){
          pendAdd(name, dirEnc);
          closeNewAlbum();
          // 立刻插一张「生成中」卡片，别让用户等一分钟还看不到东西
          try{
            var g=document.querySelector('#albums .albums');
            if(g){
              var el=document.createElement('a');
              el.className='acard pend'; el.setAttribute('data-g','手机图片');
              el.setAttribute('data-n',name); el.href='javascript:void(0)';
              el.innerHTML='<i class="ckb"></i><div style="aspect-ratio:1"></div>'
                +'<span class="gtag">手机图片</span>'
                +'<div class="m"><div class="n">'+esc(name)+'</div><div class="c">生成中…</div></div>';
              g.appendChild(el);
            }
          }catch(e){}
          __toast('正在创建「'+name+'」…');
          // 生成器一分钟一轮：盯着 photos.json，一旦出现就把这张「生成中」就地换成真相册，
          // 不刷新页面（刷新会丢掉滚动位置，用户还以为没成功）。
          var t0=Date.now();
          (function wait(){
            var ms=Date.now()-t0;
            if(ms > 10*60*1000) return;                 // 最多盯 10 分钟
            fetch('/相册/photos.json?_='+Date.now(),{cache:'no-store',credentials:'same-origin'})
              .then(function(r){ return r.ok?r.json():null; })
              .then(function(d){
                var hit=((d&&d.albums)||[]).filter(function(a){
                  return a.n===name && a.g==='手机图片'; })[0];
                if(hit){
                  try{ __albumPendingDone(name, hit.c); }catch(e){}
                  __toast('「'+name+'」已生成');
                  return;
                }
                setTimeout(wait, ms<120000 ? 2500 : 10000);   // 前两分钟查得勤，之后放慢
              }).catch(function(){ setTimeout(wait, 5000); });
          })();
        });
    })
    .catch(function(e){ __toast('创建失败：'+(e&&e.message||e)); });
}
function __enterAlbumEdit(card){
  if(document.body.classList.contains('albmode')){ if(card) __toggleAlbumCard(card); return; }
  try{ history.pushState({asel:1},'','#asel'); }catch(e){}
  document.body.classList.add('albmode');
  var box=document.getElementById('albums'); if(box) box.classList.add('edit');
  var bar=document.getElementById('albbar');
  if(!bar){
    bar=document.createElement('div'); bar.id='albbar';
    bar.innerHTML='<span id="alb-all">全选</span><b id="alb-del">删除选中(0)</b><span id="alb-done">完成</span>';
    document.body.appendChild(bar);
    bar.querySelector('#alb-all').onclick=function(){
      var cards=Array.prototype.slice.call(document.querySelectorAll('#albums .acard'));
      var all=cards.length>0 && cards.every(function(c){ return c.classList.contains('sel'); });
      cards.forEach(function(c){ c.classList.toggle('sel', !all); });
      __albumBarUpdate();
    };
    bar.querySelector('#alb-done').onclick=function(){ __exitAlbumEdit(true); };
    bar.querySelector('#alb-del').onclick=__deleteSelectedAlbums;
  }
  bar.style.display='flex';
  if(card){ card.classList.add('sel'); window.__albSelAt=Date.now(); }  // 记住长按选中时间，压掉随后那次 click
  __albumBarUpdate();
}
function __deleteSelectedAlbums(){
  var cards=__albumSelCards(); if(!cards.length) return;
  var names=cards.map(function(c){ return c.getAttribute('data-n'); });
  if(!confirm('把 '+cards.length+' 个相册连同照片一起放进回收站？\n\n'+names.join('、')
    +'\n\n之后可以在回收站逐张还原，还原的张会重新组成同名相册。')) return;
  var bar=document.getElementById('albbar');
  var del=bar?bar.querySelector('#alb-del'):null;
  if(del) del.textContent='处理中…';
  var i=0, fail=0, moved=0;
  (function next(){
    if(i>=cards.length){
      __exitAlbumEdit(true);
      if(moved) __toast('已移入回收站 '+moved+' 项');
      if(fail) alert('有 '+fail+' 个相册处理失败，请重试');
      return;
    }
    var card=cards[i++];
    __albumToTrash(card, function(n, err){
      if(err) fail++; else moved+=n;
      card.remove();
      next();
    });
  })();
}
// 把整个相册（全部照片）移入回收站，然后删掉空目录并从「新建相册」登记表里移除
function __albumToTrash(card, cb){
  var p=card.getAttribute('data-p'), nm=card.getAttribute('data-n');
  if(!p){ cb(0, true); return; }
  fetch(p+'/?json',{cache:'no-store',credentials:'same-origin'})
    .then(function(r){ return r.ok?r.json():null; })
    .then(function(d){
      var files=((d&&d.paths)||[]).filter(function(x){ return x.path_type==='File'; })
        .map(function(x){ return x.name; });
      if(!files.length){
        pendDel(card.getAttribute('data-g')||'手机图片', nm);
        fetch(p,{method:'DELETE',credentials:'same-origin'})
          .then(function(){ __unregisterAlbum(nm); cb(0); }).catch(function(){ cb(0, true); });
        return;
      }
      var d0=new Date(), p2=function(x){ return x<10?'0'+x:''+x; };
      var tag=''+d0.getFullYear()+p2(d0.getMonth()+1)+p2(d0.getDate())+'-'+
              p2(d0.getHours())+p2(d0.getMinutes())+p2(d0.getSeconds())+'-'+
              Math.random().toString(36).slice(2,6);
      var dir='/06_回收站/'+tag, dirEnc=encodeURI(dir);
      var meta={items:files.map(function(f){ return {name:f, src:p+'/'+encodeURIComponent(f)}; })};
      fetch(dirEnc,{method:'MKCOL',credentials:'same-origin'}).catch(function(){})
        .then(function(){
          return fetch(dirEnc+'/_meta.json',{method:'PUT',credentials:'same-origin',
            headers:{'Content-Type':'application/json'},body:JSON.stringify(meta)}).catch(function(){});
        })
        .then(function(){
          var k=0;
          (function moveOne(){
            if(k>=files.length){
              pendDel(card.getAttribute('data-g')||'手机图片', nm);
              fetch(p,{method:'DELETE',credentials:'same-origin'})
                .then(function(){ __unregisterAlbum(nm); cb(files.length); })
                .catch(function(){ __unregisterAlbum(nm); cb(files.length); });
              return;
            }
            var f=files[k++];
            fetch(p+'/'+encodeURIComponent(f),{method:'MOVE',credentials:'same-origin',
              headers:{'Destination':location.origin+dirEnc+'/'+encodeURIComponent(f),'Overwrite':'F'}})
              .then(moveOne).catch(moveOne);
          })();
        });
    }).catch(function(){ cb(0, true); });
}
function __unregisterAlbum(name){
  fetch('/相册/albums.json?_='+Date.now(),{cache:'no-store',credentials:'same-origin'})
    .then(function(r){ return r.ok?r.json():{}; }).catch(function(){ return {}; })
    .then(function(reg){
      reg=reg||{}; if(!reg[name]) return null; delete reg[name];
      return fetch('/相册/albums.json',{method:'PUT',credentials:'same-origin',
        headers:{'Content-Type':'application/json'},body:JSON.stringify(reg)});
    }).catch(function(){});
}
function initAlbumSort(box){
  if(!box||box.__sort) return; box.__sort=1;
  var grid=box.querySelector('.albums');
  if(!grid) return;
  var drag=null, clone=null, placeholder=null, suppressClick=false;
  var HOLD=450, MOVE_CANCEL=12;
  var scrollRAF=null, lastPt={x:0,y:0};

  box.addEventListener('contextmenu',function(e){ e.preventDefault(); },{passive:false});
  box.addEventListener('dragstart',function(e){ e.preventDefault(); });
  box.addEventListener('click',function(e){
    if(!document.body.classList.contains('albmode')) return;
    var c=e.target.closest('.acard'); if(!c) return;
    e.preventDefault(); e.stopPropagation();
    if(Date.now()-(window.__albSelAt||0) < 350) return;   // 只压掉长按 touchend 之后那次合成 click
    __toggleAlbumCard(c);
  },true);
  box.addEventListener('click',function(e){
    if(!suppressClick) return;
    e.preventDefault(); e.stopPropagation(); suppressClick=false;
  },true);

  function visibleCards(){
    return Array.prototype.slice.call(box.querySelectorAll('.acard')).filter(function(c){
      return c!==drag.card;
    });
  }
  function currentSlot(){
    if(!placeholder) return -1;
    var kids=Array.prototype.slice.call(grid.children).filter(function(n){
      return n===placeholder || (n.classList&&n.classList.contains('acard')&&n!==drag.card);
    });
    return kids.indexOf(placeholder);
  }
  function slotFromPoint(x,y){
    var cards=visibleCards(); if(!cards.length) return 0;
    var cs=getComputedStyle(grid);
    var cols=(cs.gridTemplateColumns||'').split(' ').filter(function(s){return s;}).length||1;
    var gapX=parseFloat(cs.columnGap)||0, gapY=parseFloat(cs.rowGap)||0;
    var cellW=cards[0].offsetWidth||1, cellH=cards[0].offsetHeight||1;
    var gr=grid.getBoundingClientRect();
    var col=Math.round((x-gr.left-cellW/2)/(cellW+gapX));
    var row=Math.round((y-gr.top-cellH/2)/(cellH+gapY));
    col=Math.max(0,Math.min(cols-1,col));
    var total=box.querySelectorAll('.acard').length;
    var maxRow=Math.max(0,Math.ceil(total/cols)-1);
    row=Math.max(0,Math.min(maxRow,row));
    return Math.min(total-1,row*cols+col);
  }
  function animateTo(slot){
    if(!placeholder) return;
    if(currentSlot()===slot) return;
    var cards=visibleCards();
    var ref=cards[slot]||null;
    var nodes=cards.concat([placeholder]);
    var first=nodes.map(function(n){ return n.getBoundingClientRect(); });
    grid.insertBefore(placeholder,ref);
    var last=nodes.map(function(n){ return n.getBoundingClientRect(); });
    for(var i=0;i<nodes.length;i++){
      var dx=first[i].left-last[i].left, dy=first[i].top-last[i].top;
      if(!dx&&!dy) continue;
      var el=nodes[i];
      el.style.transition='none';
      el.style.transform='translate('+dx+'px,'+dy+'px)';
      void el.offsetWidth;
      el.style.transition='transform .18s cubic-bezier(.2,.8,.2,1)';
      el.style.transform='';
    }
  }
  function updateTarget(){
    if(!drag||!drag.on) return;
    animateTo(slotFromPoint(lastPt.x,lastPt.y));
  }
  function tickScroll(){
    scrollRAF=null;
    if(!drag||!drag.on) return;
    var pane=document.getElementById('pg-albums');
    if(!pane) return;
    var y=lastPt.y, h=window.innerHeight, v=0;
    if(y<120) v=-Math.max(6,Math.min(16,(120-y)/3));
    else if(y>h-120) v=Math.max(6,Math.min(16,(y-(h-120))/3));
    if(v){ pane.scrollTop+=v; updateTarget(); }
    scrollRAF=requestAnimationFrame(tickScroll);
  }
  function startAutoScroll(){ if(!scrollRAF) scrollRAF=requestAnimationFrame(tickScroll); }
  function stopAutoScroll(){ if(scrollRAF){ cancelAnimationFrame(scrollRAF); scrollRAF=null; } }

  function saveOrder(){
    var order=Array.prototype.slice.call(box.querySelectorAll('.acard')).map(function(c){
      return {g:c.getAttribute('data-g'),n:c.getAttribute('data-n')};
    });
    fetch('/相册/album_order.json',{method:'PUT',credentials:'same-origin',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(order,null,1)}).then(function(r){
        if(!r.ok) alert('保存相册顺序失败：HTTP '+r.status);
      }).catch(function(e){
        alert('保存相册顺序失败：'+e);
      });
    if(navigator.vibrate){try{navigator.vibrate(10)}catch(e){}}
  }

  function startDrag(){
    if(!drag) return;
    var card=drag.card, r=card.getBoundingClientRect();
    drag.on=true; suppressClick=true;
    document.body.classList.add('album-sorting');
    if(window.applyPager) applyPager(0,false);
    placeholder=document.createElement('div');
    placeholder.className='sort-placeholder';
    placeholder.style.height=r.height+'px';
    card.parentNode.insertBefore(placeholder,card);
    card.classList.add('drag-origin');
    clone=card.cloneNode(true);
    clone.classList.remove('drag-origin');
    clone.classList.add('drag-clone');
    clone.style.left=r.left+'px'; clone.style.top=r.top+'px';
    clone.style.width=r.width+'px'; clone.style.height=r.height+'px';
    document.body.appendChild(clone);
    lastPt={x:drag.x0,y:drag.y0};
    startAutoScroll();
    if(navigator.vibrate){try{navigator.vibrate(18)}catch(e){}}
  }
  function finish(save){
    if(!drag) return;
    clearTimeout(drag.timer);
    if(drag.on){
      stopAutoScroll();
      if(placeholder){
        placeholder.parentNode.insertBefore(drag.card,placeholder);
        placeholder.parentNode.removeChild(placeholder);
        placeholder=null;
      }
      drag.card.classList.remove('drag-origin');
      if(clone&&clone.parentNode) clone.parentNode.removeChild(clone);
      clone=null;
      // 让 pager/document 的 touchend 先看到 album-sorting，避免松手瞬间触发翻页
      setTimeout(function(){ document.body.classList.remove('album-sorting'); },0);
      if(window.applyPager) applyPager(0,false);
      if(save) saveOrder();
      suppressClick=true;
      setTimeout(function(){ suppressClick=false; },450);
    }
    drag=null;
  }

  box.addEventListener('touchstart',function(e){
    suppressClick=false;
    if(document.body.classList.contains('selmode')) return;
    if(document.body.classList.contains('albmode')) return;   // 多选管理时：点按=勾选，不拖动
    if(e.touches.length>1){ if(drag) finish(false); return; }
    var card=e.target.closest('.acard'); if(!card) return;
    var t=e.touches[0]; if(!t) return;
    drag={card:card,x0:t.clientX,y0:t.clientY,lastX:t.clientX,lastY:t.clientY,on:false,held:false,
          timer:setTimeout(startDrag,HOLD)};
  },{passive:true});

  box.addEventListener('touchmove',function(e){
    if(!drag) return;
    var t=e.touches[0]; if(!t) return;
    drag.lastX=t.clientX; drag.lastY=t.clientY;
    lastPt={x:t.clientX,y:t.clientY};
    if(!drag.on){
      if(Math.abs(t.clientX-drag.x0)>MOVE_CANCEL||Math.abs(t.clientY-drag.y0)>MOVE_CANCEL){
        clearTimeout(drag.timer); drag=null;
      }
      return;
    }
    if(e.cancelable) e.preventDefault();
    if(clone){
      clone.style.transform='translate('+(t.clientX-drag.x0)+'px,'+(t.clientY-drag.y0)+'px) scale(1.03)';
    }
    updateTarget();
  },{passive:false});

  box.addEventListener('touchend',function(){ finish(true); },{passive:true});
  box.addEventListener('touchcancel',function(){ finish(false); },{passive:true});
}

(function(){
  var sx=0, sy=0, st=0, active=false;
  document.addEventListener('touchstart',function(e){
    if(document.body.classList.contains('album-sorting')) { active=false; return; }
    if(document.body.classList.contains('selmode')) { active=false; return; }
    var v=document.getElementById('viewer');
    if(v&&v.classList.contains('on')) { active=false; return; }
    var t=e.touches[0]; if(!t) return;
    sx=t.clientX; sy=t.clientY; st=Date.now(); active=true;
  },{passive:true});
  document.addEventListener('touchend',function(e){
    if(document.body.classList.contains('album-sorting')) { active=false; return; }
    if(!active) return; active=false;
    var t=e.changedTouches[0]; if(!t) return;
    var dx=t.clientX-sx, dy=t.clientY-sy, dt=Date.now()-st;
    if(dt>700) return;
    if(Math.abs(dx)<70 || Math.abs(dx) < Math.abs(dy)*1.6) return;
    var cur=curTab;
    if(dx<0 && cur==='timeline') switchTab('albums');
    else if(dx>0 && cur==='albums') switchTab('timeline');
  },{passive:true});
})();

var ALL_PHOTOS=null, ALL_ALBUMS=null;

function rebuildAlbums(albums, photos){
  var groups=[], out=[];
  for(var i=0;i<albums.length;i++) groups.push([]);
  for(var j=0;j<photos.length;j++){
    var p=photos[j], best=-1, bl=-1;
    for(var k=0;k<albums.length;k++){
      var a=albums[k];
      if(a.p && p[1].indexOf(a.p+'/')===0 && a.p.length>bl){ best=k; bl=a.p.length; }
    }
    if(best>=0) groups[best].push(p);
  }
  for(var m=0;m<albums.length;m++){
    var g=groups[m];
    if(!g.length){
      // 空相册（用户新建的）要保留：服务端明确给了 0 项，就不要在这里丢掉
      var ea=albums[m];
      if(ea && (ea.c===0 || ea.empty)){
        out.push({g:ea.g, n:ea.n, c:0, cv:ea.cv||'', p:ea.p||'', key:ea.key||''});
      }
      continue;
    }
    var newest=null;
    for(var n=0;n<g.length;n++){
      var pp=g[n];
      if(pp[0] && (!newest || pp[2]>newest[2])) newest=pp;
    }
    if(!newest) newest=g[0];
    var alb=albums[m];
    alb.c=g.length;
    alb.cv=newest[0]||'';
    out.push(alb);
  }
  return out;
}
function paintIndexHidden(hid){
  // 时间轴：移除已删格子、同步 data-list/data-i、更新月份计数
  document.querySelectorAll('#timeline .grid').forEach(function(g){
    var list=[]; try{ list=JSON.parse(g.getAttribute('data-list')||'[]'); }catch(e){}
    var filtered=list.filter(function(it){ return !hid[it[0]]; });
    if(filtered.length!==list.length) g.setAttribute('data-list',JSON.stringify(filtered));
    var cells=g.querySelectorAll('a[data-full]');
    for(var i=0;i<cells.length;i++){
      var a=cells[i], full=a.getAttribute('data-full');
      if(hid[full]){ if(a.parentNode) a.parentNode.removeChild(a); continue; }
      for(var k=0;k<filtered.length;k++){ if(filtered[k][0]===full){ a.setAttribute('data-i',k); break; } }
    }
  });
  document.querySelectorAll('#timeline section').forEach(function(sec){
    var cnt=sec.querySelectorAll('.grid a[data-full]').length;
    var sp=sec.querySelector('.mhead span'); if(sp) sp.textContent=cnt+' 项';
    if(!cnt && sec.parentNode) sec.parentNode.removeChild(sec);
  });
  // 相册卡片：空相册移除、数量更新、封面换成剩余最新一张
  document.querySelectorAll('#albums .acard').forEach(function(card){
    var g=card.getAttribute('data-g'), n=card.getAttribute('data-n'), found=null;
    for(var i=0;i<DATA.albums.length;i++){
      if(DATA.albums[i].g===g && DATA.albums[i].n===n){ found=DATA.albums[i]; break; }
    }
    if(!found){ if(card.parentNode) card.parentNode.removeChild(card); return; }
    var cc=card.querySelector('.c'); if(cc) cc.textContent=found.c+' 项';
    var im=card.querySelector('img');
    if(im && found.cv && im.getAttribute('src')!==found.cv) im.src=found.cv;
  });
}
function applyMovesToAll(){
  if(!ALL_PHOTOS||!ALL_ALBUMS) return;
  var moves=window.__movesGet?window.__movesGet():[];
  if(!moves.length) return;
  for(var mi=0;mi<moves.length;mi++){
    var m=moves[mi], srcP=null, hasDest=false;
    if(!m.src||!m.dest) continue;
    for(var i=0;i<ALL_PHOTOS.length;i++){
      var p=ALL_PHOTOS[i];
      if(p[1]===m.dest) hasDest=true;
      if(p[1]===m.src) srcP=p;
    }
    // 生成器已经重建出目标路径时，以服务器数据为准，不重复套用
    if(hasDest||!srcP) continue;
    srcP[1]=m.dest;
    srcP[4]=m.name||srcP[4];
    if(m.thumb) srcP[0]=m.thumb;
    if(m.ts) srcP[2]=m.ts;
    if(m.isVid!==undefined) srcP[3]=m.isVid?1:0;
    if(m.fsize) srcP[5]=m.fsize;
  }
}
window.__applyHiddenIndex=function(){
  if(!ALL_PHOTOS||!ALL_ALBUMS) return;
  applyMovesToAll();
  var hid=window.__hiddenSet?window.__hiddenSet():{};
  var photos=ALL_PHOTOS.filter(function(p){ return !hid[p[1]]; });
  var albums=rebuildAlbums(ALL_ALBUMS,photos);
  DATA={albums:applyAlbumPending(albums),photos:photos,updated:(DATA&&DATA.updated)||0};
  window.__DATA=DATA;
  var by={}; for(var bi=0;bi<photos.length;bi++) by[photos[bi][1]]=photos[bi];
  window.__photoByFull=by;
  paintIndexHidden(hid);
};
window.__refreshIndex=function(){
  fetch('photos.json?_='+Date.now()).then(function(r){return r.json();}).then(function(d){
    ALL_PHOTOS=d.photos.slice(); ALL_ALBUMS=d.albums.slice();
    window.__applyHiddenIndex();
  }).catch(function(){});
};
window.addEventListener('pageshow',function(e){
  if(!e.persisted) return;
  window.__applyHiddenIndex();
  window.__refreshIndex();
});

// ===== 网络：断网/弱网要给明确提示，不能白屏干等 =====
function netFetch(url, opts, ms){
  opts = opts || {};
  var ctl = null;
  try{ ctl = new AbortController(); }catch(e){}
  if(ctl) opts.signal = ctl.signal;
  var to = setTimeout(function(){ try{ if(ctl) ctl.abort(); }catch(e){} }, ms || 12000);
  return fetch(url, opts).then(function(r){ clearTimeout(to); return r; },
                               function(e){ clearTimeout(to); throw e; });
}
var __netTimer=null;
function hideNetError(){
  var el=document.getElementById('netov'); if(el) el.remove();
  if(__netTimer){ clearTimeout(__netTimer); __netTimer=null; }
}
function tickNetCd(n){
  var cd=document.getElementById('netcd'); if(!cd) return;
  if(n<=0){ bootData(true); return; }
  cd.textContent=n+' 秒后自动重试';
  __netTimer=setTimeout(function(){ tickNetCd(n-1); },1000);
}
function showNetError(){
  if(document.getElementById('netov')) return;
  var off=(navigator.onLine===false);
  var el=document.createElement('div'); el.id='netov';
  el.innerHTML='<div class="bx"><div class="ic">'+(off?'📴':'📡')+'</div>'
    +'<h3>'+(off?'手机没有联网':'连不上 NAS')+'</h3>'
    +'<p>'+(off?'请检查 Wi-Fi 或移动数据，恢复后会自动重试。'
               :'可能是 NAS 没开机、相册服务没起来，或当前网络到 NAS 不通。')+'</p>'
    +'<p class="cd" id="netcd"></p>'
    +'<div class="btns"><button id="netretry">立即重试</button></div></div>';
  document.body.appendChild(el);
  document.getElementById('netretry').onclick=function(){ bootData(true); };
  tickNetCd(6);
}
function showOffBar(){
  if(document.getElementById('offbar')) return;
  var d=document.createElement('div'); d.id='offbar';
  d.innerHTML='<span>连不上 NAS</span><b>点击重试</b>';
  d.onclick=function(){ d.remove(); bootData(true); };
  document.body.appendChild(d);
}
function clearOffBar(){ var d=document.getElementById('offbar'); if(d) d.remove(); }
function bootData(manual){
  if(manual) hideNetError();
  var q='?_='+Date.now();
  return Promise.all([
    netFetch('photos.json'+q,{cache:'no-store'},12000).then(function(r){
      if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); }),
    netFetch('durations.json'+q,{cache:'no-store'},12000).then(function(r){return r.json();}).catch(function(){return {};}),
    netFetch('status.json'+q,{cache:'no-store'},12000).then(function(r){return r.json();}).catch(function(){return null;}),
    netFetch('onthisday.json'+q,{cache:'no-store'},12000).then(function(r){return r.json();}).catch(function(){return [];}),
    netFetch('trash.json'+q,{cache:'no-store'},12000).then(function(r){return r.json();}).catch(function(){return null;}),
    netFetch('similar.json'+q,{cache:'no-store'},12000).then(function(r){return r.json();}).catch(function(){return [];})
  ]).then(function(res){
    hideNetError(); clearOffBar();
    applyData(res);
  }).catch(function(e){
    if(DATA){ showOffBar(); } else { showNetError(); }
  });
}
window.addEventListener('online',function(){ __toast('网络已恢复'); clearOffBar(); if(document.getElementById('netov')) bootData(true); });
window.addEventListener('offline',function(){ __toast('网络已断开，恢复后会自动重试'); });
// ---------------- 新建/删除相册的「待生效」状态 ----------------
// 生成器一分钟才重建一次：删掉/新建之后到重建之间，photos.json 还是旧的。
// 用两个独立列表记住这两类操作，**只读不写**（渲染时不修改存储，避免自己把自己删掉）。
var ADD_KEY='nas_alb_add', DEL_KEY='nas_alb_del', PEND_TTL=10*60*1000;
function _pl(k){
  try{ var a=JSON.parse(localStorage.getItem(k)||'[]'); return Array.isArray(a)?a:[]; }catch(e){ return []; }
}
function pendAdd(name, path){
  try{
    var a=_pl(ADD_KEY).filter(function(x){ return x.n!==name; });
    a.push({n:name, p:path||'', ts:Date.now()});
    localStorage.setItem(ADD_KEY, JSON.stringify(a));
  }catch(e){}
}
function pendDel(g, n){
  try{
    var a=_pl(DEL_KEY).filter(function(x){ return !(x.g===g&&x.n===n); });
    a.push({g:g, n:n, ts:Date.now()});
    localStorage.setItem(DEL_KEY, JSON.stringify(a));
  }catch(e){}
}
function applyAlbumPending(list){
  var now=Date.now();
  var dels=_pl(DEL_KEY).filter(function(x){ return x&&(now-x.ts)<PEND_TTL; });
  var adds=_pl(ADD_KEY).filter(function(x){ return x&&x.n&&(now-x.ts)<PEND_TTL; });
  var src=list||[];
  var out=src.filter(function(a){
    if(a.pending) return true;
    return !dels.some(function(d){ return d.g===a.g&&d.n===a.n; });
  });
  adds.forEach(function(x){
    if(src.some(function(a){ return a.n===x.n; })) return;   // 服务端已经有了
    if(out.some(function(a){ return a.n===x.n&&a.pending; })) return;
    out.push({g:'手机图片', n:x.n, c:0, cv:'', p:x.p||'', pending:true});
  });
  return out;
}
function applyData(res){
  var d=res[0]; DUR=res[1]||{}; STATUS=res[2]||null; OTD=res[3]||[];
  // 先把「刚新建、还没被生成器写进 photos.json」的相册补进来（就地 push，最简单直接）
  try{
    if(d&&d.albums){
      var _now=Date.now(), _adds=_pl(ADD_KEY);
      for(var _i=0;_i<_adds.length;_i++){
        var _x=_adds[_i];
        if(!_x||!_x.n) continue;
        if(_now-_x.ts >= PEND_TTL) continue;
        var _has=false;
        for(var _j=0;_j<d.albums.length;_j++){ if(d.albums[_j].n===_x.n){ _has=true; break; } }
        if(!_has) d.albums.push({g:'手机图片', n:_x.n, c:0, cv:'', p:_x.p||'', pending:true});
      }
      d.albums=applyAlbumPending(d.albums);
    }
  }catch(e){}
  window.__TRASH_N=(res[4]&&res[4].trash)||0;
  SIM=res[5]||[];
  favLoad();
  try{ COLS=parseInt(localStorage.getItem('nas_cols'),10)||3; }catch(e){ COLS=3; }
  applyCols(COLS); renderStat();
  var stEl=document.getElementById('stat');
  if(stEl) stEl.onclick=openSyncSheet;
  startIdlePoll();
  startAutoUpload();
  var sbtn=document.getElementById('sbtn'), sbar=document.getElementById('sbar'),
      sinput=document.getElementById('sinput'), sclose=document.getElementById('sclose');
  function openSearch(){
    if(sbar.classList.contains('on')) return;
    try{ history.pushState({s:1},'','#s'); }catch(e){}
    sbar.classList.add('on'); sinput.value=Q;
    setTimeout(function(){ try{ sinput.focus(); }catch(e){} }, 30);
  }
  function closeSearch(){
    if(!sbar.classList.contains('on')) return false;
    sbar.classList.remove('on');
    try{ sinput.blur(); }catch(e){}
    if(Q){ Q=''; sinput.value=''; renderTimeline(true); }
    return true;
  }
  window.__closeSearch=closeSearch;
  if(sbtn) sbtn.onclick=openSearch;
  if(sclose) sclose.onclick=function(){
    var hadState=(history.state&&history.state.s);
    closeSearch();                         // 先同步关掉，避免等 popstate 才生效
    if(hadState){ try{ history.back(); }catch(e){} }   // 再把那条历史退掉
  };
  if(sinput) sinput.oninput=function(){ Q=this.value.trim().toLowerCase(); renderTimeline(true); };
  ALL_PHOTOS=d.photos.slice(); ALL_ALBUMS=d.albums.slice();
  window.__applyHiddenIndex();
  var tab0='timeline';
  try{ tab0=sessionStorage.getItem('nas_tab')||'timeline'; }catch(e){}
  if(location.hash==='#albums') tab0='albums';
  else if(location.hash==='#timeline') tab0='timeline';
  switchTab(tab0);
  applyPager(0,false);
}
bootData(false);
"""

ALBUM_JS = r"""
(function(){
  var items=window.__LIST||[];
  var hid=window.__hiddenSet?window.__hiddenSet():{};
  if(hid) items=items.filter(function(it){ return !hid[it[0]]; });
  // 移动的乐观状态：源相册先移除，目标相册先补进来（缩略图暂用源相册那张）
  var moves=window.__movesGet?window.__movesGet():[];
  var movedOut={}, movedAgain={}, movedIn=[];
  moves.forEach(function(m){
    if(!m||!m.src||!m.dest) return;
    movedAgain[m.src]=1;
    if(window.__CURP && m.src.indexOf(window.__CURP+'/')===0) movedOut[m.src]=1;
    if(window.__CURP && m.dest.indexOf(window.__CURP+'/')===0) movedIn.push(m);
  });
  if(Object.keys(movedOut).length){
    items=items.filter(function(it){ return !movedOut[it[0]]; });
  }
  movedIn.forEach(function(m){
    if(hid[m.dest] || movedAgain[m.dest]) return;   // 已删除，或又被移到下一个相册了
    var exists=false;
    for(var i=0;i<items.length;i++){ if(items[i][0]===m.dest){ exists=true; break; } }
    if(!exists) items.push([m.dest, m.isVid?1:0, m.ts||0, m.thumb||'', m.fsize||0]);
  });
  // 与网格显示顺序一致：按时间倒序；这样大图左/右就是网格左/右。
  items.sort(function(a,b){ return b[2]-a[2]; });
  window.__albumItems=items;
  var acnt=document.getElementById('acnt'); if(acnt) acnt.textContent=items.length+' 项';
  if(!items.length){
    // 用户新建的空相册：不跳走，显示空状态（照片被删空时也这样，返回还能回上一级）
    var g0=document.getElementById('g');
    if(g0) g0.innerHTML='<div class="emptyalb">这个相册还没有照片<br><span>用「移动」把照片放进来，或直接在手机里传</span></div>';
    return;
  }
  var box=document.getElementById("g");
  var pairs=items.map(function(it,i){return [it,i];});
  pairs.sort(function(a,b){return b[0][2]-a[0][2];});
  var cur="",grid=null;
  pairs.forEach(function(p){
    var it=p[0],oi=p[1];
    var d=new Date(it[2]*1000);
    var k=d.getFullYear()+"年"+(d.getMonth()+1)+"月";
    if(k!==cur){
      cur=k;
      var s=document.createElement("section");
      s.innerHTML='<div class="mhead"><b>'+k+'</b></div><div class="grid"></div>';
      box.appendChild(s);
      grid=s.querySelector(".grid");
    }
    var a=document.createElement("a");
    a.href="#"; a.setAttribute("data-i",oi); a.setAttribute("data-full",it[0]);
    a.innerHTML='<img loading="lazy" src="'+it[3]+'">'+(it[1]===1?'<span class="play">▶</span>':'');
    grid.appendChild(a);
    var im=a.querySelector("img");
    if(im.complete){im.classList.add("ld");}else{im.onload=function(){this.classList.add("ld");};}
  });
  box.addEventListener("click",function(e){
    if(document.body.classList.contains("selmode")) return;
    var a=e.target.closest("a"); if(!a) return;
    e.preventDefault();
    var list=window.__albumItems||items;
    var full=a.getAttribute("data-full"), idx=-1;
    for(var k=0;k<list.length;k++){ if(list[k][0]===full){ idx=k; break; } }
    if(idx<0){
      alert('这张照片已不在当前列表（可能刚被移走），刷新后会消失。为避免误操作，已取消打开。');
      return;
    }
    __openViewer(list.map(function(x){return [x[0],x[1],x[4],window.__ALBUM,x[2]];}), idx, a);
  });
  if(window.__bindScrub) window.__bindScrub(null);
})();

"""


DUR_FILE = os.path.join(OUT, 'durations.json')
DUR_CACHE = {}
FFPROBE = os.path.join(os.path.dirname(FF), 'ffprobe.exe')


def probe_duration(path):
    """返回 "m:ss"；失败返回空串。"""
    try:
        r = subprocess.run([FFPROBE, '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'csv=p=0', path],
                           capture_output=True, text=True, errors='replace',
                           timeout=25, creationflags=0x08000000)
        v = float((r.stdout or '').strip().split(',')[0])
        if v <= 0:
            return ''
        s_ = int(round(v))
        return '%d:%02d' % (s_ // 60, s_ % 60)
    except Exception:
        return ''


def load_durations():
    try:
        return json.load(io.open(DUR_FILE, encoding='utf-8'))
    except Exception:
        return {}


def thumb_key(p):
    """缩略图文件名用源文件相对路径哈希：移动后不会复用成另一张照片的缩略图。"""
    rel = rel_to_root(p)
    return hashlib.md5(rel.encode('utf-8')).hexdigest()[:16]


HEIC_EXT = {'.heic', '.heif'}
HEIC_DIR = os.path.join(OUT, 'heic')
_HEIF_OK = None


def heic_to_jpeg(src, key):
    """把 HEIC/HEIF 转成 JPEG（长边 2048）：浏览器不认 HEIC，转完才能看。
    按源文件 mtime 缓存；失败返回 None（原样保留，至少不崩）。"""
    global _HEIF_OK
    dst = os.path.join(HEIC_DIR, key + '.jpg')
    try:
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
            return dst
    except OSError:
        return None
    if _HEIF_OK is False:
        return None
    try:
        import pillow_heif
        from PIL import Image, ImageOps
        if _HEIF_OK is None:
            pillow_heif.register_heif_opener()
            _HEIF_OK = True
        im = Image.open(src)
        im = ImageOps.exif_transpose(im)
        im = im.convert('RGB')
        w, h = im.size
        m = max(w, h)
        if m > 2048:
            r = 2048.0 / m
            im = im.resize((max(1, int(w * r)), max(1, int(h * r))), Image.LANCZOS)
        os.makedirs(HEIC_DIR, exist_ok=True)
        im.save(dst, 'JPEG', quality=88, optimize=True)
        return dst
    except Exception as e:
        _HEIF_OK = False
        print('[HEIC] convert failed', os.path.basename(src), repr(e)[:60])
        return None


def resolve_media(p):
    """返回 (给浏览器看的文件, 是否转换过)：HEIC 转 JPEG，其它原样。"""
    if os.path.splitext(p)[1].lower() not in HEIC_EXT:
        return p, False
    conv = heic_to_jpeg(p, thumb_key(p))
    return (conv, True) if conv else (p, False)


def media_in(path):
    out = []
    for dp, dn, fn in os.walk(path):
        for f in fn:
            if os.path.splitext(f)[1].lower() in (IMG | VID):
                out.append(os.path.join(dp, f))
    return sorted(out)



# ---------------- 拍摄时间：EXIF > 文件名里的时间 > 文件修改时间 ----------------
# 为什么需要它：上传到 NAS 后文件修改时间会变成「上传时间」，
# 老照片就会被排到今天（2026-10）。这里优先用 EXIF/文件名里的真实拍摄时间。
TS_CACHE_PATH = os.path.join(OUT, '.ts_cache.json')
_TS_CACHE = None


def _ts_cache():
    global _TS_CACHE
    if _TS_CACHE is None:
        try:
            _TS_CACHE = json.load(io.open(TS_CACHE_PATH, encoding='utf-8'))
        except Exception:
            _TS_CACHE = {}
    return _TS_CACHE


def _save_ts_cache():
    try:
        json.dump(_TS_CACHE or {}, io.open(TS_CACHE_PATH, 'w', encoding='utf-8'))
    except Exception:
        pass


def _ts_from_name(name):
    """从文件名里猜时间；猜不出返回 None。只接受合理范围（2000–2035），
    并且要求数字边界，否则像 Image_23717209905327.jpg 这种长数字会被当成"2099-05-32"。"""
    def mk(y, mo, d, h=0, mi=0, sec=0):
        if not (2000 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31
                and 0 <= h <= 23 and 0 <= mi <= 59 and 0 <= sec <= 59):
            return None
        try:
            return int(time.mktime((y, mo, d, h, mi, sec, 0, 0, -1)))
        except Exception:
            return None

    # 13 位毫秒时间戳（Image_1763028944362 / mmexport1506743360391），前后不能再接数字
    m = re.search(r'(?<!\d)(1[0-9]{12})(?!\d)', name)
    if m:
        v = int(m.group(1)) / 1000.0
        if 946684800 < v < 2051222400:          # 2000-01-01 ~ 2035-01-01
            return int(v)

    # IMG_20230812_185330 / VID_20230812_185330 / Screenshot_20230812_185330
    m = re.search(r'(?<!\d)(20\d{2})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})(?!\d)', name)
    if m:
        r = mk(*[int(x) for x in m.groups()])
        if r:
            return r

    # 只有日期：20230812（必须独立成段，防止从长数字里截）
    m = re.search(r'(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)', name)
    if m:
        r = mk(int(m.group(1)), int(m.group(2)), int(m.group(3)), 12, 0, 0)
        if r:
            return r
    return None


def media_ts(p):
    """真实拍摄时间（秒），失败退回文件修改时间。"""
    try:
        st = os.stat(p)
    except OSError:
        return 0
    key = p + '|' + str(st.st_size)
    cache = _ts_cache()
    hit = cache.get(key)
    if isinstance(hit, int) and hit > 0:
        return hit

    ts = None
    ext = os.path.splitext(p)[1].lower()
    if ext not in VID:
        try:
            from PIL import Image
            if ext in HEIC_EXT:
                try:
                    import pillow_heif
                    pillow_heif.register_heif_opener()
                except Exception:
                    pass
            with Image.open(p) as im:
                ex = im.getexif()
                raw = ex.get(36867) or ex.get(306)      # DateTimeOriginal / DateTime
            if raw:
                ts = int(time.mktime(time.strptime(str(raw)[:19], '%Y:%m:%d %H:%M:%S')))
        except Exception:
            ts = None
    if not ts:
        ts = _ts_from_name(os.path.basename(p))
    now = time.time()
    if not ts or ts < 946684800 or ts > now + 86400:   # 2000 之前 / 未来：不信，用修改时间
        ts = int(st.st_mtime)
    cache[key] = int(ts)
    return int(ts)


def save_ts_cache():
    _save_ts_cache()


THUMB_WARNED = []


def _thumb_by_pil(src, dst):
    """优先用 Pillow 缩图：不依赖 ffmpeg，装了 pillow 就能用。"""
    try:
        from PIL import Image, ImageOps
    except Exception:
        return False
    try:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except Exception:
            pass
        im = Image.open(src)
        im = ImageOps.exif_transpose(im)
        im.thumbnail((THUMB_W, THUMB_W * 3), Image.LANCZOS)
        if im.mode not in ('RGB', 'L'):
            im = im.convert('RGB')
        im.save(dst, 'JPEG', quality=82, optimize=True)
        return os.path.exists(dst) and os.path.getsize(dst) > 0
    except Exception:
        return False


def make_thumb(src, dst):
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return True
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
    except Exception as e:
        if 'mk' not in THUMB_WARNED:
            THUMB_WARNED.append('mk')
            print('[缩略图] 建目录失败：%s' % e, flush=True)
        return False

    is_vid = os.path.splitext(src)[1].lower() in VID
    # 图片先试 Pillow（快、不需要 ffmpeg）；失败再交给 ffmpeg
    if not is_vid and _thumb_by_pil(src, dst):
        return True

    cmd = [FF, '-hide_banner', '-loglevel', 'error', '-y']
    if is_vid:
        cmd += ['-ss', '1']
    cmd += ['-i', src, '-frames:v', '1', '-vf', 'scale=%d:-2' % THUMB_W, '-q:v', '4', dst]
    try:
        r = subprocess.run(cmd, capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=120)
        if r.returncode == 0 and os.path.exists(dst):
            return True
        if 'ff' not in THUMB_WARNED:
            THUMB_WARNED.append('ff')
            tip = (r.stderr or b'').decode('utf-8', 'replace')[:120]
            print('[缩略图] 生成失败（多半是没装 ffmpeg/pillow）：%s' % tip, flush=True)
        return False
    except Exception as e:
        if 'ff' not in THUMB_WARNED:
            THUMB_WARNED.append('ff')
            print('[缩略图] 调不动 ffmpeg（没装或路径不对）：%s' % e, flush=True)
        return False


def rel_to_root(p):
    """相对根目录的路径（给 URL 用）。不在根目录下就退回文件名，绝不抛异常。"""
    try:
        return os.path.relpath(p, ROOT).replace('\\', '/')
    except Exception:
        return os.path.basename(p).replace('\\', '/')


def build_albums():
    albums = []
    for group, root, skip in SOURCES:
        if not os.path.isdir(root):
            continue
        if group in FLAT_GROUPS:
            items = media_in(root)
            if items:
                albums.append({'g': group, 'n': group, 'items': items, 'dir': root})
            continue
        for d in sorted(os.listdir(root)):
            p = os.path.join(root, d)
            if not os.path.isdir(p) or d.startswith('.') or d in skip:
                continue
            items = media_in(p)
            if items:
                albums.append({'g': group, 'n': d, 'items': items, 'dir': p})
        direct = [os.path.join(root, f) for f in os.listdir(root)
                  if os.path.isfile(os.path.join(root, f))
                  and os.path.splitext(f)[1].lower() in (IMG | VID)]
        if direct:
            albums.append({'g': group, 'n': '未分类', 'items': direct, 'dir': root})
    # 用户新建的空相册（哪怕 0 项也保留）：以 albums.json 为准，目录还在就产出空相册
    try:
        reg = load_user_albums()
    except Exception:
        reg = {}
    if reg:
        have = set((a['g'], a['n']) for a in albums)
        for name in reg:
            d = os.path.join(PHOTO_ROOT, name)
            if not os.path.isdir(d):
                continue
            if ('手机图片', name) in have:
                continue
            albums.append({'g': '手机图片', 'n': name, 'items': [], 'dir': d})
    return albums


ALBUMS_PATH = os.path.join(OUT, 'albums.json')    # 用户新建的相册登记表：{名字: 时间戳}


def load_user_albums():
    try:
        d = json.load(io.open(ALBUMS_PATH, encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

# ---------------- 已删除名单（防止手机把删掉的照片又传回来） ----------------
# 照片在相册里被删 → 进 06_回收站；这里把文件名并入 tombstones.json，**只增不减**。
# 手机上传时先读这份名单，命中就跳过，即使回收站已经清空也不会重传。
TOMB_PATH = os.path.join(OUT, 'tombstones.json')


def update_tombstones():
    try:
        cur = json.load(io.open(TOMB_PATH, encoding='utf-8'))
        if not isinstance(cur, dict):
            cur = {}
    except Exception:
        cur = {}
    added = 0
    try:
        if os.path.isdir(RECYCLE):
            for d in os.listdir(RECYCLE):
                dp = os.path.join(RECYCLE, d)
                if not os.path.isdir(dp):
                    continue
                for f in os.listdir(dp):
                    if f in ('_meta.json', '_manifest.json'):
                        continue
                    if f not in cur:
                        cur[f] = int(time.time())
                        added += 1
    except Exception as e:
        print('[已删除名单] 扫描失败:', repr(e)[:60])
    try:
        json.dump(cur, io.open(TOMB_PATH, 'w', encoding='utf-8'), ensure_ascii=False)
    except Exception as e:
        print('[已删除名单] 写入失败:', repr(e)[:60])
    if added:
        print('[已删除名单] 新增 %d，累计 %d' % (added, len(cur)))
    return len(cur)

RECYCLE_KEEP_DAYS = 30


def clean_empty_batches():
    """永久删除后留下的空批次目录直接删掉，别在回收站里留一行「时间 · 0 项」。"""
    n = 0
    try:
        if not os.path.isdir(RECYCLE):
            return 0
        for d in os.listdir(RECYCLE):
            dp = os.path.join(RECYCLE, d)
            if not os.path.isdir(dp) or not re.match(r'^\d{8}-\d{6}-[a-z0-9]{4}$', d):
                continue
            left = [f for f in os.listdir(dp)
                    if f != '_meta.json' and os.path.isfile(os.path.join(dp, f))]
            if not left:
                shutil.rmtree(dp, ignore_errors=True)
                n += 1
    except Exception as e:
        print('[回收站] 清理空批次失败:', repr(e)[:60])
    if n:
        print('[回收站] 删除空批次 %d 个' % n)
    return n




def clean_recycle():
    """只清理本程序创建的回收站批次目录（YYYYMMDD-HHMMSS-xxxx），避免误删用户自己放的东西。"""
    if not os.path.isdir(RECYCLE):
        return 0
    cutoff = time.time() - RECYCLE_KEEP_DAYS * 86400
    n = 0
    for name in os.listdir(RECYCLE):
        p = os.path.join(RECYCLE, name)
        if not os.path.isdir(p):
            continue
        if not re.match(r'^\d{8}-\d{6}-[a-z0-9]{4}$', name):
            continue
        try:
            if os.path.getmtime(p) < cutoff:
                shutil.rmtree(p, ignore_errors=True)
                n += 1
        except OSError:
            pass
    return n


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        n = clean_recycle()
        if n:
            print('回收站清理: %d 个过期批次' % n)
    except Exception as e:
        print('回收站清理失败:', repr(e)[:60])
    albums = build_albums()

    # 用户在 App 里拖动排序过的顺序（album_order.json），未列出的排后面。
    # 注意：排序文件的内容必须进入 .sig，否则拖动后没有新照片时签名不变，
    # 生成器会跳过重建，页面刷新又回到旧顺序（表现为“拖动保存了但没用”）。
    order_sig = ''
    try:
        order_file = os.path.join(OUT, 'album_order.json')
        if os.path.exists(order_file):
            raw = open(order_file, 'rb').read()
            olist = json.loads(raw.decode('utf-8-sig'))
            rank = {}
            for i, o in enumerate(olist):
                k = (o.get('g', '') + '/' + o.get('n', ''))
                if k not in rank:
                    rank[k] = i
            albums.sort(key=lambda a: rank.get(a['g'] + '/' + a['n'], 10 ** 9))
            order_sig = hashlib.md5(raw).hexdigest()[:12]
    except Exception as e:
        print('[排序] 读取失败:', repr(e)[:80])

    # 缩略图必须先并行生成：文件名用源路径哈希，移动后稳定且不会复用到别的照片。
    # 首次从旧的 %04d.jpg 迁移会一次性生成全部；之后只生成移动/新增/改过的。
    thumb_tasks = []
    for a in albums:
        tdir = os.path.join(OUT, 'thumbs', a['g'], a['n'])
        for p in a['items']:
            media, _ = resolve_media(p)
            thumb_tasks.append((media, os.path.join(tdir, thumb_key(p) + '.jpg')))
    if thumb_tasks:
        print('[缩略图] 检查/生成 %d 张（并行）...' % len(thumb_tasks), flush=True)
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(lambda t: make_thumb(*t), thumb_tasks))

    # 相册内页的「移动到相册」目标列表：内页不加载 photos.json，必须注入全部相册，
    # 否则 meta 为空、面板会提示「没有可移动的目标相册」。当前相册由 __CURP 排除。
    move_meta = []
    for a in albums:
        move_meta.append({
            'g': a['g'], 'n': a['n'], 'c': len(a['items']),
            'p': '/' + quote(rel_to_root(a['dir'])),
        })

    total_files = 0
    newest = 0.0
    for a in albums:
        total_files += len(a['items'])
        for p in a['items']:
            try:
                m = os.path.getmtime(p)
                if m > newest:
                    newest = m
            except OSError:
                pass
    # 新建/删除空相册只改 albums.json，文件数和 mtime 都不变 —— 必须把它算进签名，
    # 否则生成器判定"没变化"直接跳过，用户新建的相册永远不出现。
    reg_sig = ''
    try:
        rf = os.path.join(OUT, 'albums.json')
        if os.path.exists(rf):
            reg_sig = hashlib.md5(open(rf, 'rb').read()).hexdigest()[:12]
    except Exception:
        pass
    sig = '%s|%d|%d|%s|%s' % (TEMPLATE_VER, total_files, int(newest), order_sig, reg_sig)
    sigfile = os.path.join(OUT, '.sig')
    try:
        if os.path.exists(sigfile) and open(sigfile, encoding='utf-8').read().strip() == sig:
            return 0
    except Exception:
        pass
    try:
        with open(sigfile, 'w', encoding='utf-8') as f:
            f.write(sig)
    except Exception:
        pass

    global REGENERATED
    REGENERATED = True

    photos = []
    meta = []
    global DUR_CACHE
    DUR_CACHE = load_durations()

    for a in albums:
        g, n, items = a['g'], a['n'], a['items']
        tdir = os.path.join(OUT, 'thumbs', g, n)
        cells = []
        thumbs = []
        for i, p in enumerate(items):
            rel = rel_to_root(p)
            key = thumb_key(p)
            media, converted = resolve_media(p)      # HEIC → JPEG，浏览器不认 HEIC
            full = ('/相册/heic/%s.jpg' % quote(key)) if converted else ('/' + quote(rel))
            tpath = os.path.join(tdir, key + '.jpg')
            ok = make_thumb(media, tpath)
            ts = media_ts(p)
            turl = ('/相册/thumbs/%s/%s/%s.jpg?v=%d' % (quote(g), quote(n), key, ts)) if ok else ''
            thumbs.append(turl)
            is_vid = os.path.splitext(p)[1].lower() in VID
            if is_vid:
                try:
                    mt = int(os.path.getmtime(p))
                except OSError:
                    mt = 0
                c = DUR_CACHE.get(full)
                if c and c[0] == mt and c[1]:
                    pass
                else:
                    ds = probe_duration(p)
                    if ds:
                        DUR_CACHE[full] = [mt, ds]
                    elif c:
                        DUR_CACHE.pop(full, None)
            try:
                fsize = os.path.getsize(p)
            except OSError:
                fsize = 0
            cells.append('[%s, %d, %d, %s, %d]' % (json.dumps(full), 1 if is_vid else 0, ts,
                                                   json.dumps(turl), fsize))
            photos.append([turl, full, ts, 1 if is_vid else 0, n, fsize])

        # 封面用相册里按修改时间最新、且缩略图生成成功的那一项（照片/视频都算）。
        cover = None
        if items:
            try:
                newest_first = sorted(range(len(items)),
                                      key=lambda k: media_ts(items[k]), reverse=True)
            except OSError:
                newest_first = list(range(len(items)))
            cover = next((thumbs[k] for k in newest_first if thumbs[k]), None)

        drel = '/' + quote(rel_to_root(a['dir']))
        meta.append({'g': g, 'n': n, 'c': len(items), 'cv': cover or '', 'p': drel,
                     'key': g + '/' + n})

        adir = os.path.join(OUT, g, n)
        os.makedirs(adir, exist_ok=True)
        head = ('<div class="bar"><a href="/相册/index.html#albums">‹ 相册</a>'
                '<div class="t">%s</div><div class="n" id="acnt" style="color:#888;font-size:12px">%d 项</div></div>'
                % (html.escape(n), len(items)))
        doc = ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
               '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
               '<meta name="theme-color" content="#0f0f10">'
               '<link rel="icon" href="data:,">'
               '<title>%s</title><style>%s</style></head><body>%s'
               '<main><div id="g"></div></main>%s%s%s'
               '<script>window.__ALBUM=%s;window.__CURP=%s;window.__ALBUMS=%s;window.__LIST=%s;</script><script>%s</script>'
               '</body></html>'
               % (html.escape(n), CSS, head, VIEWER_HTML, SELECT_HTML,
                  scrub_html('52px', '14px'),
                  json.dumps(n, ensure_ascii=False),
                  json.dumps(drel, ensure_ascii=False),
                  json.dumps(move_meta, ensure_ascii=False),
                  '[' + ','.join(cells) + ']',
                  VIEWER_JS + SELECT_JS + SCRUB_JS + ALBUM_JS))
        with open(os.path.join(adir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(doc)
        print('  [%s] %-22s %4d 项' % (g, n, len(items)))

    photos.sort(key=lambda x: -x[2])
    save_ts_cache()          # 拍摄时间缓存落盘，下次重建不用再读 EXIF
    # 视频时长（增量缓存）
    try:
        json.dump(DUR_CACHE, io.open(DUR_FILE, 'w', encoding='utf-8'), ensure_ascii=False)
    except Exception as e:
        print('写 durations.json 失败:', repr(e)[:60])

    payload = {'albums': meta, 'photos': photos, 'updated': int(time.time())}
    with open(os.path.join(OUT, 'photos.json'), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))

    index = ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
             '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
             '<meta name="theme-color" content="#0f0f10">'
             '<link rel="icon" href="data:,">'
             '<title>照片</title><style>%s</style></head><body class="idx">'
             '<header><div class="title" id="title">照片</div><div style="flex:1"></div>'
             '<div id="stat"><i></i><span>—</span></div>'
             '<div class="hact">'
             '<span id="sbtn"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" '
             'stroke="currentColor" stroke-width="2" stroke-linecap="round">'
             '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/></svg></span></div></header>'
             '<div id="sbar"><input id="sinput" type="search" placeholder="搜索文件名…"><b id="sclose">取消</b></div>'
             '<div class="pager" id="pager">'
             '<div class="pane-page" id="pg-timeline"><div class="pad">'
             '<div id="otd-slot"></div><div id="timeline"></div><div id="sentinel" style="height:40px"></div>'
             '</div></div>'
             '<div class="pane-page" id="pg-albums"><div class="pad"><div id="albums"></div></div></div>'
             '</div>%s'
             '<nav><div class="on" id="b-timeline" onclick="goTab(\'timeline\')">'
             '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1.6"/>'
             '<rect x="14" y="3" width="7" height="7" rx="1.6"/><rect x="3" y="14" width="7" height="7" rx="1.6"/>'
             '<rect x="14" y="14" width="7" height="7" rx="1.6"/></svg>时间轴</div>'
             '<div id="b-albums" onclick="goTab(\'albums\')">'
             '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2.2"/>'
             '<path d="M3 15l4.5-4.5 3 3"/><circle cx="15.5" cy="10" r="1.6"/></svg>相册</div></nav>'
             '%s%s<script>%s</script></body></html>'
             % (CSS, VIEWER_HTML, SELECT_HTML, scrub_html('54px', '58px'),
                VIEWER_JS + SELECT_JS + SCRUB_JS + INDEX_JS))
    index = index.replace('TVER_PLACEHOLDER', TEMPLATE_VER)
    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index)

    print()
    try:
        # 相似（连拍）检测：同相册 + 文件名主干相同 + 时间差<=3s + 大小相近
        try:
            from urllib.parse import unquote as _unq
            by_key = {}
            for p_ in photos:
                base = os.path.basename(_unq(p_[1]))
                stem = re.sub(r'[_-]?\d{2,}$', '', os.path.splitext(base)[0])
                if not stem or len(stem) < 4:
                    continue
                by_key.setdefault(str(p_[4]) + '|' + stem, []).append(p_)
            sim = []
            for _k, arr in by_key.items():
                if len(arr) < 2:
                    continue
                arr.sort(key=lambda x: x[2])
                cur = [arr[0]]
                for x in arr[1:]:
                    prev = cur[-1]
                    dsz = abs((x[5] or 0) - (prev[5] or 0))
                    lim = max(4096, (prev[5] or 1) * 0.12)
                    if x[2] - prev[2] <= 3 and dsz <= lim:
                        cur.append(x)
                    else:
                        if len(cur) >= 2:
                            sim.append(cur)
                        cur = [x]
                if len(cur) >= 2:
                    sim.append(cur)
            sim.sort(key=lambda g: -len(g))
            json.dump(sim[:80], io.open(os.path.join(OUT, 'similar.json'), 'w',
                                        encoding='utf-8'), ensure_ascii=False)
        except Exception as e:
            print('相似检测失败:', repr(e)[:80])

        try:
            trash_n = build_trash_page(OUT)
        except Exception as e:
            trash_n = 0
            print('回收站页生成失败:', repr(e)[:80])
        try:
            clean_empty_batches()
        except Exception:
            pass
        try:
            tomb_n = update_tombstones()
        except Exception as e:
            tomb_n = 0
            print('已删除名单更新失败:', repr(e)[:60])
        try:
            st_tr = {'trash': trash_n}
            json.dump(st_tr, io.open(os.path.join(OUT, 'trash.json'), 'w', encoding='utf-8'))
        except Exception:
            pass

        # 往年今日：同月日 ±3 天、年份不同
        tday = time.localtime()
        otd = []
        for p_ in photos:
            try:
                d = time.localtime(p_[2])
            except (OSError, ValueError):
                continue
            if d.tm_year >= tday.tm_year:
                continue
            dt = abs((d.tm_yday - tday.tm_yday))
            if dt <= 3 or dt >= 362:
                otd.append((d.tm_year, p_))
        otd.sort(key=lambda x: (-x[0], -x[1][2]))
        json.dump([p_ for _, p_ in otd[:24]],
                  io.open(os.path.join(OUT, 'onthisday.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False)

        st = {'generated': int(time.time()), 'albums': len(meta), 'photos': len(photos),
              'newest': int(newest), 'videos': sum(1 for p in photos if p[3] == 1)}
        json.dump(st, io.open(os.path.join(OUT, 'status.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False)
    except Exception as e:
        print('写 status.json 失败:', repr(e)[:60])

    print('完成：%d 个相册，%d 项媒体' % (len(meta), len(photos)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
