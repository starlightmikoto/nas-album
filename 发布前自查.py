# -*- coding: utf-8 -*-
"""发布到 GitHub 前的傻瓜式自查：双击运行，全绿就能传。

关键词清单从「上一级目录的 检查关键词.txt」读取（那个文件不在仓库里，
所以把你的密码写进去也不会跟着上传）。
"""
import io
import os
import sys

try:
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
KEYFILE = os.path.join(PARENT, '检查关键词.txt')

TEXT_EXT = ('.py', '.md', '.java', '.xml', '.cmd', '.txt', '.json', '.html',
            '.vbs', '.cfg', '.gitignore')
SKIP_DIRS = ('bin', '__pycache__', '.git')

# 这些「不该出现在仓库文件夹里」的东西，出现了就警告别上传
MUST_NOT_EXIST = [
    'web/album_config.json',
    'web/album_config.json.bak',
    'server.log',
    '地址.txt',
    'gen_error.log',
]
MUST_NOT_DIR = ['photos', '05_收件箱', '01_照片', '06_回收站', '.git']

# 这些必须存在，缺了仓库就不完整
MUST_EXIST = [
    'README.md', 'LICENSE', 'NOTICE.md', '.gitignore',
    'docs/用户手册.md', 'docs/外网访问.md', 'docs/安装_Windows.md',
    'web/gen_album4.py', 'web/gen_guard.py', 'web/trash_page.py',
    'server.py', 'setup.py', 'tests/smoke_test.py',
    'android/src/MainActivity.java', 'android/AndroidManifest.xml',
    'bin/dufs.exe', 'apk/我的相册.apk',
]

results = []


def ok(t):
    print('  [OK] ' + t)
    results.append(True)


def bad(t):
    print('  [!!] ' + t)
    results.append(False)


def info(t):
    print('       ' + t)


def iter_files():
    for dp, dns, fns in os.walk(HERE):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            yield os.path.join(dp, fn)


def check_keywords():
    kws = []
    if os.path.exists(KEYFILE):
        for ln in io.open(KEYFILE, encoding='utf-8'):
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                kws.append(ln)
    if not kws:
        bad('没找到关键词清单：%s' % KEYFILE)
        info('在那个文件里一行一个写上：你的域名、密码、用户名、电脑路径')
        info('（这个文件本身不在仓库里，放心写）')
        return
    print('  用关键词清单检查（%d 个词，来自 检查关键词.txt）' % len(kws))
    hit_any = False
    for f in iter_files():
        ext = os.path.splitext(f)[1].lower()
        if ext not in TEXT_EXT:
            continue
        try:
            txt = io.open(f, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        rel = os.path.relpath(f, HERE)
        for kw in kws:
            if kw.lower() in txt.lower():
                bad('发现敏感词「%s」→ %s' % (kw, rel))
                hit_any = True
    if not hit_any:
        ok('全部文本文件都没有你的域名/密码/用户名')


def check_must_not():
    for rel in MUST_NOT_EXIST:
        if os.path.exists(os.path.join(HERE, rel.replace('/', os.sep))):
            bad('不要上传：%s（先删掉再上传）' % rel)
    for d in MUST_NOT_DIR:
        if os.path.isdir(os.path.join(HERE, d)):
            bad('不要上传文件夹：%s（里面可能有你的照片/数据）' % d)
    if all(not os.path.exists(os.path.join(HERE, r.replace('/', os.sep)))
           for r in MUST_NOT_EXIST) and \
       all(not os.path.isdir(os.path.join(HERE, d)) for d in MUST_NOT_DIR):
        ok('没有照片/配置/日志混进来')


def check_must_exist():
    miss = [r for r in MUST_EXIST
            if not os.path.exists(os.path.join(HERE, r.replace('/', os.sep)))]
    if miss:
        for m in miss:
            bad('缺少文件：%s' % m)
    else:
        ok('必备文件齐全（README / 许可 / 文档 / 源码 / App）')


def check_big_files():
    d = os.path.join(HERE, 'bin', 'dufs.exe')
    if os.path.exists(d):
        ok('dufs.exe 存在（%.1f MB）' % (os.path.getsize(d) / 1048576))
    else:
        bad('缺少 bin/dufs.exe（服务核心）')
    apks = [f for f in iter_files() if f.lower().endswith('.apk')]
    if apks:
        ok('手机 App 已包含：%s' % '、'.join(os.path.relpath(a, HERE) for a in apks))
    else:
        bad('缺少手机 App（apk/我的相册.apk）')
    ff = os.path.join(HERE, 'bin', 'ffmpeg.exe')
    if os.path.exists(ff):
        bad('bin/ffmpeg.exe（%.0f MB）不要放仓库：网页上传上限 25MB → 删掉它，'
            '用户双击「下载ffmpeg.exe」会自动补' % (os.path.getsize(ff) / 1048576))
    huge = []
    for f in iter_files():
        try:
            if os.path.getsize(f) > 25 * 1048576:
                huge.append('%s（%.0f MB）' % (os.path.relpath(f, HERE),
                                              os.path.getsize(f) / 1048576))
        except Exception:
            continue
    if huge:
        for h in huge:
            bad('超过 25MB，网页上传传不了它：%s → 大文件放 Releases，小文件改用命令行' % h)


def main():
    print('=' * 56)
    print(' 发布前自查')
    print('=' * 56)
    check_keywords()
    check_must_not()
    check_must_exist()
    check_big_files()
    print()
    if all(results):
        print('★ 全部通过，可以上传了。按 GitHub发布指南.md 的步骤操作。')
    else:
        print('× 有 %d 项要处理。把标 [!!] 的都解决后再上传。' %
              results.count(False))
        print('  不会弄就把这一屏截图发出来。')
    print()
    try:
        input('按回车退出…')
    except Exception:
        pass


if __name__ == '__main__':
    main()
