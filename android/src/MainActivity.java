package com.selfhost.album;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.ClipData;
import android.content.ComponentName;
import android.content.ContentUris;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.database.ContentObserver;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.provider.Settings;
import android.util.Base64;
import android.view.KeyEvent;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.HttpAuthHandler;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLDecoder;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class MainActivity extends Activity {

    /** 当前版本，每次打包新 APK 时递增 */
    private static final int VERSION_CODE = 35;
    private static final String VERSION_NAME = "1.34";

    // 服务器地址 / 账号 / 密码：首次启动让用户填，存在本机（不再写死在代码里）
    private static String BASE = "";
    private static String HOME = "";
    private static String VERSION_URL = "";
    private static String USER = "";
    private static String PASS = "";

    private WebView web;
    private long downloadId = -1;
    private BroadcastReceiver dlReceiver;
    private volatile boolean viewerOpen = false;
    private long pausedAt = 0;

    // ---- 远程诊断：把关键日志/崩溃堆栈写到 NAS，出问题不用连电脑看 logcat ----
    private final StringBuilder recentLog = new StringBuilder();
    private Thread.UncaughtExceptionHandler defaultCrashHandler;
    private boolean upStartedThisSession = false;
    private android.view.View fallbackView;

    private void log(String s) {
        try {
            recentLog.append(new java.text.SimpleDateFormat("MM-dd HH:mm:ss")
                            .format(new java.util.Date()))
                    .append(' ').append(s).append('\n');
            if (recentLog.length() > 8000) recentLog.delete(0, recentLog.length() - 8000);
        } catch (Exception ignored) {
        }
    }

    /** 把日志同步写到 NAS（阻塞，最多 8 秒），崩溃时也能拿到 */
    private void flushLogBlocking() {
        HttpURLConnection c = null;
        try {
            byte[] body = recentLog.toString().getBytes("UTF-8");
            c = (HttpURLConnection) new URL(BASE + "/03_%E5%85%B1%E4%BA%AB/_app_log.txt").openConnection();
            c.setRequestMethod("PUT");
            c.setConnectTimeout(4000);
            c.setReadTimeout(4000);
            c.setDoOutput(true);
            c.setFixedLengthStreamingMode(body.length);
            c.setRequestProperty("Authorization", "Basic " + basicAuth());
            c.setRequestProperty("Content-Type", "text/plain; charset=utf-8");
            OutputStream out = c.getOutputStream();
            out.write(body);
            out.close();
            c.getResponseCode();
        } catch (Exception ignored) {
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private void flushLogAsync() {
        final String body = recentLog.toString();
        new Thread(new Runnable() {
            public void run() {
                HttpURLConnection c = null;
                try {
                    byte[] b = body.getBytes("UTF-8");
                    c = (HttpURLConnection) new URL(BASE + "/03_%E5%85%B1%E4%BA%AB/_app_log.txt").openConnection();
                    c.setRequestMethod("PUT");
                    c.setConnectTimeout(5000);
                    c.setReadTimeout(5000);
                    c.setDoOutput(true);
                    c.setFixedLengthStreamingMode(b.length);
                    c.setRequestProperty("Authorization", "Basic " + basicAuth());
                    c.setRequestProperty("Content-Type", "text/plain; charset=utf-8");
                    OutputStream out = c.getOutputStream();
                    out.write(b);
                    out.close();
                    c.getResponseCode();
                } catch (Exception ignored) {
                } finally {
                    if (c != null) c.disconnect();
                }
            }
        }).start();
    }

    private void installCrashHandler() {
        defaultCrashHandler = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler(new Thread.UncaughtExceptionHandler() {
            public void uncaughtException(Thread t, Throwable e) {
                try {
                    log("FATAL@" + t.getName() + " " + android.util.Log.getStackTraceString(e));
                    flushLogBlocking();
                    getSharedPreferences("up", MODE_PRIVATE).edit()
                            .putBoolean("crashed", true)
                            .putString("crash", android.util.Log.getStackTraceString(e))
                            .apply();
                } catch (Throwable ignored) {
                }
                if (defaultCrashHandler != null) defaultCrashHandler.uncaughtException(t, e);
                else System.exit(1);
            }
        });
    }

    /** 网页打不开时给个能点的界面，别留黑屏 */
    private void showFallback(String why) {
        try {
            if (fallbackView != null) return;
            android.widget.LinearLayout box = new android.widget.LinearLayout(this);
            box.setOrientation(android.widget.LinearLayout.VERTICAL);
            box.setGravity(android.view.Gravity.CENTER);
            box.setBackgroundColor(Color.parseColor("#0f0f10"));
            android.widget.TextView tv = new android.widget.TextView(this);
            tv.setText("连不上 NAS\n\n" + why + "\n\n检查手机网络，或等 NAS 开机后重试");
            tv.setTextColor(Color.parseColor("#c9c9cf"));
            tv.setTextSize(14);
            tv.setGravity(android.view.Gravity.CENTER);
            tv.setPadding(40, 40, 40, 30);
            android.widget.Button btn = new android.widget.Button(this);
            btn.setText("重试");
            btn.setOnClickListener(new android.view.View.OnClickListener() {
                public void onClick(android.view.View v) {
                    try {
                        if (web != null) web.loadUrl(HOME);
                    } catch (Exception ignored) {
                    }
                }
            });
            android.widget.Button btn2 = new android.widget.Button(this);
            btn2.setText("修改服务器地址");
            btn2.setOnClickListener(new android.view.View.OnClickListener() {
                public void onClick(android.view.View v) {
                    showSetupDialog(false);
                }
            });
            box.addView(tv);
            box.addView(btn);
            box.addView(btn2);
            setContentView(box);
            fallbackView = box;
            log("fallback shown: " + why);
        } catch (Exception ignored) {
        }
    }

    private void hideFallback() {
        if (fallbackView == null) return;
        fallbackView = null;
        try {
            setContentView(web);
        } catch (Exception ignored) {
        }
    }

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        if (!loadConfig()) {           // 还没配置过：先让用户填服务器和账号
            installCrashHandler();
            showSetupDialog(true);
            return;
        }
        installCrashHandler();
        registerBackCallback();
        try {
            log("boot " + VERSION_NAME + " sdk=" + Build.VERSION.SDK_INT
                    + " perm=" + hasPerms());
            flushLogAsync();
        } catch (Throwable ignored) {
        }
        try {
            stopService(new Intent(this, KeepAliveService.class));   // 清掉上次残留的僵尸通知
        } catch (Throwable ignored) {
        }
        requestWindowFeature(Window.FEATURE_NO_TITLE);

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#0f0f10"));
        web.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setMediaPlaybackRequiresUserGesture(false);

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onJsAlert(WebView view, String url, String message,
                                     final android.webkit.JsResult result) {
                try {
                    new AlertDialog.Builder(MainActivity.this).setMessage(message)
                            .setPositiveButton("确定", new android.content.DialogInterface.OnClickListener() {
                                public void onClick(android.content.DialogInterface d, int w) {
                                    result.confirm();
                                }
                            })
                            .setOnCancelListener(new android.content.DialogInterface.OnCancelListener() {
                                public void onCancel(android.content.DialogInterface d) {
                                    result.cancel();
                                }
                            }).show();
                } catch (Throwable t) {
                    result.confirm();
                }
                return true;
            }

            @Override
            public boolean onJsConfirm(WebView view, String url, String message,
                                       final android.webkit.JsResult result) {
                try {
                    new AlertDialog.Builder(MainActivity.this).setMessage(message)
                            .setPositiveButton("确定", new android.content.DialogInterface.OnClickListener() {
                                public void onClick(android.content.DialogInterface d, int w) {
                                    result.confirm();
                                }
                            })
                            .setNegativeButton("取消", new android.content.DialogInterface.OnClickListener() {
                                public void onClick(android.content.DialogInterface d, int w) {
                                    result.cancel();
                                }
                            })
                            .setOnCancelListener(new android.content.DialogInterface.OnCancelListener() {
                                public void onCancel(android.content.DialogInterface d) {
                                    result.cancel();
                                }
                            }).show();
                } catch (Throwable t) {
                    result.cancel();
                }
                return true;
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                // 新文档加载（含重载）后 DOM 里的查看器已经不存在，
                // 必须清掉旧标记，否则返回键会一直走“关大图”分支，把返回吞掉。
                viewerOpen = false;
            }

            @Override
            public void onReceivedHttpAuthRequest(WebView view, HttpAuthHandler handler,
                                                  String host, String realm) {
                handler.proceed(USER, PASS);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                hideFallback();
            }

            @Override
            public void onReceivedError(WebView view, android.webkit.WebResourceRequest req,
                                        android.webkit.WebResourceError err) {
                try {
                    if (req != null && req.isForMainFrame()) {
                        showFallback(err == null ? "" : String.valueOf(err.getDescription()));
                    }
                } catch (Exception ignored) {
                }
            }

            @Override
            public void onReceivedError(WebView view, int code, String desc, String url) {
                showFallback(desc + " (" + code + ")");
            }

            @Override
            public boolean onRenderProcessGone(WebView view,
                                               android.webkit.RenderProcessGoneDetail detail) {
                // 网页渲染进程崩了（黑屏的常见原因）：记日志并重建界面，别留黑屏
                try {
                    log("RENDER_GONE crash=" + (detail != null && detail.didCrash()));
                    flushLogAsync();
                } catch (Exception ignored) {
                }
                try {
                    recreate();
                } catch (Exception ignored) {
                }
                return true;
            }
        });
        web.addJavascriptInterface(new Bridge(), "Android");

        setContentView(web);
        web.setVerticalScrollBarEnabled(false);    // WebView 自带的滚动条关掉，只留页面自绘那条（可拖动）
        web.setHorizontalScrollBarEnabled(false);
        web.loadUrl(HOME + "?t=" + System.currentTimeMillis());   // 带时间戳，强制拿最新 HTML（CSS 内嵌，缓存会让改动看不到）

        startMediaObserver();
        registerDownloadReceiver();
        checkUpdate();
        setupReminder();
    }

    // ---------------- 前端调用的原生能力 ----------------

    public class Bridge {

        /** 网页里点「服务器设置」时重新弹出配置窗 */
        @JavascriptInterface
        public void openSetup() {
            runOnUiThread(new Runnable() {
                public void run() { showSetupDialog(false); }
            });
        }

        /** 前端同步「大图查看器是否打开」状态 */
        @JavascriptInterface
        public void setViewer(boolean open) {
            viewerOpen = open;
        }

        /** 保存到手机相册 */
        @JavascriptInterface
        public void save(final String url) {
            fetchAndSave(abs(url), false);
        }

        /** 下载后用系统图片编辑器打开 */
        @JavascriptInterface
        public void edit(final String url) {
            fetchAndSave(abs(url), true);
        }

        /** 从 NAS 删除 */
        @JavascriptInterface
        public void remove(final String url) {
            new Thread(new Runnable() {
                public void run() {
                    final int code = httpDelete(abs(url));
                    final boolean ok = code >= 200 && code < 300;
                    runOnUiThread(new Runnable() {
                        public void run() {
                            if (ok) {
                                toast("已从 NAS 删除");
                                web.evaluateJavascript(
                                        "window.__onDeleted&&window.__onDeleted()", null);
                            } else {
                                toast("删除失败（" + code + "）");
                            }
                        }
                    });
                }
            }).start();
        }

        /** 批量删除 */
        @JavascriptInterface
        public void removeMany(final String json) {
            bulk(json, null);
        }

        /** 批量移动到目标相册目录 */
        @JavascriptInterface
        public void moveMany(final String json, final String destDir) {
            bulk(json, destDir);
        }

        /** 批量下载到手机相册 */
        @JavascriptInterface
        public void saveMany(final String json) {
            new Thread(new Runnable() {
                public void run() {
                    int ok = 0, fail = 0;
                    try {
                        JSONArray arr = new JSONArray(json);
                        for (int i = 0; i < arr.length(); i++) {
                            String u = abs(arr.getString(i));
                            try {
                                byte[] data = httpGet(u);
                                if (data == null || data.length == 0) { fail++; continue; }
                                String name = fileName(u);
                                boolean isVid = name.toLowerCase()
                                        .matches(".*\\.(mp4|mov|3gp|mkv|avi)$");
                                Uri uri = saveToGallery(name, data, isVid);
                                if (uri != null) ok++; else fail++;
                            } catch (Exception e) {
                                fail++;
                            }
                        }
                    } catch (Exception ignored) {
                    }
                    final int o = ok, f = fail;
                    runOnUiThread(new Runnable() {
                        public void run() {
                            toast("已下载 " + o + " 项到相册「我的相册」"
                                    + (f > 0 ? "，失败 " + f + " 项" : ""));
                        }
                    });
                }
            }).start();
        }

        /** 发送：下载到手机相册后调起系统分享面板（单张/多张都用这一个入口） */
        @JavascriptInterface
        public void shareMany(final String json) {
            new Thread(new Runnable() {
                public void run() {
                    final ArrayList<Uri> uris = new ArrayList<Uri>();
                    boolean hasImage = false, hasVideo = false;
                    try {
                        JSONArray arr = new JSONArray(json);
                        if (arr.length() > 0) toast("正在准备发送 " + arr.length() + " 项…");
                        for (int i = 0; i < arr.length(); i++) {
                            String u = abs(arr.getString(i));
                            try {
                                byte[] data = httpGet(u);
                                if (data == null || data.length == 0) continue;
                                String name = fileName(u);
                                boolean isVid = name.toLowerCase()
                                        .matches(".*\\.(mp4|mov|3gp|mkv|avi)$");
                                Uri uri = saveToGallery(name, data, isVid);
                                if (uri != null) {
                                    uris.add(uri);
                                    if (isVid) hasVideo = true; else hasImage = true;
                                }
                            } catch (Exception ignored) {
                            }
                        }
                    } catch (Exception ignored) {
                    }
                    final boolean img = hasImage, vid = hasVideo;
                    runOnUiThread(new Runnable() {
                        public void run() {
                            if (uris.isEmpty()) {
                                toast("发送失败，请检查网络");
                                return;
                            }
                            String mime = (img && vid) ? "*/*" : (vid ? "video/*" : "image/*");
                            Intent i = new Intent(uris.size() > 1
                                    ? Intent.ACTION_SEND_MULTIPLE : Intent.ACTION_SEND);
                            i.setType(mime);
                            if (uris.size() > 1) {
                                i.putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris);
                            } else {
                                i.putExtra(Intent.EXTRA_STREAM, uris.get(0));
                            }
                            ClipData clip = ClipData.newRawUri("", uris.get(0));
                            for (int k = 1; k < uris.size(); k++) {
                                clip.addItem(new ClipData.Item(uris.get(k)));
                            }
                            i.setClipData(clip);
                            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                            try {
                                startActivity(Intent.createChooser(i, "发送到"));
                            } catch (Exception e) {
                                toast("没有可用的发送应用");
                            }
                        }
                    });
                }
            }).start();
        }

        /** 把手机相册补传到 NAS：返回 started / busy / perm */
        @JavascriptInterface
        public String startUploadAll() {
            log("js.startUploadAll");
            if (upRunning) return "busy";
            if (!hasPerms()) {
                runOnUiThread(new Runnable() {
                    public void run() {
                        try {
                            requestPermissions(neededPerms(), 2001);
                        } catch (Exception ignored) {
                        }
                    }
                });
                return "perm";
            }
            doUploadAll();
            return "started";
        }

        /** 中止本次上传 */
        @JavascriptInterface
        public void cancelUpload() {
            upCancel = true;
            log("js.cancelUpload");
        }

        /** 上传进度快照 */
        @JavascriptInterface
        public String uploadStatus() {
            return upJson();
        }

        /** 把上次崩溃日志取出来（排查用） */
        @JavascriptInterface
        public String crashInfo() {
            try {
                return getSharedPreferences("up", MODE_PRIVATE).getString("crash", "");
            } catch (Exception e) {
                return "";
            }
        }

    }

    /** 批量操作：destDir 为 null 时删除，否则移动 */
    private void bulk(final String json, final String destDir) {
        new Thread(new Runnable() {
            public void run() {
                int ok = 0, fail = 0;
                try {
                    JSONArray arr = new JSONArray(json);
                    for (int i = 0; i < arr.length(); i++) {
                        String u = abs(arr.getString(i));
                        int code;
                        if (destDir == null) {
                            code = httpDelete(u);
                        } else {
                            String name = u.substring(u.lastIndexOf('/') + 1);
                            code = httpMove(u, BASE + destDir + "/" + name);
                        }
                        if (code >= 200 && code < 300) ok++; else fail++;
                    }
                } catch (Exception ignored) {
                }
                final int o = ok, f = fail;
                runOnUiThread(new Runnable() {
                    public void run() {
                        String msg = (destDir == null ? "已删除 " : "已移动 ") + o + " 项";
                        if (f > 0) msg += "，失败 " + f + " 项";
                        web.evaluateJavascript(
                                "window.__onBulkDone&&window.__onBulkDone("
                                        + JSONObject.quote(msg) + ")", null);
                    }
                });
            }
        }).start();
    }

    /** 把相对路径补成完整 URL（前端传的是 /05_收件箱/...） */
    private String abs(String u) {
        if (u == null) return null;
        if (u.startsWith("http://") || u.startsWith("https://")) return u;
        if (u.startsWith("/")) return BASE + u;
        return BASE + "/" + u;
    }

    private void fetchAndSave(final String url, final boolean openEditor) {
        new Thread(new Runnable() {
            public void run() {
                try {
                    byte[] data = httpGet(url);
                    if (data == null || data.length == 0) {
                        toast("下载失败");
                        return;
                    }
                    String name = fileName(url);
                    boolean isVid = name.toLowerCase().matches(".*\\.(mp4|mov|3gp|mkv|avi)$");
                    final Uri uri = saveToGallery(name, data, isVid);
                    runOnUiThread(new Runnable() {
                        public void run() {
                            if (uri == null) {
                                toast("保存失败");
                            } else if (openEditor) {
                                launchEditor(uri);
                            } else {
                                toast("已保存到相册「我的相册」");
                            }
                        }
                    });
                } catch (Exception e) {
                    toast("失败：" + e.getMessage());
                }
            }
        }).start();
    }

    private Uri saveToGallery(String name, byte[] data, boolean isVideo) throws Exception {
        ContentValues cv = new ContentValues();
        cv.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
        cv.put(MediaStore.MediaColumns.MIME_TYPE, mimeOf(name));
        Uri collection;
        if (isVideo) {
            collection = MediaStore.Video.Media.EXTERNAL_CONTENT_URI;
        } else {
            collection = MediaStore.Images.Media.EXTERNAL_CONTENT_URI;
        }
        if (Build.VERSION.SDK_INT >= 29) {
            cv.put(MediaStore.MediaColumns.RELATIVE_PATH,
                    isVideo ? "Movies/我的相册" : "Pictures/我的相册");
            cv.put(MediaStore.MediaColumns.IS_PENDING, 1);
        }
        Uri uri = getContentResolver().insert(collection, cv);
        if (uri == null) return null;
        OutputStream os = getContentResolver().openOutputStream(uri);
        os.write(data);
        os.flush();
        os.close();
        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues done = new ContentValues();
            done.put(MediaStore.MediaColumns.IS_PENDING, 0);
            getContentResolver().update(uri, done, null, null);
        }
        return uri;
    }

    private void launchEditor(Uri uri) {
        String type = getContentResolver().getType(uri);
        try {
            Intent i = new Intent(Intent.ACTION_EDIT);
            i.setDataAndType(uri, type);
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            startActivity(i);
        } catch (Exception e) {
            try {
                Intent v = new Intent(Intent.ACTION_VIEW);
                v.setDataAndType(uri, type);
                v.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                startActivity(v);
                toast("没有找到编辑器，已用查看器打开");
            } catch (Exception e2) {
                toast("没有可用的图片应用");
            }
        }
    }

    private String mimeOf(String name) {
        String n = name.toLowerCase();
        if (n.endsWith(".png")) return "image/png";
        if (n.endsWith(".webp")) return "image/webp";
        if (n.endsWith(".gif")) return "image/gif";
        if (n.endsWith(".heic")) return "image/heic";
        if (n.endsWith(".mp4")) return "video/mp4";
        if (n.endsWith(".mov")) return "video/quicktime";
        if (n.endsWith(".mkv")) return "video/x-matroska";
        return "image/jpeg";
    }

    private String fileName(String url) {
        String p = url;
        int q = p.indexOf('?');
        if (q > 0) p = p.substring(0, q);
        int i = p.lastIndexOf('/');
        String n = (i >= 0) ? p.substring(i + 1) : p;
        try {
            n = URLDecoder.decode(n, "UTF-8");
        } catch (Exception ignored) {
        }
        if (n.isEmpty()) n = "photo_" + System.currentTimeMillis() + ".jpg";
        return n;
    }


    // ---------------- 媒体库监听：一拍新照片就自动补传 ----------------
    private ContentObserver mediaObserver;
    private final Handler mediaHandler = new Handler(Looper.getMainLooper());
    private Runnable mediaPending;

    private void startMediaObserver() {
        try {
            if (mediaObserver != null) return;
            mediaObserver = new ContentObserver(mediaHandler) {
                @Override
                public void onChange(boolean selfChange) {
                    if (mediaPending != null) mediaHandler.removeCallbacks(mediaPending);
                    mediaPending = new Runnable() {
                        public void run() {
                            log("media.changed");
                            try {
                                if (!upRunning && hasPerms()) doUploadAll();
                            } catch (Throwable t) {
                                log("media.upload ERR " + t);
                            }
                        }
                    };
                    mediaHandler.postDelayed(mediaPending, 4000);   // 连拍/批量保存时合并成一次
                }
            };
            getContentResolver().registerContentObserver(
                    MediaStore.Images.Media.EXTERNAL_CONTENT_URI, true, mediaObserver);
            getContentResolver().registerContentObserver(
                    MediaStore.Video.Media.EXTERNAL_CONTENT_URI, true, mediaObserver);
            log("media.observer on");
        } catch (Throwable t) {
            log("media.observer ERR " + t);
        }
    }

    // ---------------- 手机相册 → NAS 上传 ----------------

    private static final class MItem {
        long id, size, mtime;
        String name, bucket, relPath;
        boolean video;
    }

    private volatile boolean upRunning = false;
    private volatile String upState = "idle";
    private volatile int upTotal = 0, upDone = 0, upFail = 0, upSkip = 0;
    private volatile int upAdded = 0, upMedia = 0, upTomb = 0;
    private volatile boolean upCancel = false;
    private final Map<String, String> dirCache = new HashMap<String, String>();
    private volatile long upLastTick = 0;
    private final android.os.Handler uiHandler = new android.os.Handler(android.os.Looper.getMainLooper());
    private final Runnable upWatchdog = new Runnable() {
        public void run() {
            try {
                if (upRunning && System.currentTimeMillis() - upLastTick > 120000L) {
                    log("up.watchdog 卡住 120 秒，强制收尾");
                    upState = "error";
                    upRunning = false;
                    upCancel = true;
                    stopKeepAlive();
                    notifyUp();
                    flushLogAsync();
                }
            } catch (Throwable ignored) {
            }
            if (upRunning) uiHandler.postDelayed(this, 30000);
        }
    };
    private static final int UP_MAX_PER_RUN = 200;   // 单次最多传这么多，防止一次跑成马拉松
    private volatile String upCur = "";
    private long upLastNotify = 0;

    private String[] neededPerms() {
        if (Build.VERSION.SDK_INT >= 33) {
            return new String[]{"android.permission.READ_MEDIA_IMAGES",
                    "android.permission.READ_MEDIA_VIDEO"};
        }
        return new String[]{android.Manifest.permission.READ_EXTERNAL_STORAGE};
    }

    private boolean hasPerms() {
        for (String p : neededPerms()) {
            if (checkSelfPermission(p) != android.content.pm.PackageManager.PERMISSION_GRANTED)
                return false;
        }
        return true;
    }

    private String upJson() {
        return "{\"state\":\"" + upState + "\",\"running\":" + upRunning
                + ",\"total\":" + upTotal + ",\"done\":" + upDone
                + ",\"fail\":" + upFail + ",\"skip\":" + upSkip
                + ",\"added\":" + upAdded + ",\"media\":" + upMedia + ",\"cap\":" + UP_MAX_PER_RUN
                + ",\"cur\":\"" + upCur.replace("\\", "").replace("\"", "") + "\"}";
    }

    private void notifyUp() {
        long now = System.currentTimeMillis();
        upLastTick = now;
        boolean finalState = "done".equals(upState) || "error".equals(upState)
                || "idle".equals(upState);
        if (!finalState && now - upLastNotify < 350) return;
        upLastNotify = now;
        final String j = upJson();
        runOnUiThread(new Runnable() {
            public void run() {
                try {
                    if (web != null) web.evaluateJavascript(
                            "window.__upProg&&window.__upProg(" + j + ")", null);
                } catch (Exception ignored) {
                }
            }
        });
    }

    /** 把手机里所有照片/视频补传到 NAS（已存在同名文件就跳过） */
    /** 上传期间挂一个前台服务，保证切到后台也不被系统掐掉 */
    private void startKeepAlive() {
        try {
            runOnUiThread(new Runnable() {
                public void run() {
                    try {
                        Intent i = new Intent(MainActivity.this, KeepAliveService.class);
                        if (Build.VERSION.SDK_INT >= 26) startForegroundService(i);
                        else startService(i);
                        log("keepalive.start");
                    } catch (Throwable t) {
                        log("keepalive.start ERR " + t);
                    }
                }
            });
        } catch (Throwable ignored) {
        }
    }

    private void stopKeepAlive() {
        try {
            runOnUiThread(new Runnable() {
                public void run() {
                    try {
                        stopService(new Intent(MainActivity.this, KeepAliveService.class));
                        log("keepalive.stop");
                    } catch (Throwable ignored) {
                    }
                }
            });
        } catch (Throwable ignored) {
        }
    }

    /** NAS 上「已被用户删掉」的文件名清单（生成器维护，只增不减），上传时跳过 */
    private Set<String> loadTombstones() {
        Set<String> set = new HashSet<String>();
        String[] files = {"/相册/tombstones.json", "/相册/deleted_client.json"};
        for (String f : files) {
            byte[] data = httpGet(BASE + encPath(f) + "?v=" + System.currentTimeMillis());
            if (data == null) {
                continue;
            }
            try {
                JSONObject o = new JSONObject(new String(data, "UTF-8"));
                java.util.Iterator<String> it = o.keys();
                while (it.hasNext()) set.add(it.next());
            } catch (Throwable e) {
                log("tomb.parse ERR " + f);
            }
        }
        if (set.isEmpty()) log("tomb.miss");
        return set;
    }

    private void doUploadAll() {
        if (upRunning) return;
        upRunning = true;
        upCancel = false;
        upState = "listing";
        upTotal = upDone = upFail = upSkip = upAdded = upTomb = 0;
        upCur = "";
        notifyUp();
        startKeepAlive();                     // 挂前台服务，切到后台也能继续传
        upLastTick = System.currentTimeMillis();
        uiHandler.removeCallbacks(upWatchdog);
        uiHandler.postDelayed(upWatchdog, 30000);
        new Thread(new Runnable() {
            public void run() {
                try {
                    log("up.start");
                    flushLogAsync();
                    String vis = (Build.VERSION.SDK_INT >= 34)
                            ? String.valueOf(checkSelfPermission(
                                    "android.permission.READ_MEDIA_VISUAL_USER_SELECTED"))
                            : "na";
                    log("perm img=" + checkSelfPermission("android.permission.READ_MEDIA_IMAGES")
                            + " vid=" + checkSelfPermission("android.permission.READ_MEDIA_VIDEO")
                            + " vis=" + vis + " sdk=" + Build.VERSION.SDK_INT);

                    Set<String> tomb = loadTombstones();
                    log("up.tomb=" + tomb.size());
                    List<MItem> items = queryMedia();
                    upMedia = items.size();
                    upState = "checking";
                    log("up.media=" + upMedia);
                    notifyUp();

                    Map<String, List<MItem>> byDir = new LinkedHashMap<String, List<MItem>>();
                    for (MItem it : items) {
                        String dir = targetDirOf(it);
                        List<MItem> l = byDir.get(dir);
                        if (l == null) {
                            l = new ArrayList<MItem>();
                            byDir.put(dir, l);
                        }
                        l.add(it);
                    }

                    // 第一遍：只做对比，算出到底哪些需要传（进度条只报这个，不再报总数）
                    List<Object[]> pending = new ArrayList<Object[]>();
                    int skip = 0;
                    for (Map.Entry<String, List<MItem>> e : byDir.entrySet()) {
                        String dir = e.getKey();
                        ensureDir(dir);
                        Map<String, Long> exist = listRemote(dir);
                        if (exist == null) {                 // 列表没拿到：这次跳过，别把它当成「全都缺」
                            log("up.skipdir " + dir);
                            continue;
                        }
                        int need = 0;
                        log("up.dir " + dir + " total=" + e.getValue().size() + " exist=" + exist.size());
                        for (MItem it : e.getValue()) {
                            if (tomb.contains(it.name)) {           // 用户已在 NAS 里删掉，别再传回来
                                skip++;
                                upTomb++;
                                continue;
                            }
                            Long rs = exist.get(it.name);
                            if (rs != null && rs == it.size) skip++;   // 名字和大小都对得上才算已传
                            else {
                                pending.add(new Object[]{it, dir});
                                need++;
                            }
                        }
                        log("up.dir.need " + dir + " " + need);
                        flushLogAsync();
                    }
                    java.util.Collections.sort(pending, new java.util.Comparator<Object[]>() {
                        public int compare(Object[] a, Object[] b) {
                            return Long.compare(((MItem) b[0]).mtime, ((MItem) a[0]).mtime);
                        }
                    });
                    upSkip = skip;
                    upTotal = pending.size();
                    log("up.pending=" + upTotal + " skip=" + skip + " tomb=" + upTomb);
                    flushLogAsync();
                    upState = "uploading";
                    notifyUp();

                    // 第二遍：只传缺的
                    long t0 = System.currentTimeMillis();
                    int i = 0;
                    for (Object[] po : pending) {
                        if (upCancel) {
                            log("up.cancel at " + i + "/" + pending.size());
                            break;
                        }
                        if (System.currentTimeMillis() - t0 > 15 * 60 * 1000L) {
                            log("up.timeout after " + i + " 项，剩下的下次继续");
                            break;
                        }
                        if (i >= UP_MAX_PER_RUN) {
                            log("up.capped at " + UP_MAX_PER_RUN + "，剩 " + (pending.size() - i) + " 张下次传");
                            break;
                        }
                        MItem it = (MItem) po[0];
                        String dir = (String) po[1];
                        upCur = it.name;
                        if (uploadOne(it, dir)) upAdded++;
                        else upFail++;
                        upDone++;
                        i++;
                        notifyUp();
                        if (upDone % 10 == 0) flushLogAsync();
                    }

                    upState = "done";
                    log("up.done added=" + upAdded + " fail=" + upFail + " skip=" + upSkip);
                    try {
                        if (web != null && upAdded > 0) {
                            web.post(new Runnable() {
                                public void run() {
                                    web.evaluateJavascript("window.__afterUploadDone&&window.__afterUploadDone("
                                            + upAdded + ")", null);
                                }
                            });
                        }
                    } catch (Throwable ignored) {
                    }
                    try {
                        getSharedPreferences("up", MODE_PRIVATE).edit()
                                .putBoolean("crashed", false).apply();
                    } catch (Exception ignored) {
                    }
                } catch (Throwable ex) {
                    upState = "error";
                    log("up.ERR " + android.util.Log.getStackTraceString(ex));
                } finally {
                    upRunning = false;
                    upCur = "";
                    notifyUp();
                    stopKeepAlive();
                    flushLogAsync();
                }
            }
        }).start();
    }

    private List<MItem> queryMedia() {
        List<MItem> out = new ArrayList<MItem>();
        collectMedia(out, MediaStore.Images.Media.EXTERNAL_CONTENT_URI, false);
        collectMedia(out, MediaStore.Video.Media.EXTERNAL_CONTENT_URI, true);
        if (out.isEmpty()) {
            // 有些机型 Images/Video 两个 Uri 查不到，但 Files 表能查到，用 media_type 兜底
            log("media.empty, try Files provider");
            queryViaFiles(out);
        }
        if (out.isEmpty()) {
            // 还是一条都没有：探一下最小查询，把线索写进日志
            log("media.empty, retry minimal query");
            Cursor c = null;
            try {
                c = getContentResolver().query(
                        MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                        new String[]{"_ID"}, null, null, null);
                log("media.minimal rows=" + (c == null ? -1 : c.getCount())
                        + " uri=" + MediaStore.Images.Media.EXTERNAL_CONTENT_URI);
            } catch (Throwable e) {
                log("media.minimal ERR " + android.util.Log.getStackTraceString(e));
            } finally {
                if (c != null) try {
                    c.close();
                } catch (Exception ignored) {
                }
            }
        }
        return out;
    }


    /** 兜底：直接用 Files 表查所有图片/视频（某些 ROM 上 Images/Video 分区查不到） */
    private void queryViaFiles(List<MItem> out) {
        Cursor cur = null;
        try {
            Uri base = MediaStore.Files.getContentUri("external");
            String[] cols = {"_id", "_display_name", "bucket_display_name", "_size",
                    "date_modified", "media_type", "relative_path"};
            cur = getContentResolver().query(base, cols, "media_type IN (1,2)", null,
                    "date_modified DESC");
            log("files.query rows=" + (cur == null ? -1 : cur.getCount()));
            if (cur == null) return;
            while (cur.moveToNext()) {
                int mt = cur.getInt(5);
                MItem it = new MItem();
                it.id = cur.getLong(0);
                it.name = cur.getString(1);
                it.bucket = cur.getString(2);
                it.size = cur.getLong(3);
                it.mtime = cur.getLong(4);
                it.video = (mt == 2);
                try {
                    it.relPath = cur.getString(6);
                } catch (Exception ignored) {
                }
                if (it.name == null || it.name.isEmpty() || it.size <= 0) continue;
                out.add(it);
            }
            log("files.collected=" + out.size());
        } catch (Throwable e) {
            log("files.query ERR " + android.util.Log.getStackTraceString(e));
        } finally {
            if (cur != null) try {
                cur.close();
            } catch (Exception ignored) {
            }
        }
    }

    private void collectMedia(List<MItem> out, Uri base, boolean video) {
        Cursor cur = null;
        try {
            String[] cols;
            if (Build.VERSION.SDK_INT >= 29) {
                // 列名必须用媒体库的真名：DISPLAY_NAME 的真名是 _display_name（写 display_name 会报 Invalid column）
                cols = new String[]{"_id", "_display_name", "bucket_display_name", "_size",
                        "date_modified", "relative_path"};
            } else {
                cols = new String[]{"_id", "_display_name", "_size", "date_modified"};
            }
            cur = getContentResolver().query(base, cols, null, null, "date_modified DESC");
            log("media.query " + (video ? "video" : "image") + " rows="
                    + (cur == null ? -1 : cur.getCount()));
            if (cur == null) return;
            // 列下标必须写死：1.22 用 cols.length-2 计算，加了 relative_path 之后
            // 把 date_modified 当成了文件大小，导致「所有文件都判定为大小不一致」→ 全量重传
            int iSize = (Build.VERSION.SDK_INT >= 29) ? 3 : 2;
            int iMod = (Build.VERSION.SDK_INT >= 29) ? 4 : 3;
            while (cur.moveToNext()) {
                MItem it = new MItem();
                it.id = cur.getLong(0);
                it.name = cur.getString(1);
                if (Build.VERSION.SDK_INT >= 29) {
                    it.bucket = cur.getString(2);
                    it.relPath = cur.getString(5);
                }
                it.size = cur.getLong(iSize);
                it.mtime = cur.getLong(iMod);
                it.video = video;
                if (it.name == null || it.name.isEmpty() || it.size <= 0) continue;
                out.add(it);
            }
        } catch (Throwable e) {
            log("media.query ERR " + base + " " + android.util.Log.getStackTraceString(e));
        } finally {
            if (cur != null) try {
                cur.close();
            } catch (Exception ignored) {
            }
        }
    }

    /**
     * 按「相册名」定位 NAS 目录（这才是图库里的相册划分）：
     *   相机类 → 手机照片
     *   其它   → 手机相册/<相册名>，没有就找 手机相册/Gallery/owner/<相册名>，都没有才新建
     * 这样 CamScanner / Screenshots 不会被塞进「相机」，图库自建相册也不会被拍平重复。
     */
    private String targetDirOf(MItem it) {
        String b = it.bucket == null ? "" : it.bucket.trim();
        if (b.isEmpty()) b = "未分类";
        String cached = dirCache.get(b);
        if (cached != null) return cached;
        String r;
        if (b.equalsIgnoreCase("Camera") || b.equals("相机")
                || b.equalsIgnoreCase("100ANDRO")) {
            r = "/05_收件箱/手机照片";
        } else {
            String sa = "/05_收件箱/手机相册/" + b;
            String sg = "/05_收件箱/手机相册/Gallery/owner/" + b;
            int[] a = dirStat(sa);
            int[] g = dirStat(sg);
            // 选「已经有文件」的那个：只看目录是否存在会选中空目录，
            // 导致图库自建相册（Gallery/owner 下）被整批重传（2026-10-26 的坑）
            if (g[1] > a[1]) r = sg;
            else if (a[0] == 1) r = sa;
            else r = g[0] == 1 ? sg : sa;
        }
        dirCache.put(b, r);
        log("dir.map " + b + " -> " + r);
        return r;
    }

    /** 返回 {是否存在, 文件数} */
    private int[] dirStat(String path) {
        byte[] d = httpGet(BASE + encPath(path) + "/?json");
        if (d == null) return new int[]{0, 0};
        try {
            JSONObject o = new JSONObject(new String(d, "UTF-8"));
            int ex = o.optBoolean("dir_exists", false) ? 1 : 0;
            int n = 0;
            JSONArray ps = o.optJSONArray("paths");
            if (ps != null) {
                for (int i = 0; i < ps.length(); i++) {
                    if ("File".equals(ps.getJSONObject(i).optString("path_type"))) n++;
                }
            }
            return new int[]{ex, n};
        } catch (Throwable e) {
            return new int[]{0, 0};
        }
    }

    private String trimSlash(String s) {
        while (s.endsWith("/")) s = s.substring(0, s.length() - 1);
        return s;
    }

    /** 逐段 URL 编码（保留 / 分隔） */
    private String encPath(String p) {
        StringBuilder sb = new StringBuilder();
        for (String seg : p.split("/")) {
            if (seg.isEmpty()) continue;
            sb.append('/').append(Uri.encode(seg));
        }
        return sb.toString();
    }

    private Map<String, Long> listRemote(String dir) {
        Map<String, Long> map = new HashMap<String, Long>();
        byte[] data = httpGet(BASE + encPath(dir) + "/?json");
        if (data == null) {
            log("up.listfail " + dir);      // 拿不到列表就不传这个目录，避免误判「全都缺」
            return null;
        }
        try {
            JSONObject o = new JSONObject(new String(data, "UTF-8"));
            JSONArray ps = o.optJSONArray("paths");
            if (ps == null) return map;
            for (int i = 0; i < ps.length(); i++) {
                JSONObject p = ps.getJSONObject(i);
                if (!"File".equals(p.optString("path_type"))) continue;
                map.put(p.optString("name"), p.optLong("size", -1));
            }
        } catch (Exception e) {
            log("up.listparse ERR " + e);
            return null;          // 解析失败也当「未知」，这次不传这个目录
        }
        return map;
    }

    private boolean uploadOne(MItem it, String dir) {
        Uri uri = ContentUris.withAppendedId(
                it.video ? MediaStore.Video.Media.EXTERNAL_CONTENT_URI
                        : MediaStore.Images.Media.EXTERNAL_CONTENT_URI, it.id);
        String finalUrl = BASE + encPath(dir) + "/" + Uri.encode(it.name);
        try {
            // 直接写正式文件名：Android 的 HttpURLConnection 不支持 MOVE 方法
            // （之前「先传 .part 再改名」就是因为这个，全部卡在改名，白传了 81 个文件）
            int code = httpPutStream(uri, finalUrl, it.size);
            if (code >= 200 && code < 300) return true;
            log("up.fail " + it.name + " put=" + code + " size=" + it.size);
            flushLogAsync();
            return false;
        } catch (Throwable e) {
            log("up.fail " + it.name + " ex=" + e);
            flushLogAsync();
            return false;
        }
    }

    private int httpPutStream(Uri uri, String url, long size) {
        HttpURLConnection c = null;
        InputStream in = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setRequestMethod("PUT");
            c.setConnectTimeout(15000);
            c.setReadTimeout(180000);
            c.setRequestProperty("Authorization", "Basic " + basicAuth());
            c.setRequestProperty("Content-Type", "application/octet-stream");
            c.setDoOutput(true);
            // 用分块上传：不依赖 MediaStore 报的大小，避免「声明 5MB 实际 3MB」这种中断
            c.setChunkedStreamingMode(65536);
            in = getContentResolver().openInputStream(uri);
            if (in == null) return -1;
            OutputStream out = c.getOutputStream();
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            out.flush();
            out.close();
            return c.getResponseCode();
        } catch (Exception e) {
            return -1;
        } finally {
            if (in != null) try {
                in.close();
            } catch (Exception ignored) {
            }
            if (c != null) c.disconnect();
        }
    }

    private int httpMkcol(String url) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setRequestMethod("MKCOL");
            c.setConnectTimeout(8000);
            c.setReadTimeout(8000);
            c.setRequestProperty("Authorization", "Basic " + basicAuth());
            return c.getResponseCode();
        } catch (Exception e) {
            return -1;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private void ensureDir(String dir) {
        httpMkcol(BASE + encPath(dir));
    }

    // ---------------- 网络 ----------------

    private byte[] httpGet(String url) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(10000);
            c.setReadTimeout(30000);
            c.setRequestProperty("Authorization", "Basic " + basicAuth());
            if (c.getResponseCode() != 200) return null;
            InputStream in = c.getInputStream();
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            in.close();
            return bo.toByteArray();
        } catch (Exception e) {
            return null;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private int httpDelete(String url) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setRequestMethod("DELETE");
            c.setConnectTimeout(10000);
            c.setReadTimeout(20000);
            c.setRequestProperty("Authorization", "Basic " + basicAuth());
            return c.getResponseCode();
        } catch (Exception e) {
            return -1;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private int httpMove(String src, String dest) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(src).openConnection();
            c.setRequestMethod("MOVE");
            c.setConnectTimeout(10000);
            c.setReadTimeout(20000);
            c.setRequestProperty("Authorization", "Basic " + basicAuth());
            c.setRequestProperty("Destination", dest);
            c.setRequestProperty("Overwrite", "T");
            return c.getResponseCode();
        } catch (Exception e) {
            return -1;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    // ---------------- 首次配置：服务器地址 / 账号 / 密码 ----------------
    private static final String SP = "srv";

    private boolean loadConfig() {
        try {
            android.content.SharedPreferences sp = getSharedPreferences(SP, MODE_PRIVATE);
            String url = sp.getString("url", "");
            USER = sp.getString("user", "");
            PASS = sp.getString("pass", "");
            if (url == null || url.trim().isEmpty()) return false;
            BASE = url.trim().replaceAll("/+$", "");
            if (!BASE.startsWith("http")) BASE = "http://" + BASE;   // 自建默认明文 http
            HOME = BASE + "/相册/index.html";
            VERSION_URL = BASE + "/03_共享/version.json";
            return true;
        } catch (Throwable t) {
            return false;
        }
    }

    private void saveConfig(String url, String user, String pass) {
        try {
            getSharedPreferences(SP, MODE_PRIVATE).edit()
                    .putString("url", url.trim())
                    .putString("user", user)
                    .putString("pass", pass)
                    .apply();
        } catch (Throwable ignored) {
        }
        loadConfig();
    }

    /** 弹「填写服务器」窗口；first=true 时取消就退出 App */
    private void showSetupDialog(final boolean first) {
        final android.content.SharedPreferences sp = getSharedPreferences(SP, MODE_PRIVATE);
        int pad = (int) (getResources().getDisplayMetrics().density * 18);
        android.widget.LinearLayout box = new android.widget.LinearLayout(this);
        box.setOrientation(android.widget.LinearLayout.VERTICAL);
        box.setPadding(pad, pad / 2, pad, 0);

        final android.widget.EditText eUrl = new android.widget.EditText(this);
        eUrl.setHint("服务器地址，例如 192.168.1.10:8081");
        eUrl.setText(sp.getString("url", ""));
        eUrl.setInputType(android.text.InputType.TYPE_TEXT_VARIATION_URI);
        box.addView(eUrl);

        final android.widget.EditText eUser = new android.widget.EditText(this);
        eUser.setHint("账号");
        eUser.setText(sp.getString("user", ""));
        box.addView(eUser);

        final android.widget.EditText ePass = new android.widget.EditText(this);
        ePass.setHint("密码");
        ePass.setText(sp.getString("pass", ""));
        ePass.setInputType(android.text.InputType.TYPE_CLASS_TEXT
                | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        box.addView(ePass);

        android.widget.TextView tip = new android.widget.TextView(this);
        tip.setText("填电脑上「配置向导」最后显示的那一行地址和账号。\n在家用局域网地址，在外面用外网地址（如果有）。");
        tip.setTextSize(12);
        tip.setPadding(0, pad / 2, 0, 0);
        box.addView(tip);

        AlertDialog.Builder b = new AlertDialog.Builder(this)
                .setTitle("连接你的相册服务器")
                .setView(box)
                .setCancelable(!first)
                .setPositiveButton("连接", null)
                .setNeutralButton("测试连接", null);
        if (first) b.setNegativeButton("退出", new android.content.DialogInterface.OnClickListener() {
            public void onClick(android.content.DialogInterface d, int w) { finish(); }
        });
        final AlertDialog dlg = b.create();
        dlg.setOnShowListener(new android.content.DialogInterface.OnShowListener() {
            public void onShow(android.content.DialogInterface d) {
                dlg.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(
                        new android.view.View.OnClickListener() {
                            public void onClick(android.view.View v) {
                                String u = eUrl.getText().toString().trim();
                                if (u.isEmpty()) { toast("先填服务器地址"); return; }
                                testServer(u, eUser.getText().toString().trim(),
                                        ePass.getText().toString(), true);
                            }
                        });
                dlg.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(
                        new android.view.View.OnClickListener() {
                            public void onClick(android.view.View v) {
                                final String u = eUrl.getText().toString().trim();
                                final String un = eUser.getText().toString().trim();
                                final String pw = ePass.getText().toString();
                                if (u.isEmpty()) { toast("先填服务器地址"); return; }
                                dlg.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
                                testServer(u, un, pw, false);
                                dlg.dismiss();
                                saveConfig(u, un, pw);
                                recreate();
                            }
                        });
            }
        });
        dlg.show();
    }

    /** 用给定地址/账号试一次请求，成功就提示 */
    private void testServer(final String url, final String user, final String pass, final boolean toastOnly) {
        new Thread(new Runnable() {
            public void run() {
                String base = url.trim().replaceAll("/+$", "");
                if (!base.startsWith("http")) base = "http://" + base;
                HttpURLConnection c = null;
                String msg;
                try {
                    c = (HttpURLConnection) new URL(base + "/相册/photos.json").openConnection();
                    c.setConnectTimeout(6000);
                    c.setReadTimeout(6000);
                    c.setRequestProperty("Authorization", "Basic " + Base64.encodeToString(
                            (user + ":" + pass).getBytes(), Base64.NO_WRAP));
                    int code = c.getResponseCode();
                    if (code == 200) msg = "连接成功";
                    else if (code == 401) msg = "账号或密码不对（401）";
                    else msg = "服务器有响应，但状态码 " + code;
                } catch (Exception e) {
                    msg = "连不上：" + e.getClass().getSimpleName();
                } finally {
                    if (c != null) c.disconnect();
                }
                final String m = msg;
                runOnUiThread(new Runnable() {
                    public void run() { toast(m); }
                });
            }
        }).start();
    }

    private String basicAuth() {
        return Base64.encodeToString((USER + ":" + PASS).getBytes(), Base64.NO_WRAP);
    }

    private void toast(final String t) {
        runOnUiThread(new Runnable() {
            public void run() {
                Toast.makeText(MainActivity.this, t, Toast.LENGTH_SHORT).show();
            }
        });
    }

    // ---------------- 每周清理提醒 ----------------

    private void setupReminder() {
        ReminderScheduler.schedule(this);
        try {
            if (Build.VERSION.SDK_INT >= 33) {
                if (checkSelfPermission("android.permission.POST_NOTIFICATIONS")
                        != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 9);
                }
            }
        } catch (Exception ignored) {
        }
    }

    // ---------------- 更新检查 ----------------


    /** 真实安装的 versionCode；常量只是兜底，避免「更新完还提示更新」 */
    private int myVersionCode() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
        } catch (Exception e) {
            return VERSION_CODE;
        }
    }

    private void checkUpdate() {
        new Thread(new Runnable() {
            public void run() {
                try {
                    JSONObject o = fetchJson(VERSION_URL);
                    if (o == null) return;
                    final int remoteCode = o.optInt("versionCode", 0);
                    if (remoteCode <= myVersionCode()) return;

                    final String remoteName = o.optString("versionName", "");
                    final String notes = o.optString("notes", "");
                    final String url = o.optString("url", "");
                    if (url.isEmpty()) return;

                    runOnUiThread(new Runnable() {
                        public void run() {
                            showUpdateDialog(remoteName, notes, url);
                        }
                    });
                } catch (Exception ignored) {
                }
            }
        }).start();
    }

    private JSONObject fetchJson(String u) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(u).openConnection();
            c.setConnectTimeout(8000);
            c.setReadTimeout(8000);
            c.setRequestProperty("Authorization", "Basic " + basicAuth());
            c.setRequestProperty("Cache-Control", "no-cache");
            if (c.getResponseCode() != 200) return null;
            InputStream in = c.getInputStream();
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            in.close();
            return new JSONObject(new String(bo.toByteArray(), "UTF-8"));
        } catch (Exception e) {
            return null;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private void showUpdateDialog(String ver, String notes, final String url) {
        String msg = "已发布新版本 " + ver;
        if (notes != null && notes.length() > 0) msg += "\n\n更新内容：\n" + notes;
        new AlertDialog.Builder(this)
                .setTitle("发现更新")
                .setMessage(msg)
                .setPositiveButton("立即更新", (d, w) -> startDownload(url))
                .setNegativeButton("以后再说", null)
                .setCancelable(true)
                .show();
    }

    private void startDownload(String url) {
        try {
            if (Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
                Toast.makeText(this, "请先允许安装未知应用，然后再次点击更新", Toast.LENGTH_LONG).show();
                Intent i = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:" + getPackageName()));
                startActivity(i);
                return;
            }
            DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
            DownloadManager.Request r = new DownloadManager.Request(Uri.parse(url));
            r.addRequestHeader("Authorization", "Basic " + basicAuth());
            r.setTitle("我的相册更新");
            r.setDescription("正在下载安装包…");
            r.setMimeType("application/vnd.android.package-archive");
            r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            r.setDestinationInExternalFilesDir(this, null, "update.apk");
            downloadId = dm.enqueue(r);
            Toast.makeText(this, "开始下载，完成后会自动提示安装", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "下载失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void registerDownloadReceiver() {
        dlReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context ctx, Intent intent) {
                long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1);
                if (id != downloadId) return;
                DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                Uri uri = dm.getUriForDownloadedFile(id);
                if (uri == null) {
                    Toast.makeText(MainActivity.this, "下载失败，请手动重试", Toast.LENGTH_LONG).show();
                    return;
                }
                Intent i = new Intent(Intent.ACTION_VIEW);
                i.setDataAndType(uri, "application/vnd.android.package-archive");
                i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                try {
                    startActivity(i);
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, "无法启动安装器，请到下载目录手动安装",
                            Toast.LENGTH_LONG).show();
                }
            }
        };
        IntentFilter f = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(dlReceiver, f, Context.RECEIVER_EXPORTED);
        } else {
            registerReceiver(dlReceiver, f);
        }
    }

    // ---------------- 基本交互 ----------------

    /** 统一返回：大图/信息面板 → 网页历史（搜索、相册 tab、相册页）→ 退出 */
    private void handleBack() {
        log("back: viewer=" + viewerOpen + " canGoBack=" + (web != null && web.canGoBack()));
        flushLogAsync();
        if (web == null) {
            finish();
            return;
        }
        if (viewerOpen) {
            web.evaluateJavascript(
                    "if(history.state&&(history.state.v||history.state.nf)){history.back();}"
                            + "else if(window.__closeViewer){window.__closeViewer();}", null);
            return;
        }
        if (web.canGoBack()) {
            web.goBack();
            return;
        }
        finish();
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && web != null) {
            handleBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    // 手势返回（Android 10+ 全面屏手势）不走 onKeyDown，必须单独接
    @Override
    public void onBackPressed() {
        handleBack();
    }

    /** Android 13+ 的预测性返回：注册了回调才会走我们，否则系统直接 finish */
    private void registerBackCallback() {
        if (Build.VERSION.SDK_INT < 33) return;
        try {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT,
                    new android.window.OnBackInvokedCallback() {
                        @Override
                        public void onBackInvoked() {
                            log("back.invoked");
                            handleBack();
                        }
                    });
            log("back.callback registered");
        } catch (Throwable t) {
            log("back.callback ERR " + t);
        }
    }

    @Override
    protected void onPause() {
        pausedAt = System.currentTimeMillis();
        super.onPause();
    }

    /** 相册上传需要读取媒体权限 */
    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] grants) {
        super.onRequestPermissionsResult(code, perms, grants);
        if (code != 2001) return;
        boolean ok = grants.length > 0;
        for (int g : grants) {
            if (g != android.content.pm.PackageManager.PERMISSION_GRANTED) ok = false;
        }
        try {
            if (web != null) web.evaluateJavascript(
                    "window.__upPerm&&window.__upPerm(" + ok + ")", null);
        } catch (Exception ignored) {
        }
        if (ok) doUploadAll();
    }

    /** 从后台回来超过 10 分钟就重新加载，保证拿到最新页面 */
    @Override
    protected void onResume() {
        super.onResume();
        // 之前崩过：这次先不自动上传，保证相册能用（面板里仍可手动点）
        if (!upStartedThisSession && !upRunning && hasPerms()) {
            upStartedThisSession = true;
            try {
                log("resume: auto start upload");
                doUploadAll();
            } catch (Throwable t) {
                log("resume upload ERR " + t);
            }
        }
        try {
            if (web != null && pausedAt > 0
                    && System.currentTimeMillis() - pausedAt > 10 * 60 * 1000L) {
                web.reload();
            }
        } catch (Exception ignored) {
        }
    }

    @Override
    protected void onDestroy() {
        try {
            if (dlReceiver != null) unregisterReceiver(dlReceiver);
        } catch (Exception ignored) {
        }
        if (web != null) {
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
