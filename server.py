# -*- coding: utf-8 -*-
"""启动相册服务：dufs（网页/WebDAV）+ 每分钟重建相册页。

    python server.py          # 前台运行，Ctrl+C 停止
"""
import io
import json
import os
import subprocess
import sys
import threading
import time

FROZEN = getattr(sys, 'frozen', False)          # 打成 exe 后为 True
HERE = (os.path.dirname(sys.executable) if FROZEN
        else os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(HERE, 'web', 'album_config.json')
LOG = os.path.join(HERE, 'server.log')

# 统一 UTF-8，避免控制台/日志里中文乱码
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

# 用 pythonw 后台运行时没有控制台，print 会报错 —— 统一写到 server.log
if sys.stdout is None or sys.stderr is None:
    try:
        _f = open(LOG, 'a', encoding='utf-8', buffering=1)
        sys.stdout = _f
        sys.stderr = _f
    except Exception:
        pass


def load_cfg():
    if not os.path.exists(CFG):
        print('还没有配置。先运行： python setup.py')
        sys.exit(1)
    return json.load(io.open(CFG, encoding='utf-8'))


def run_dufs(cfg):
    dufs = cfg.get('dufs') or 'dufs'
    if not os.path.exists(dufs):
        dufs = 'dufs'          # 交给 PATH
    root = cfg['root']
    cmd = [dufs, root,
           '--bind', '0.0.0.0', '--bind', '::',
           '--port', str(cfg.get('port', 8081)),
           '--auth', '%s:%s@/:rw' % (cfg['user'], cfg['pass']),
           '--allow-search', '--allow-delete', '--allow-upload',
           '--render-try-index', '--hidden', '_album,.gen.lock']
    port = cfg.get('port', 8081)
    if port_in_use(port):
        print('[服务] 端口 %s 已被占用：可能服务已经在跑，或别的程序占了它。' % port)
        print('        换个端口：重新运行 配置向导，或改 web/album_config.json 里的 port。')
        sys.exit(2)
    print('[服务] 手机/电脑打开：')
    for ip in local_ips():
        print('        http://%s:%s/           （局域网）' % (ip, port))
    v6 = public_ipv6()
    if v6:
        print('        http://[%s]:%s/   （外网，手机用流量试）' % (v6, port))
    # 把地址写成文件，双击运行的窗口一关就看不全了；记事本打开 地址.txt 就有
    try:
        txt = io.open(os.path.join(HERE, '地址.txt'), 'w', encoding='utf-8-sig')
        txt.write('手机上填这几行里的一个：\n\n')
        for ip in local_ips():
            txt.write('内网：http://%s:%s/\n' % (ip, port))
        if v6:
            txt.write('外网：http://[%s]:%s/\n' % (v6, port))
        txt.write('\n（外网那行要用手机流量试；地址变了会自动更新这个文件）\n')
        txt.close()
    except Exception:
        pass
    sys.stdout.flush()
    allow_firewall(port)
    # dufs 是控制台程序：pythonw 下若不加 CREATE_NO_WINDOW，Windows 会单独给它弹一个黑窗口
    flags = 0x08000000 if os.name == 'nt' else 0
    try:
        out = open(LOG, 'a', encoding='utf-8', buffering=1)
    except Exception:
        out = subprocess.DEVNULL
    return subprocess.Popen(cmd, creationflags=flags, stdout=out, stderr=out)


def run_gen_once():
    """跑一次生成（冻结成 exe 时走这里，不再依赖外部 python）。"""
    try:
        import gen_guard
        return gen_guard.main()
    except SystemExit as e:
        return e.code or 0
    except Exception as e:
        print('[生成] 出错：', repr(e)[:300], flush=True)
        return 1


def gen_loop():
    """每 60 秒跑一次生成器；它自己有签名判断，没变化会立刻返回。"""
    guard = os.path.join(HERE, 'web', 'gen_guard.py')
    cfg = load_cfg()
    env = dict(os.environ)
    env['ALBUM_ROOT'] = cfg['root']
    env['ALBUM_OUT'] = os.path.join(cfg['root'], '相册')
    # 冻结版是「进程内」跑生成，必须把同样的环境变量塞进本进程
    os.environ.update(env)
    while True:
        try:
            if FROZEN:
                n = run_gen_once()
                if n:
                    print('[生成] 出错，返回码 %s' % n, flush=True)
                time.sleep(60)
                continue
            r = subprocess.run([sys.executable, guard], capture_output=True, env=env,
                               text=True, encoding='utf-8', errors='replace', timeout=900)
            out = (r.stdout or '').strip().splitlines()
            if out:
                print('[生成]', out[-1], flush=True)
            if r.returncode != 0:
                print('[生成] 出错：', (r.stderr or '')[-300:], flush=True)
        except Exception as e:
            print('[生成] 异常：', e)
        time.sleep(60)


def public_ipv6():
    """本机的公网 IPv6（240e/2408/2409/2400 等开头），没有返回 None。"""
    try:
        out = subprocess.run(['ipconfig'], capture_output=True, text=True,
                             encoding='utf-8', errors='replace', timeout=15).stdout
    except Exception:
        return None
    for ln in out.splitlines():
        s = ln.strip()
        if 'IPv6' not in s:
            continue
        cand = s.split(':', 1)[-1].strip() if ':' in s else ''
        if '%' in cand:
            cand = cand.split('%')[0]
        if len(cand) >= 12 and cand[:4] in ('240e', '2408', '2409', '2400', '2401',
                                            '2402', '2001'):
            return cand
    return None


def allow_firewall(port):
    """尽力在 Windows 防火墙放行端口；没有管理员权限就静默跳过。"""
    if os.name != 'nt':
        return
    try:
        r = subprocess.run(['netsh', 'advfirewall', 'firewall', 'add', 'rule',
                            'name=相册服务 %d' % port, 'dir=in', 'action=allow',
                            'protocol=TCP', 'localport=%d' % port],
                           capture_output=True, timeout=20)
        if r.returncode == 0:
            print('[服务] 已在防火墙放行 TCP %d' % port, flush=True)
        else:
            print('[服务] 提示：没能自动放行防火墙（需要管理员）。手机连不上就先关防火墙试。', flush=True)
    except Exception:
        pass


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
    return out or ['127.0.0.1']


def port_in_use(port):
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', int(port))) == 0
    finally:
        s.close()


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


def main():
    cfg = load_cfg()
    t = threading.Thread(target=gen_loop, daemon=True)
    t.start()
    p = run_dufs(cfg)
    print('[服务] 手机上填： http://%s:%s  账号 %s'
          % (local_ip(), cfg.get('port', 8081), cfg['user']))
    try:
        p.wait()
    except KeyboardInterrupt:
        print('\n[服务] 正在停止…')
        try:
            p.terminate()
        except Exception:
            pass


if __name__ == '__main__':
    if '--gen' in sys.argv:          # 冻结版用它跑一次生成
        sys.exit(run_gen_once())
    main()
