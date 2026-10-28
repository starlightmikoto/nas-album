# -*- coding: utf-8 -*-
"""回收站页面生成器：扫描 D:\\NAS\\06_回收站，输出 /相册/回收站.html。

v72 起：
1. 图片行用 160px 缩略图（缩略图缺失时才回退原图），不再让 52px 的格子下载整张原图；
2. 页面打开时会用 dufs 的 `?json` 接口**现场拉一遍目录**再渲染，
   刚删掉的照片立刻能看到（之前只靠每分钟重建静态页，最多滞后 1 分钟，用户以为删丢了）；
3. 拉取失败（离线/接口不可用）时保留服务端渲染的内容，页面照常可用。

单独成文件是为了避免在 gen_album4.py 里嵌套多层引号。
"""
import html as _html
import io
import json
import os
import re
import shutil
import subprocess
import time
from urllib.parse import quote as _q

# 根目录：环境变量 > 同目录 album_config.json > 默认（脚本上一层/photos）
_CFG = {}
try:
    import io as _io
    import json as _json
    import os as _os
    _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'album_config.json')
    if _os.path.exists(_p):
        _CFG = _json.load(_io.open(_p, encoding='utf-8'))
except Exception:
    _CFG = {}
ROOT = (_CFG.get('root') or '')
RECYCLE = _os.path.join(ROOT, '06_回收站') if ROOT else r'06_回收站'
BATCH_RE = re.compile(r'^\d{8}-\d{6}-[a-z0-9]{4}$')
VID_EXT = ('.mp4', '.mov', '.3gp', '.mkv', '.avi')
IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.heic')
THUMB_W = 160
FF = _CFG.get('ffmpeg') or 'ffmpeg'
CREATE_NO_WINDOW = 0x08000000


def thumb_rel(batch, name):
    """缩略图 URL（相对 /相册）。"""
    return '/相册/thumbs/_回收站/%s/%s.jpg' % (_q(batch), _q(os.path.splitext(name)[0]))


def _make_thumb(out_dir, batch, name):
    """生成 160px 缩略图，成功返回 True。"""
    if not os.path.exists(FF):
        return False
    src = os.path.join(RECYCLE, batch, name)
    dst = os.path.join(out_dir, 'thumbs', '_回收站', batch, os.path.splitext(name)[0] + '.jpg')
    try:
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
            return True
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        r = subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-i', src,
                            '-vf', 'scale=%d:-2' % THUMB_W, '-q:v', '5', dst],
                           capture_output=True, timeout=60, creationflags=CREATE_NO_WINDOW)
        return r.returncode == 0 and os.path.exists(dst)
    except Exception:
        return False


