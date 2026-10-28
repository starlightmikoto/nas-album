# -*- coding: utf-8 -*-
"""停止后台运行的相册服务（只杀监听本配置端口的 dufs/python）。"""
import io
import json
import os
import subprocess
import sys

FROZEN = getattr(sys, 'frozen', False)
HERE = (os.path.dirname(sys.executable) if FROZEN
        else os.path.dirname(os.path.abspath(__file__)))

# Windows 控制台默认是 GBK，中文/符号会乱码甚至报错：统一切到 UTF-8
try:
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
CFG = os.path.join(HERE, 'web', 'album_config.json')


def main():
    try:
        cfg = json.load(io.open(CFG, encoding='utf-8'))
    except Exception:
        print('没有配置，可能本来就没在跑。')
        return 1
    port = int(cfg.get('port', 8081))
    out = subprocess.run(['netstat', '-ano'], capture_output=True, text=True,
                         encoding='utf-8', errors='replace', timeout=20).stdout
    pids = set()
    for ln in out.splitlines():
        if 'LISTENING' in ln and (':%d ' % port) in ln + ' ':
            parts = ln.split()
            if parts and parts[-1].isdigit():
                pids.add(parts[-1])
    if not pids:
        print('端口 %d 上没有服务在跑。' % port)
        return 0
    for pid in pids:
        r = subprocess.run(['tasklist', '/FI', 'PID eq %s' % pid, '/FO', 'CSV', '/NH'],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace').stdout
        name = (r.strip().strip('"').split('","')[0] if r.strip() else '').lower()
        if name in ('dufs.exe', 'python.exe', 'pythonw.exe', 'python3.exe'):
            subprocess.run(['taskkill', '/PID', pid, '/T', '/F'], capture_output=True)
            print('已停止 %s (pid %s)' % (name, pid))
        else:
            print('端口 %d 被 %s 占用，不是本项目的，跳过' % (port, name or '未知'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
