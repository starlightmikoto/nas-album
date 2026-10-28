package com.selfhost.album;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** 开机后重新安排每周提醒（闹钟在重启后会丢失） */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context ctx, Intent intent) {
        ReminderScheduler.schedule(ctx);
    }
}
