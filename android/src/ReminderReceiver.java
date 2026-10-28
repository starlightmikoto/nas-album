package com.selfhost.album;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

/** 每周触发：弹出「该清理照片了」通知 */
public class ReminderReceiver extends BroadcastReceiver {

    private static final String CHANNEL = "clean_reminder";

    @Override
    public void onReceive(Context ctx, Intent intent) {
        try {
            NotificationManager nm =
                    (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;

            if (Build.VERSION.SDK_INT >= 26) {
                NotificationChannel ch = new NotificationChannel(
                        CHANNEL, "照片清理提醒", NotificationManager.IMPORTANCE_DEFAULT);
                ch.setDescription("每周提醒整理照片");
                nm.createNotificationChannel(ch);
            }

            Intent open = new Intent(ctx, MainActivity.class);
            open.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= 23) flags |= PendingIntent.FLAG_IMMUTABLE;
            PendingIntent pi = PendingIntent.getActivity(ctx, 2001, open, flags);

            Notification.Builder b;
            if (Build.VERSION.SDK_INT >= 26) {
                b = new Notification.Builder(ctx, CHANNEL);
            } else {
                b = new Notification.Builder(ctx);
            }
            b.setSmallIcon(android.R.drawable.ic_menu_gallery)
                    .setContentTitle("该清理手机照片了")
                    .setContentText("打开相册翻一翻，把不要的删掉，给手机腾点空间")
                    .setAutoCancel(true)
                    .setContentIntent(pi);
            if (Build.VERSION.SDK_INT >= 21) {
                b.setColor(0xFF4A9EFF);
            }
            nm.notify(3001, b.build());
        } catch (Exception ignored) {
        }
    }
}
