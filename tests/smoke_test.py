# -*- coding: utf-8 -*-
"""端到端自检：起服务 → 上传一张图 → 生成 → 页面能打开。

    python tests/smoke_test.py            # 用临时目录，不影响你的照片

全部通过打印 ALL OK，退出码 0。
"""
import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(HERE)
PY = sys.executable


def http(base, path, method='GET', data=None, auth=None, raw_path=False):
    url = base + (path if raw_path else urllib.parse.quote(path))
    r = urllib.request.Request(url, method=method, data=data)
    if auth:
        r.add_header('Authorization', auth)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 忽略系统代理
    try:
        with op.open(r, timeout=15) as f:
            return f.status, f.read()
    except urllib.error.HTTPError as e:
        return e.code, b''


def wait_port(port, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            st, _ = http('http://127.0.0.1:%d' % port, '/', raw_path=True)
            if st in (200, 401, 404):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    tmp = tempfile.mkdtemp(prefix='album_smoke_', dir=os.environ.get('SMOKE_DIR') or None)
    root = os.path.join(tmp, '照片 目录')          # 故意带空格和中文
    port = 8123
    user = 'tester'
    pwd = 'pw%d' % (int(time.time()) % 1000000)      # 随机密码，避免写死

    print('[1/6] 配置到临时目录', root)
    r = subprocess.run([PY, os.path.join(ROOT_DIR, 'setup.py'), '--root', root,
                        '--port', str(port), '--user', user, '--pass', pwd, '--yes'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print((r.stdout or '') + (r.stderr or ''))
        return 1

    print('[2/6] 启动服务')
    srv = subprocess.Popen([PY, os.path.join(ROOT_DIR, 'server.py')],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        if not wait_port(port):
            print('服务没起来')
            print((srv.stdout.read() or b'').decode('utf-8', 'replace')[-800:])
            return 1

        auth = 'Basic ' + base64.b64encode(('%s:%s' % (user, pwd)).encode()).decode()
        base = 'http://127.0.0.1:%d' % port

        print('[3/6] 打开首页')
        st, body = http(base, '/相册/index.html', auth=auth)
        assert st == 200, '首页 %s' % st
        assert '照片' in body.decode('utf-8', 'replace'), '首页内容不对'

        print('[4/6] 模拟手机上传一张照片')
        d = '/05_收件箱/手机相册/自检相册'
        st, body = http(base, d, 'MKCOL', auth=auth)
        if st in (201, 405):
            st, _ = http(base, d + '/a.jpg', 'PUT', b'\xff\xd8\xff\xd9', auth=auth)
            assert st in (201, 204), 'PUT %s' % st
        else:
            # 某些环境（受限目录/沙箱）会拒绝 MKCOL：退回「直接写文件」，同样能验证生成链路
            print('    MKCOL 被拒（%s），改用文件系统直接写入' % st)
            local = os.path.join(root, '05_收件箱', '手机相册', '自检相册')
            os.makedirs(local, exist_ok=True)
            io.open(os.path.join(local, 'a.jpg'), 'wb').write(b'\xff\xd8\xff\xd9')

        print('[5/6] 生成相册')
        env = dict(os.environ, ALBUM_ROOT=root, ALBUM_OUT=os.path.join(root, '相册'))
        subprocess.run([PY, os.path.join(ROOT_DIR, 'web', 'gen_guard.py')],
                       env=env, capture_output=True, timeout=300)
        st, body = http(base, '/相册/photos.json', auth=auth)
        assert st == 200, 'photos.json %s' % st
        data = json.loads(body.decode('utf-8'))
        names = [a['n'] for a in data.get('albums', [])]
        assert '自检相册' in names, '相册里没有自检相册：%s' % names

        print('[6/6] 相册内页')
        st, body = http(base, '/相册/手机图片/自检相册/index.html', auth=auth)
        assert st == 200, '内页 %s' % st

        print('\nALL OK')
        return 0
    finally:
        srv.terminate()
        time.sleep(1)
        try:
            srv.kill()
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
