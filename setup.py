# -*- coding: utf-8 -*-
"""相册服务配置向导（跨平台，纯标准库）。

用法：
    python setup.py                 # 交互式
    python setup.py --root D:/照片 --port 8081 --user nas --pass 123456 --yes
"""
import io
import json
import os
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


def ask(prompt, default=''):
    tip = '（直接回车 = %s）' % default if default else ''
    v = input('%s%s: ' % (prompt, tip)).strip()
    return v or default


def main():
    args = sys.argv[1:]
    opt = {}
    for i, a in enumerate(args):
        if a.startswith('--') and i + 1 < len(args):
            opt[a[2:]] = args[i + 1]
    yes = '--yes' in args

    print('=' * 46)
    print(' 云相册 · 配置向导')
    print('=' * 46)

    root = opt.get('root') or ask('照片存放的文件夹', os.path.join(HERE, 'photos'))
    root = os.path.abspath(root)
    port = opt.get('port') or ask('网页端口', '8081')
    user = opt.get('user') or ask('账号', 'nas')
    pwd = opt.get('pass') or ask('密码（至少 6 位）', '')
    while len(pwd) < 6:
        print('  密码太短了，再输一次')
        pwd = ask('密码（至少 6 位）', '')

    # 建目录
    for sub in ('01_照片/_album', '05_收件箱/手机相册', '05_收件箱/手机照片', '06_回收站'):
        os.makedirs(os.path.join(root, *sub.split('/')), exist_ok=True)

    # 验证可写
    probe = os.path.join(root, '_write_test.tmp')
    try:
        io.open(probe, 'w', encoding='utf-8').write('ok')
        os.remove(probe)
    except Exception as e:
        print('目录写不进去：', e)
        return 1

    if port_busy(int(port)):
        print('  端口 %s 已被占用，换一个（比如 8082、9000）' % port)
        port = ask('网页端口', str(int(port) + 1))

    cfg = {'root': root, 'port': int(port), 'user': user, 'pass': pwd,
           'dufs': os.path.join(HERE, 'bin', 'dufs.exe' if os.name == 'nt' else 'dufs'),
           'ffmpeg': os.environ.get('FFMPEG', 'ffmpeg')}
    io.open(CFG, 'w', encoding='utf-8').write(json.dumps(cfg, ensure_ascii=False, indent=1))

    ips = local_ips()
    print()
    print('配置已保存：', CFG)
    print()
    print('─' * 46)
    print(' 手机上打开 App，填这几项：')
    print('   地址： http://%s:%s' % (ips[0], port))
    if len(ips) > 1:
        print('   （如果连不上，试试这些：%s）' % '、'.join('http://%s:%s' % (i, port) for i in ips[1:]))
    print('   账号： %s' % user)
    print('   密码： %s' % pwd)
    print('─' * 46)
    # 可选：开机自动在后台运行（窗口不会常驻）
    if os.name == 'nt' and not yes:
        try:
            a = input('要不要开机自动运行（后台，无窗口）？(y/N): ').strip().lower()
            if a == 'y':
                startup = os.path.join(os.environ.get('APPDATA', ''),
                                       r'Microsoft\Windows\Start Menu\Programs\Startup')
                fp = os.path.join(startup, '云相册自动启动.cmd')
                batch = ('@echo off\r\ncd /d "%~dp0"\r\n'
                         'start "" pythonw "%s"\r\n' % os.path.join(HERE, 'server.py'))
                io.open(fp, 'w', encoding='utf-8').write(batch)
                print('  已加入开机启动：' + fp)
        except Exception as e:
            print('  设置开机启动失败（不影响使用）：', e)
    print('然后双击「后台启动.cmd」在后台运行（窗口会自动关掉）。')
    print('地址会同时写到「地址.txt」，手机上要填的时候打开它就行。')

    # ffmpeg：只有视频封面需要它；照片缩略图用内置 Pillow，不需要
    try:
        import ffmpeg_setup
        if ffmpeg_setup.have():
            print()
            print('ffmpeg 已就绪（视频封面可用）。')
        else:
            a2 = input('要不要现在下载 ffmpeg（约 80MB，视频封面用）？(Y/n): ').strip().lower()
            if a2 in ('', 'y', 'yes'):
                ffmpeg_setup.download()
    except Exception as e:
        print('ffmpeg 步骤跳过：', e)
    print()
    print('提示：如果手机连不上，多半是 Windows 防火墙拦了：')
    print('   控制面板 → Windows Defender 防火墙 → 允许应用通过防火墙 → 勾上 Python')
    print('   （或临时关掉防火墙试一下，确认是不是它的问题）')
    return 0


def port_busy(port):
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0
    finally:
        s.close()


def local_ips():
    """列出本机可能的局域网地址（第一个最可能是对的）。"""
    import socket
    out = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        out.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        host = socket.gethostname()
        for ip in socket.gethostbyname_ex(host)[2]:
            if ip not in out and not ip.startswith('127.'):
                out.append(ip)
    except Exception:
        pass
    def rank(ip):
        if ip.startswith('192.168.'): return 0
        if ip.startswith('10.'): return 1
        if ip.startswith('169.254.'): return 9          # 自动分配地址，基本不可用
        if ip.startswith('172.'):
            try:
                return 8 if 16 <= int(ip.split('.')[1]) <= 31 else 3
            except Exception:
                return 3
        return 5
    out.sort(key=rank)
    return out or ['127.0.0.1']


def local_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


if __name__ == '__main__':
    sys.exit(main())
