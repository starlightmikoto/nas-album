# -*- coding: utf-8 -*-
"""看这台电脑能用哪种「外网访问」，并给出手机上该填的地址。

    python 外网.py     （或双击 外网访问.cmd）
"""
import io
import json
import os
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


def cfg():
    try:
        return json.load(io.open(CFG, encoding='utf-8'))
    except Exception:
        return {}


def public_ipv6():
    """本机的公网 IPv6（240e/2408/2409/2400 开头这些）。没有就返回 None。"""
    try:
        out = subprocess.run(['ipconfig'], capture_output=True, text=True,
                             encoding='utf-8', errors='replace', timeout=15).stdout
    except Exception:
        return None
    best = None
    for ln in out.splitlines():
        s = ln.strip()
        for kw in ('IPv6', 'IPv6 地址', 'IPv6 Address'):
            if kw in s:
                cand = s.split(':', 1)[-1].strip() if ':' in s else ''
                if '%' in cand:
                    cand = cand.split('%')[0]
                if len(cand) >= 6 and cand[0:4] in ('240e', '2408', '2409', '2400',
                                                    '2001', '2401', '2402'):
                    return cand
                if len(cand) >= 6 and cand[0:2] in ('24', '20'):
                    best = best or cand
    return best


def tailscale_ip():
    try:
        out = subprocess.run(['ipconfig'], capture_output=True, text=True,
                             encoding='utf-8', errors='replace', timeout=15).stdout
    except Exception:
        return None
    for ln in out.splitlines():
        s = ln.strip()
        if 'IPv4' in s and ':' in s:
            ip = s.split(':', 1)[1].strip()
            if ip.startswith('100.') and 64 <= int(ip.split('.')[1] or 0) <= 127:
                return ip
    return None


def line(t=''):
    print(t)


def main():
    c = cfg()
    port = c.get('port', 8081)
    line('=' * 56)
    line(' 云相册 · 外网访问检查')
    line('=' * 56)

    v6 = public_ipv6()
    ts = tailscale_ip()

    line('这台电脑的情况：')
    line('  公网 IPv6：%s' % (v6 if v6 else '没有（或不支持）'))
    line('  Tailscale：%s' % (ts if ts else '没装'))
    line()

    line('─' * 56)
    line(' 能用哪种：')
    line()

    if v6:
        line('  ① IPv6 直连（免费，不用装任何东西）')
        line('     手机地址：http://[%s]:%s' % (v6, port))
        line('     前提：手机所在网络也要有 IPv6（多数 4G/5G 有）')
        line('     注意：这个地址会变，最好配 DDNS')
    else:
        line('  ① IPv6 直连：本机没有公网 IPv6，走不通')
    line()

    if ts:
        line('  ② Tailscale（免费，要注册账号）')
        line('     手机地址：http://%s:%s' % (ts, port))
        line('     手机装 Tailscale 并登录同一账号即可')
    else:
        line('  ② Tailscale：没检测到。装了之后这里会显示 100.x 的地址')
        line('     电脑/手机各装一次，登同一账号，5 分钟搞定，不限网络')
    line()

    line('  ③ Cloudflare Tunnel（要一个域名，最稳）')
    line('     cloudflared tunnel --url http://localhost:%s' % port)
    line('     会给你一个 https 的公网地址，手机直接填它')
    line()

    line('─' * 56)
    line(' 建议：')
    if v6:
        line('   先用 ①（最快）；地址会变、或者想稳定，就上 ③。')
    elif ts:
        line('   用 ②，最省事。')
    else:
        line('   先装 Tailscale（②），它是唯一「不管什么宽带都能用」的办法；')
        line('   有域名的话用 ③ 更正规。')
    line()
    try:
        input('按回车退出…')
    except Exception:
        pass


if __name__ == '__main__':
    main()