PAGE = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f0f10"><link rel="icon" href="data:,"><title>回收站</title><style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:#0f0f10;color:#ededef;font:14px/1.4 -apple-system,system-ui,"PingFang SC","Microsoft YaHei",sans-serif;padding-bottom:24px}
.bar{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:10px;height:52px;padding:0 14px;
  background:#0d0d0ef7;backdrop-filter:blur(16px);border-bottom:1px solid #ffffff0f}
.bar a{color:#7aa7ff;text-decoration:none;font-size:15px}
.bar .t{font-size:16px;font-weight:650}
.tip{padding:12px 16px;color:#8a8a90;font-size:12.5px}
.tbar{display:flex;align-items:center;gap:10px;padding:8px 14px;border-bottom:1px solid #ffffff0f;
  background:#141416;position:sticky;top:52px;z-index:4}
.tbar .all{display:flex;align-items:center;gap:7px;font-size:13px;color:#c9c9cf}
.tbar .sp{flex:1}
.tbar .del{font-size:12.5px;padding:7px 12px;border-radius:9px;border:1px solid #ff5a5a55;
  background:#ff5a5a18;color:#ff8f8f}
.tbar .del:disabled{opacity:.4}
.ck{width:18px;height:18px;flex:none;accent-color:#3b82f6;margin:0}
.bh{padding:14px 16px 6px;color:#78787d;font-size:12px}
.row{display:flex;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid #ffffff0a}
.th{width:52px;height:52px;flex:none;border-radius:7px;object-fit:cover;background:#1b1b1f;display:block}
.th.vid{display:flex;align-items:center;justify-content:center;color:#8a8a90;font-size:16px}
.mid{flex:1;min-width:0}
.nm{font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mt{color:#78787d;font-size:11.5px;margin-top:2px}
.row button{flex:none;font-size:12px;padding:6px 10px;border-radius:8px;border:1px solid #ffffff1f;
  background:#ffffff10;color:#d6d6da}
.row button.rs{color:#7ab4ff;border-color:#7ab4ff44;background:#7ab4ff1a}
.row button:disabled{opacity:.45}
.th,.nm{cursor:pointer}
.empty{padding:40px 16px;text-align:center;color:#78787d}
.ov{position:fixed;inset:0;z-index:80;background:#000000f2;display:none;align-items:center;justify-content:center}
.ov.on{display:flex}
.ov img,.ov video{max-width:100vw;max-height:100vh;object-fit:contain}
</style></head><body>
<div class="bar"><a href="/相册/index.html#albums">‹ 相册</a><div class="t">回收站</div>
<div style="flex:1"></div><div id="tot" style="color:#78787d;font-size:12px">__TOTAL__ 项</div></div>
<div class="tip">删除的照片在这里保留 30 天，之后自动清理。点「恢复」放回原来的相册；点缩略图可看原图。</div>
<div class="tbar">
  <label class="all"><input type="checkbox" id="ckall"> 全选</label>
  <div class="sp"></div>
  <button class="del" id="delSel" disabled>永久删除选中(0)</button>
</div>
<div id="rows">__BODY__</div>
<div class="ov" id="ov"></div>
<script>
(function(){
  var rows=document.getElementById('rows'), tot=document.getElementById('tot');
  var BR=/^\\d{8}-\\d{6}-[a-z0-9]{4}$/, VID=/\\.(mp4|mov|3gp|mkv|avi)$/i;
  function bust(u){ return u+(u.indexOf('?')<0?'?':'&')+'_='+Date.now(); }
  function jget(u){ return fetch(bust(u),{credentials:'same-origin',cache:'no-store'})
      .then(function(r){ return r.ok?r.json():null; }).catch(function(){ return null; }); }
  function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  function dec(s){ try{ return decodeURIComponent(s||''); }catch(e){ return s||''; } }
  function sz(z){ return z>=1048576 ? (z/1048576).toFixed(1)+' MB' : Math.round((z||0)/1024)+' KB'; }
  function fmtT(ms){ if(!ms) return '—'; var d=new Date(ms);
    function p(n){ return n<10?'0'+n:''+n; }
    return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+' '+p(d.getHours())+':'+p(d.getMinutes()); }
  function idTime(id){ try{ return new Date(+id.slice(0,4),+id.slice(4,6)-1,+id.slice(6,8),
      +id.slice(9,11),+id.slice(11,13),+id.slice(13,15)).getTime(); }catch(e){ return 0; } }

  function rowHTML(b,f){
    var isVid=VID.test(f.name);
    var orig='/06_回收站/'+encodeURIComponent(b)+'/'+encodeURIComponent(f.name);
    var th='/相册/thumbs/_回收站/'+encodeURIComponent(b)+'/'+
      encodeURIComponent(f.name.replace(/\\.[^.]+$/,''))+'.jpg';
    var thumb=isVid ? '<div class="th vid">▶</div>'
      : '<img class="th" loading="lazy" alt="" src="'+th+'" data-orig="'+esc(orig)+'">';
    return '<div class="row" data-b="'+esc(b)+'" data-n="'+esc(f.name)+'" data-s="'+esc(f.src)+'">'
      + '<input type="checkbox" class="ck">'
      + thumb + '<div class="mid"><div class="nm">'+esc(f.name)+'</div>'
      + '<div class="mt">'+sz(f.size)+(f.src?'':' · 原路径未知')+'</div></div>'
      + '<button class="rs">恢复</button><button class="dl">彻底删</button></div>';
  }
  function bindFallback(){
    Array.prototype.forEach.call(rows.querySelectorAll('img.th'),function(im){
      if(im.__fb) return; im.__fb=1;
      im.onerror=function(){ this.onerror=null; var o=this.getAttribute('data-orig');
        if(o && this.src.indexOf(o)<0) this.src=o; };
      if(im.complete && im.naturalWidth===0) im.onerror();
    });
  }
  function render(list){
    var html='', n=0;
    list.forEach(function(b){
      html+='<div class="bh">'+fmtT(b.t)+' · '+b.files.length+' 项</div>';
      b.files.forEach(function(f){ html+=rowHTML(b.id,f); n++; });
    });
    rows.innerHTML = html || '<p class="empty">回收站是空的。</p>';
    tot.textContent = n+' 项';
    bindFallback();
    if(typeof updateSel==='function') updateSel();
  }
  function load(){
    return jget('/06_回收站/?json').then(function(top){
      if(!top || !top.paths) return false;                 // 接口不可用：保留服务端渲染
      var bs=top.paths.filter(function(p){ return p.path_type==='Dir' && BR.test(p.name); })
        .map(function(p){ return {id:p.name, t:p.mtime||idTime(p.name)}; })
        .sort(function(a,b){ return a.id<b.id?1:-1; });
      if(!bs.length){ render([]); return true; }
      return Promise.all(bs.map(function(b){
        var base='/06_回收站/'+encodeURIComponent(b.id);
        return Promise.all([jget(base+'/?json'), jget(base+'/_meta.json')]).then(function(a){
          var list=(a[0]&&a[0].paths)?a[0].paths.filter(function(p){
            return p.path_type==='File' && p.name!=='_meta.json'; }) : [];
          var meta={}; ((a[1]&&a[1].items)||[]).forEach(function(it){
            if(it&&it.name) meta[it.name]=dec(it.src); });
          b.files=list.map(function(p){
            return {name:p.name, size:p.size||0, mtime:p.mtime||0, src:meta[p.name]||''};
          }).sort(function(x,y){ return x.name<y.name?-1:1; });
          if(!b.t && b.files.length) b.t=b.files[0].mtime;
          return b;
        });
      })).then(function(all){ render(all); return true; });
    }).catch(function(){ return false; });
  }

  // 点缩略图看原图，再点一下关掉
  var ov=document.getElementById('ov');
  function openOv(b,n){
    if(!b||!n) return;
    var u='/06_回收站/'+encodeURIComponent(b)+'/'+encodeURIComponent(n);
    ov.innerHTML = VID.test(n)
      ? '<video src="'+u+'" controls autoplay playsinline></video>'
      : '<img alt="" src="'+u+'">';
    ov.classList.add('on');
    try{ if(!(history.state&&history.state.pv)) history.pushState({pv:1},'','#pv'); }catch(e){}
  }
  function closeOv(){ ov.classList.remove('on'); ov.innerHTML=''; }
  function closeOvBack(){
    if(history.state&&history.state.pv){ history.back(); return; }   // 交给 popstate 收尾
    closeOv();
  }
  // 关键：手指按下就关，并吃掉这次触摸的 click。
  // 否则关掉的瞬间会「穿透」到下面那行的按钮，误触「恢复」/「彻底删」（幽灵点击）。
  ov.addEventListener('touchstart',function(e){
    e.preventDefault(); e.stopPropagation(); closeOvBack();
  },{passive:false});
  ov.addEventListener('click',function(e){
    e.stopPropagation();
    if(ov.classList.contains('on')) closeOvBack();
  });
  document.addEventListener('keydown',function(e){ if(e.key==='Escape') closeOvBack(); });

  // 恢复 / 彻底删：事件委托，服务端渲染和现场渲染的行都适用
  rows.addEventListener('click',function(e){
    var pic=e.target.closest ? e.target.closest('.th,.nm') : null;
    if(pic){
      var r0=pic.closest('.row');
      if(r0){ openOv(r0.getAttribute('data-b'), r0.getAttribute('data-n')); return; }
    }
    var btn=e.target.closest ? e.target.closest('button') : null;
    if(!btn) return;
    var row=btn.closest('.row'); if(!row) return;
    var b=row.getAttribute('data-b'), n=row.getAttribute('data-n'), s=row.getAttribute('data-s');
    if(btn.classList.contains('rs')){
      if(!s){ alert('这条记录缺少原路径（早期删除的），无法自动恢复。'); return; }
      if(!confirm('恢复到原位置？')) return;
      btn.disabled=true; btn.textContent='...';
      fetch(s,{method:'HEAD',credentials:'same-origin',cache:'no-store'}).then(function(r){
        if(r.status===200||r.status===204){ btn.disabled=false; btn.textContent='恢复';
          alert('原位置已有同名文件，未恢复（避免覆盖）'); return; }
        if(r.status!==404){ btn.disabled=false; btn.textContent='恢复';
          alert('无法确认目标位置（HTTP '+r.status+'），未恢复'); return; }
        // 目标目录可能已随相册一起删掉：先补建，才能把照片放回去（相册也会随之复原）
        var parent=s.slice(0,s.lastIndexOf('/'));
        var mk=fetch(parent,{method:'MKCOL',credentials:'same-origin'}).catch(function(){});
        return mk.then(function(){
          return fetch('/06_回收站/'+encodeURIComponent(b)+'/'+encodeURIComponent(n),
          {method:'MOVE',credentials:'same-origin',
           headers:{'Destination':location.origin+(/%[0-9A-Fa-f]{2}/.test(s)?s:encodeURI(s)),
                    'Overwrite':'F'}});
        }).then(function(r2){
          if(r2.ok){ row.style.opacity=.4;
            Array.prototype.forEach.call(row.querySelectorAll('button'),function(x){x.disabled=true;});
            var t=parseInt(tot.textContent,10); if(!isNaN(t)&&t>0) tot.textContent=(t-1)+' 项';
            load(); }
          else { btn.disabled=false; btn.textContent='恢复'; alert('恢复失败（HTTP '+r2.status+'）'); }
        });
      }).catch(function(){ btn.disabled=false; btn.textContent='恢复'; alert('网络错误，未恢复'); });
    }else if(btn.classList.contains('dl')){
      if(!confirm('彻底删除「'+n+'」？无法恢复。')) return;
      fetch('/06_回收站/'+encodeURIComponent(b)+'/'+encodeURIComponent(n),
        {method:'DELETE',credentials:'same-origin'}).then(function(r){
        if(r.ok||r.status===404){ row.style.display='none';
          var t=parseInt(tot.textContent,10); if(!isNaN(t)&&t>0) tot.textContent=(t-1)+' 项'; load(); }
        else alert('删除失败（HTTP '+r.status+'）');
      });
    }
  });

  // 批量选择 / 全选 / 永久删除
  var ckall=document.getElementById('ckall'), delSel=document.getElementById('delSel');
  function boxes(){ return Array.prototype.slice.call(rows.querySelectorAll('.row .ck')); }
  function selected(){
    return Array.prototype.slice.call(rows.querySelectorAll('.row'))
      .filter(function(r){ var c=r.querySelector('.ck'); return c && c.checked; })
      .map(function(r){ return {b:r.getAttribute('data-b'), n:r.getAttribute('data-n'), row:r}; });
  }
  var poppingSel=false;
  function updateSel(){
    if(!delSel) return;
    var n=selected().length, all=boxes();
    if(n===0 && !poppingSel && history.state && history.state.ts){ history.back(); }
    delSel.textContent='永久删除选中('+n+')';
    delSel.disabled=(n===0);
    if(ckall){
      ckall.checked=(all.length>0 && n===all.length);
      ckall.indeterminate=(n>0 && n<all.length);
    }
  }
  rows.addEventListener('change',function(e){
    if(e.target && e.target.classList && e.target.classList.contains('ck')){
      updateSel();
      if(selected().length>0 && !(history.state&&history.state.ts)){
        try{ history.pushState({ts:1},'','#ts'); }catch(e2){}
      }
    }
  });
  if(ckall) ckall.onchange=function(){
    boxes().forEach(function(c){ c.checked=ckall.checked; });
    updateSel();
  };
  if(delSel) delSel.onclick=function(){
    var list=selected(); if(!list.length) return;
    if(!confirm('永久删除选中的 '+list.length+' 项？删除后无法恢复。')) return;
    delSel.disabled=true; delSel.textContent='删除中…';
    var fail=0, batches={};
    list.forEach(function(x){ if(x.b) batches[x.b]=1; });
    (function one(i){
      if(i>=list.length){
        // 批次删空后连目录一起删掉，别再留一行「时间 · 0 项」
        var bs=Object.keys(batches);
        (function delDir(k){
          if(k>=bs.length){ load(); if(fail) setTimeout(function(){ alert('有 '+fail+' 项删除失败，请重试'); },400); return; }
          fetch('/06_回收站/'+encodeURIComponent(bs[k]),{method:'DELETE',credentials:'same-origin'})
            .then(function(){ delDir(k+1); }).catch(function(){ delDir(k+1); });
        })(0);
        return;
      }
      fetch('/06_回收站/'+encodeURIComponent(list[i].b)+'/'+encodeURIComponent(list[i].n),
        {method:'DELETE',credentials:'same-origin'}).then(function(r){
          if(!(r.ok||r.status===404)) fail++;
          one(i+1);
        }).catch(function(){ fail++; one(i+1); });
    })(0);
  };
  updateSel();

  // 返回手势：详情图 > 勾选 > 上一页
  window.addEventListener('popstate',function(){
    if(ov.classList.contains('on')){ closeOv(); return; }
    var checked=rows.querySelectorAll('.row .ck:checked');
    if(checked.length){
      poppingSel=true;
      Array.prototype.forEach.call(checked,function(c){ c.checked=false; });
      var ck=document.getElementById('ckall'); if(ck){ ck.checked=false; ck.indeterminate=false; }
      poppingSel=false;
      updateSel();
      return;
    }
  });

  bindFallback();
  load();
})();
</script></body></html>"""


def scan():
    batches = []
    if not os.path.isdir(RECYCLE):
        return batches, 0
    for b in sorted(os.listdir(RECYCLE), reverse=True):
        p = os.path.join(RECYCLE, b)
        if not os.path.isdir(p) or not BATCH_RE.match(b):
            continue
        meta = {}
        mf = os.path.join(p, '_meta.json')
        if os.path.exists(mf):
            try:
                for it in json.load(io.open(mf, encoding='utf-8')).get('items', []):
                    if it.get('name'):
                        meta[it['name']] = it.get('src') or ''
            except Exception:
                pass
        files = []
        for f in sorted(os.listdir(p)):
            fp = os.path.join(p, f)
            if f == '_meta.json' or not os.path.isfile(fp):
                continue
            try:
                files.append({'n': f, 's': meta.get(f, ''), 'z': os.path.getsize(fp)})
            except OSError:
                continue
        if files:
            try:
                bt = int(os.path.getmtime(p))
            except OSError:
                bt = 0
            batches.append({'id': b, 't': bt, 'files': files})
    return batches, sum(len(x['files']) for x in batches)


def build_trash_page(out_dir, make_thumbs=True):
    batches, total = scan()
    # 清掉已不存在的批次留下的缩略图，避免 thumbs/_回收站 越积越多
    tbase = os.path.join(out_dir, 'thumbs', '_回收站')
    if os.path.isdir(tbase):
        live = set(b['id'] for b in batches)
        for d in os.listdir(tbase):
            p = os.path.join(tbase, d)
            if os.path.isdir(p) and d not in live:
                shutil.rmtree(p, ignore_errors=True)
    rows = []
    for b in batches:
        bt = time.strftime('%Y-%m-%d %H:%M', time.localtime(b['t'])) if b['t'] else b['id']
        rows.append('<div class="bh">%s · %d 项</div>' % (_html.escape(bt), len(b['files'])))
        for f in b['files']:
            sz = ('%.1f MB' % (f['z'] / 1048576)) if f['z'] >= 1048576 else ('%.0f KB' % (f['z'] / 1024))
            orig_url = '/06_回收站/%s/%s' % (b['id'], _q(f['n']))
            if f['n'].lower().endswith(VID_EXT):
                thumb = '<div class="th vid">▶</div>'
            else:
                turl = None
                if make_thumbs and f['n'].lower().endswith(IMG_EXT):
                    if _make_thumb(out_dir, b['id'], f['n']):
                        turl = thumb_rel(b['id'], f['n'])
                thumb = ('<img class="th" loading="lazy" alt="" src="%s" data-orig="%s">'
                         % (_html.escape(turl or orig_url, quote=True),
                            _html.escape(orig_url, quote=True)))
            rows.append(
                '<div class="row" data-b="%s" data-n="%s" data-s="%s">'
                '<input type="checkbox" class="ck">%s'
                '<div class="mid"><div class="nm">%s</div>'
                '<div class="mt">%s%s</div></div>'
                '<button class="rs">恢复</button><button class="dl">彻底删</button></div>'
                % (_html.escape(b['id']), _html.escape(f['n'], quote=True),
                   _html.escape(f['s'], quote=True), thumb, _html.escape(f['n']),
                   sz, '' if f['s'] else ' · 原路径未知'))
    body = ''.join(rows) if rows else '<p class="empty">回收站是空的。</p>'
    doc = PAGE.replace('__TOTAL__', str(total)).replace('__BODY__', body)
    io.open(os.path.join(out_dir, '回收站.html'), 'w', encoding='utf-8').write(doc)
    return total
