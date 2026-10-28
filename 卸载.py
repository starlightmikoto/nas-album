# -*- coding: utf-8 -*-
"""一键撤销：把云相册对这台电脑做过的改动清干净。

只删「我们自己生成的东西」，**绝不碰你的照片**。

    python 卸载.py
"""
import io
import json
import os
import shutil
import socket
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

# 我们可能创建过的目录（只删空的，或用 --purge 时整删「相册」这种纯产物目录）
GEN_DIRS = ['相册']


def line(t=''):
    print(t)


def load_cfg():
    try:
        return json.load(io.open(CFG, encoding='utf-8'))
    except Exception:
        return {}


def port_pids(port):
    """找监听该端口的进程。"""
    pids = []
    try:
        out = subprocess.run(['netstat', '-ano'], capture_output=True, text=True,
                             encoding='utf-8', errors='replace', timeout=20).stdout
    except Exception:
        return pids
    for ln in out.splitlines():
        if 'LISTENING' in ln and (':%d ' % port) in ln + ' ':
            parts = ln.split()
            if parts and parts[-1].isdigit():
                pids.append(int(parts[-1]))
    return sorted(set(pids))


def proc_name(pid):
    try:
        out = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/FO', 'CSV', '/NH'],
                             capture_output=True, text=True, encoding='utf-8',
                             errors='replace', timeout=15).stdout
        return out.strip().strip('"').split('","')[0] if out.strip() else ''
    except Exception:
        return ''


def stop_service(port):
    killed = []
    for pid in port_pids(port):
        name = proc_name(pid)
        if name.lower() in ('dufs.exe', 'python.exe', 'pythonw.exe', 'python3.exe'):
            try:
                subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                               capture_output=True, timeout=15)
                killed.append('%s(pid %d)' % (name, pid))
            except Exception:
                pass
        else:
            line('  端口 %d 被 %s 占用，不是本项目的进程，跳过' % (port, name or '未知'))
    return killed


def del_rule(port):
    if os.name != 'nt':
        return
    for name in ('相册服务 %d' % port, '相册服务'):
        try:
            r = subprocess.run(['netsh', 'advfirewall', 'firewall', 'delete', 'rule',
                                'name=%s' % name],
                               capture_output=True, text=True, encoding='utf-8',
                               errors='replace', timeout=20)
            if r.returncode == 0:
                line('  已删除防火墙规则：%s' % name)
        except Exception:
            pass


def is_gen_dir(p):
    """确认这个目录是生成出来的相册页（有一堆固定文件），不是用户照片。"""
    if not os.path.isdir(p):
        return False
    names = set(os.listdir(p)) & {'index.html', 'photos.json', 'thumbs', 'trash.json'}
    return bool(names)


def main():
    cfg = load_cfg()
    port = int(cfg.get('port', 8081))
    root = cfg.get('root', '')

    line('=' * 56)
    line(' 撤销云相册的改动')
    line('=' * 56)
    line()
    line('将要做的事：')
    line('  1. 停止正在运行的服务（端口 %d）' % port)
    line('  2. 删掉加过的防火墙放行规则')
    line('  3. 删掉配置文件 web/album_config.json')
    line('  4. 删掉生成的相册页（%s）' % os.path.join(root, '相册'))
    line()
    line('**不会动你的照片。**05_收件箱、01_照片 里的原图一张都不删。')
    line()
    line('  输入 yes 并回车 = 执行；直接回车 = 取消（什么都不做）')
    line()
    ans = input('确认恢复？：').strip().lower()
    if ans != 'yes':
        line('已取消，什么都没做（你的照片、配置、服务都保持原样）。')
        return 1

    line()
    line('[1] 停止服务')
    killed = stop_service(port)
    if killed:
        line('  已停止：' + '、'.join(killed))
    else:
        line('  没有在跑的服务（或已经手动关了）')

    line('[2] 删除防火墙规则')
    del_rule(port)

    line('[3] 删除配置')
    if os.path.exists(CFG):
        os.remove(CFG)
        line('  已删除 %s' % CFG)
    else:
        line('  没有配置文件，跳过')

    line('[4] 删除生成的相册页')
    if root:
        gen = os.path.join(root, '相册')
        if is_gen_dir(gen):
            shutil.rmtree(gen, ignore_errors=True)
            line('  已删除 %s' % gen)
        else:
            line('  %s 不存在或不像生成目录，跳过' % gen)

    line()
    line('完成。你的照片都在 %s，没有被动过。' % (root or '原目录'))
    line('如果还想彻底清掉空目录，可以手动删掉这几个空的：')
    line('  05_收件箱 / 01_照片 / 06_回收站（里面还有东西就别删）')
    try:
        input('按回车退出…')
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
