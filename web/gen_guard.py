# -*- coding: utf-8 -*-
"""生成相册并做 JS 语法自检（供每分钟任务调用，防止再出现脚本错误导致页面空白）。"""
import io
import os
import shutil
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def _find_node():
    """找 Node：环境变量 > PATH > 常见安装位置；找不到就跳过 JS 自检。"""
    p = os.environ.get('NODE')
    if p and os.path.exists(p): return p
    w = shutil.which('node') or shutil.which('node.exe')
    if w: return w
    for c in ('/usr/bin/node', '/usr/local/bin/node',
              r'C://Program Files\nodejs\node.exe'):
        if os.path.exists(c): return c
    return ''

NODE = _find_node()
CREATE_NO_WINDOW = 0x08000000
BASE = os.environ.get('ALBUM_OUT') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'photos', '相册')
ERRLOG = os.path.join(BASE, 'gen_error.log')
LOCK = os.path.join(BASE, '.gen.lock')


def acquire_lock():
    try:
        os.makedirs(BASE, exist_ok=True)      # 首次运行时输出目录还不存在
    except Exception:
        pass
    """防止每分钟任务和手工全量缩略图迁移重叠。"""
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        try:
            if time.time() - os.path.getmtime(LOCK) < 900:
                print('[生成] 已有生成任务在跑，跳过')
                return False
            os.remove(LOCK)
        except OSError:
            return False
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except OSError:
            return False


def check(html_path):
    if not os.path.exists(html_path):
        return ['文件不存在: ' + html_path]
    html = io.open(html_path, encoding='utf-8').read()
    errs = []
    for i, code in enumerate(re.findall(r'<script[^>]*>([\s\S]*?)</script>', html)):
        if len(code.strip()) < 10:
            continue
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(code)
            tmp = f.name
        try:
            r = subprocess.run([NODE, '--check', tmp], capture_output=True, text=True,
                               errors='replace', timeout=30,
                               creationflags=CREATE_NO_WINDOW)
            if r.returncode != 0:
                first = (r.stderr or '').strip().split('\n')
                detail = next((ln for ln in first if 'Error' in ln), 'syntax error')
                errs.append('%s script[%d]: %s' % (os.path.basename(html_path), i, detail[:200]))
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return errs


def main():
    if not acquire_lock():
        return 0
    try:
        import gen_album4
        gen_album4.main()
        if not getattr(gen_album4, 'REGENERATED', False):
            return 0   # 内容没变化，跳过语法检查，避免每分钟起 node 进程

        errs = []
        errs += check(os.path.join(BASE, 'index.html'))
        cam = os.path.join(BASE, '相机', '相机', 'index.html')
        errs += check(cam)

        try:
            if errs:
                with io.open(ERRLOG, 'a', encoding='utf-8') as f:
                    for e in errs:
                        f.write(e + '\n')
            elif os.path.exists(ERRLOG):
                os.remove(ERRLOG)
        except Exception:
            pass
        return 0
    finally:
        try:
            os.remove(LOCK)
        except OSError:
            pass


if __name__ == '__main__':
    sys.exit(main())
