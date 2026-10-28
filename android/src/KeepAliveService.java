package com.selfhost.album;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

/**
 * 只做一件事：上传照片时挂一个前台服务，让进程在切到后台后也能继续跑。
 * 通知会一直显示「正在上传」，传完由 MainActivity 停掉。
 */
public class KeepAliveService extends Service {

    private static final String CH = "upload";
    private static final int NID = 1001;

    @Override
    public void onCreate() {
        super.onCreate();
        try {
            Notification.Builder b;
            if (Build.VERSION.SDK_INT >= 26) {
                NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
                if (nm != null && nm.getNotificationChannel(CH) == null) {
                    NotificationChannel c = new NotificationChannel(CH, "照片上传",
                            NotificationManager.IMPORTANCE_LOW);
                    c.setShowBadge(false);
                    c.setSound(null, null);
                    nm.createNotificationChannel(c);
                }
                b = new Notification.Builder(this, CH);
            } else {
                b = new Notification.Builder(this);
            }
            b.setContentTitle("正在把手机照片传到 NAS")
                    .setContentText("传完会自动消失，可以切到别的应用")
                    .setSmallIcon(android.R.drawable.stat_sys_upload)
                    .setOngoing(true);
            startForeground(NID, b.build());
        } catch (Throwable ignored) {
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_NOT_STICKY;   // 不要被系统重启成「僵尸通知」
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
