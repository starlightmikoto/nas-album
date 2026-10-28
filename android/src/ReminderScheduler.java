package com.selfhost.album;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

/** 每周一次「清理照片」提醒的闹钟管理 */
public class ReminderScheduler {

    public static final String ACTION_REMIND = "com.selfhost.album.REMIND";
    private static final int REQ = 1001;
    private static final long WEEK = 7L * 24 * 60 * 60 * 1000L;

    public static void schedule(Context ctx) {
        try {
            AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
            if (am == null) return;
            Intent i = new Intent(ctx, ReminderReceiver.class);
            i.setAction(ACTION_REMIND);
            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= 23) flags |= PendingIntent.FLAG_IMMUTABLE;
            PendingIntent pi = PendingIntent.getBroadcast(ctx, REQ, i, flags);
            am.setInexactRepeating(AlarmManager.RTC_WAKEUP,
                    System.currentTimeMillis() + WEEK, WEEK, pi);
        } catch (Exception ignored) {
        }
    }
}
