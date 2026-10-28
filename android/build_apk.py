# -*- coding: utf-8 -*-
"""用 Python 打包 APK（不依赖 PowerShell 执行策略）。
用法： python build_apk.py [输出路径]
"""
import os
import shutil
import subprocess
import sys
import zipfile

# 定位 Android SDK / JDK：可用环境变量覆盖
BASE = r'D:/tools/android'          # 本机 SDK/JDK 所在目录
SDK = os.environ.get('ANDROID_HOME', os.path.join(BASE, 'sdk'))
JDK = os.environ.get('JAVA_HOME', os.path.join(BASE, 'jdk-17.0.20.1+1'))
BT = os.path.join(SDK, 'build-tools', '34.0.0')
BUILD = os.environ.get('BUILD_DIR', os.path.join(BASE, 'build'))
APP = os.environ.get('APP_DIR', os.path.dirname(os.path.abspath(__file__)))
AJ = os.path.join(SDK, 'platforms', 'android-34', 'android.jar')

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BUILD, 'album-release.apk')
KS = os.path.join(BUILD, 'debug.keystore')


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', **kw)
    if r.returncode != 0:
        print('FAILED:', ' '.join(cmd)[:120])
        print((r.stdout or '')[-2000:])
        print((r.stderr or '')[-3000:])
        sys.exit(1)
    return r


def main():
    for d in ('gen', 'classes', 'dex'):
        shutil.rmtree(os.path.join(BUILD, d), ignore_errors=True)
    for f in ('res.zip', 'app-unsigned.apk', 'app-with-dex.apk', 'app-aligned.apk'):
        p = os.path.join(BUILD, f)
        if os.path.exists(p):
            os.remove(p)
    for d in ('gen', 'classes', 'dex'):
        os.makedirs(os.path.join(BUILD, d), exist_ok=True)

    env = dict(os.environ)
    env['JAVA_HOME'] = JDK
    env['PATH'] = os.path.join(JDK, 'bin') + os.pathsep + env.get('PATH', '')

    print('[1/6] aapt2 compile')
    run([os.path.join(BT, 'aapt2.exe'), 'compile', '--dir', os.path.join(APP, 'res'),
         '-o', os.path.join(BUILD, 'res.zip')], env=env)

    print('[2/6] aapt2 link')
    run([os.path.join(BT, 'aapt2.exe'), 'link', '-o', os.path.join(BUILD, 'app-unsigned.apk'),
         '-I', AJ, '--manifest', os.path.join(APP, 'AndroidManifest.xml'),
         '-R', os.path.join(BUILD, 'res.zip'), '--auto-add-overlay',
         '--java', os.path.join(BUILD, 'gen'),
         '--min-sdk-version', '23', '--target-sdk-version', '34'], env=env)

    print('[3/6] javac')
    srcs = []
    for root in (os.path.join(BUILD, 'gen'), os.path.join(APP, 'src')):
        for dp, _, fs in os.walk(root):
            srcs += [os.path.join(dp, f) for f in fs if f.endswith('.java')]
    run([os.path.join(JDK, 'bin', 'javac.exe'), '--release', '8', '-encoding', 'UTF-8',
         '-classpath', AJ, '-d', os.path.join(BUILD, 'classes')] + srcs, env=env)

    print('[4/6] d8')
    cls = []
    for dp, _, fs in os.walk(os.path.join(BUILD, 'classes')):
        cls += [os.path.join(dp, f) for f in fs if f.endswith('.class')]
    run([os.path.join(BT, 'd8.bat'), '--lib', AJ, '--min-api', '23',
         '--output', os.path.join(BUILD, 'dex')] + cls, env=env)

    print('[5/6] package + align')
    shutil.copy(os.path.join(BUILD, 'app-unsigned.apk'), os.path.join(BUILD, 'app-with-dex.apk'))
    with zipfile.ZipFile(os.path.join(BUILD, 'app-with-dex.apk'), 'a', zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(BUILD, 'dex', 'classes.dex'), 'classes.dex')
    run([os.path.join(BT, 'zipalign.exe'), '-f', '4',
         os.path.join(BUILD, 'app-with-dex.apk'), os.path.join(BUILD, 'app-aligned.apk')], env=env)

    print('[6/6] sign')
    if not os.path.exists(KS):
        run([os.path.join(JDK, 'bin', 'keytool.exe'), '-genkeypair', '-keystore', KS,
             '-storepass', 'android', '-keypass', 'android', '-alias', 'androiddebugkey',
             '-dname', 'CN=Android Debug,O=Android,C=US', '-keyalg', 'RSA', '-validity', '10000'], env=env)
    run([os.path.join(BT, 'apksigner.bat'), 'sign', '--ks', KS, '--ks-pass', 'pass:android',
         '--key-pass', 'pass:android', '--out', OUT, os.path.join(BUILD, 'app-aligned.apk')], env=env)

    print('BUILD OK:', OUT, os.path.getsize(OUT), 'bytes')


if __name__ == '__main__':
    main()
