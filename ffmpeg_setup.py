# -*- coding: utf-8 -*-
"""自动下载 ffmpeg 到 bin\\ffmpeg.exe（只用于视频封面，照片不需要）。"""
import io
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

FROZEN = getattr(sys, 'frozen', False)
HERE = (os.path.dirname(sys.executable) if FROZEN
        else os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(HERE, 'bin')
DST = os.path.join(BIN, 'ffmpeg.exe')

# 优先 BtbN 的 GitHub 构建（稳定、直链），失败再试 gyan.dev
URLS = [
    'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/'
    'ffmpeg-master-latest-win64-gpl.zip',
    'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
]


def have():
    return os.path.exists(DST) and os.path.getsize(DST) > 1024 * 1024


def _progress(blocks, blocksize, total):
    if total <= 0:
        return
    done = min(blocks * blocksize, total) / 1048576.0
    pct = min(100, int(done * 1048576 * 100 / total))
    bar = '#' * (pct // 5)
    sys.stdout.write('\r  下载中 %3d%%  %5.1f MB  [%-20s]' % (pct, done, bar))
    sys.stdout.flush()


# 下载源（按顺序试）：① 淘宝 npmmirror（国内，快）② gyan.dev ③ GitHub 直连
# ① 是 gzip 的单文件 ffmpeg.exe；②③ 是 zip，需要从里面挑 ffmpeg.exe
NPMMIRROR = ('https://registry.npmmirror.com/-/binary/ffmpeg-static/'
             'b6.1.1/ffmpeg-win32-x64.gz')
URLS = [
    NPMMIRROR,
    'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
    'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/'
    'ffmpeg-master-latest-win64-gpl.zip',
]


def install_from(src_path):
    """把下载到的文件装成 bin/ffmpeg.exe：自动识别 gz / zip / 裸 exe。"""
    with io.open(src_path, 'rb') as f:
        head = f.read(4)
    if head[:2] == b'MZ':                      # 已经是 exe
        shutil.copyfile(src_path, DST)
    elif head[:2] == b'\x1f\x8b':              # gzip：单文件直接解
        import gzip
        with gzip.open(src_path, 'rb') as g, io.open(DST, 'wb') as out:
            shutil.copyfileobj(g, out, 1048576)
    elif head[:2] == b'PK':                    # zip：从里面挑 ffmpeg.exe
        with zipfile.ZipFile(src_path) as z:
            target = None
            for name in z.namelist():
                base = name.replace('\\', '/').split('/')[-1].lower()
                if base == 'ffmpeg.exe':
                    target = name
                    break
            if not target:
                raise RuntimeError('压缩包里没有 ffmpeg.exe')
            with z.open(target) as src, io.open(DST, 'wb') as out:
                shutil.copyfileobj(src, out, 1048576)
    else:
        raise RuntimeError('不认识的文件格式：%r' % head)
    if not (have() and io.open(DST, 'rb').read(2) == b'MZ'):
        raise RuntimeError('安装后校验失败')


def download(force=False):
    if have() and not force:
        print('  已经有了：' + DST)
        return True
    os.makedirs(BIN, exist_ok=True)
    tmpd = tempfile.mkdtemp(prefix='ffdl_')
    ok = False
    for url in URLS:
        fpath = os.path.join(tmpd, 'ff.bin')
        try:
            print('  从 %s 下载…' % url.split('/')[2])
            req = urllib.request.Request(url, headers={'User-Agent': 'album-setup'})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=60) as r, io.open(fpath, 'wb') as f:
                total = int(r.headers.get('Content-Length') or 0)
                n = 0
                while True:
                    chunk = r.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)
                    n += len(chunk)
                    if total:
                        _progress(n // 262144, 262144, total)
            print()
            install_from(fpath)
            ok = have()
            if ok:
                print('  已安装：' + DST)
                break
        except Exception as e:
            print('\n  失败（%s）：%s' % (url.split('/')[2], str(e)[:120]))
        finally:
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
            except Exception:
                pass
    shutil.rmtree(tmpd, ignore_errors=True)
    if not ok:
        print('  自动下载没成功。可以稍后再试，或手动下载 ffmpeg.exe 放进 bin\\ 目录。')
        print('  没有 ffmpeg 也能用，只是视频没有封面图。')
    return ok


if __name__ == '__main__':
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    print('=' * 46)
    print(' 下载 ffmpeg（视频封面用，约 80MB）')
    print('=' * 46)
    download(force='--force' in sys.argv)
    try:
        input('\n按回车退出…')
    except Exception:
        pass
