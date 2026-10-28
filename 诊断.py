# -*- coding: utf-8 -*-
"""出问题时跑这个：把可能的原因一条条检查出来，照着提示改。

    python 诊断.py        （或双击 诊断.cmd）
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


def line(t=''):
    print(t)


def ok(t):
    print('  [OK]   ' + t)


def bad(t):
    print('  [!!]   ' + t)


def info(t):
    print('         ' + t)


def check_python():
    v = sys.version.split()[0]
    if sys.version_info >= (3, 8):
        ok('Python %s' % v)
    else:
        bad('Python %s 太旧，需要 3.8+' % v)


def check_libs():
    for m in ('PIL', 'pillow_heif'):
        try:
            __import__(m)
            ok('依赖 %s 已安装' % m)
        except Exception:
            bad('缺依赖 %s（HEIC 会失败，其他不影响）' % m)


def check_dufs():
    p = os.path.join(HERE, 'bin', 'dufs.exe' if os.name == 'nt' else 'dufs')
    if os.path.exists(p):
        ok('dufs 存在（%.1f MB）' % (os.path.getsize(p) / 1048576))
    else:
        bad('找不到 bin/dufs.exe —— 解压时可能没解全')
        info('重新完整解压一次仓库 zip')


def check_cfg():
    if not os.path.exists(CFG):
        bad('还没有配置：先双击「配置向导.cmd」')
        return None
    try:
        c = json.load(io.open(CFG, encoding='utf-8'))
    except Exception as e:
        bad('配置文件读不了：%s' % e)
        return None
    ok('配置：目录=%s  端口=%s  账号=%s' % (c.get('root'), c.get('port'), c.get('user')))
    if not os.path.isdir(c.get('root', '')):
        bad('照片目录不存在：%s' % c.get('root'))
        info('把目录建好，或重跑配置向导')
    else:
        probe = os.path.join(c['root'], '_w.tmp')
        try:
            io.open(probe, 'w', encoding='utf-8').write('1')
            os.remove(probe)
            ok('照片目录可写')
        except Exception:
            bad('照片目录写不进去（权限问题）')
    return c


def port_listening(port):
    s = socket.socket()
    try:
        s.settimeout(0.6)
        return s.connect_ex(('127.0.0.1', int(port))) == 0
    finally:
        s.close()


def check_ffmpeg(c):
    d = os.path.join(HERE, 'bin', 'ffmpeg.exe')
    if os.path.exists(d):
        ok('ffmpeg 已就绪（视频封面可用）')
        return
    if (c.get('ffmpeg') or 'ffmpeg') and os.path.exists(c.get('ffmpeg')):
        ok('ffmpeg 已就绪（自定义路径）')
        return
    bad('没有 ffmpeg：视频会没有封面图，照片不受影响')
    info('双击「下载ffmpeg.exe」自动下载，或手动放进 bin/ 目录')


def check_running(c):
    port = int(c.get('port', 8081))
    if port_listening(port):
        ok('服务正在运行（本机 %s 端口有响应）' % port)
        return True
    bad('本机 %s 端口没有响应 —— 服务没起来' % port)
    info('双击「启动相册服务.cmd」，看那个黑窗口里有没有报错')
    info('窗口不能关，关了服务就停了')
    return False


def check_firewall():
    if os.name != 'nt':
        return
    try:
        r = subprocess.run(['netsh', 'advfirewall', 'firewall', 'show', 'rule',
                            'name=all', 'dir=in', 'verbose'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=25)
        txt = (r.stdout or '')
    except Exception as e:
        bad('查防火墙失败：%s' % e)
        return
    hits = [ln for ln in txt.splitlines() if ('python' in ln.lower() or 'dufs' in ln.lower())]
    if hits:
        ok('防火墙里有和 python/dufs 相关的入站规则')
    else:
        bad('防火墙里没找到 python/dufs 的入站放行规则')
        info('这是手机连不上最常见的原因。两种办法：')
        info('  A. 控制面板 → Windows Defender 防火墙 → 允许应用通过防火墙')
        info('     → 点「更改设置」→ 勾上 Python（专用+公用）→ 确定')
        info('  B. 管理员身份运行一次下面这条（会弹 UAC）：')
        info('     netsh advfirewall firewall add rule name="相册服务" dir=in action=allow protocol=TCP localport=8081')


def local_ips():
    out = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        out.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in out and not ip.startswith('127.'):
                out.append(ip)
    except Exception:
        pass
    return out


def show_urls(c):
    port = c.get('port', 8081)
    ips = local_ips()
    line()
    line('=== 手机上该填的地址 ===')
    for i, ip in enumerate(ips):
        mark = '（首选）' if i == 0 else ''
        line('  http://%s:%s  %s' % (ip, port, mark))
    line()
    line('先用电脑上的浏览器打开上面的地址试试：')
    line('  能打开 → 说明服务没问题，是手机/防火墙/网络的事')
    line('  打不开 → 服务本身没起来，看黑窗口的报错')


def main():
    line('=' * 50)
    line(' 云相册 · 自检')
    line('=' * 50)
    check_python()
    check_libs()
    check_dufs()
    check_ffmpeg(c or {})
    c = check_cfg()
    if c:
        running = check_running(c)
        if running:
            check_firewall()
        show_urls(c)
    line()
    line('把这一整屏截图发出来，能直接定位问题。')
    try:
        input('按回车退出…')
    except Exception:
        pass


if __name__ == '__main__':
    main()
