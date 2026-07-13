package com.ross.launcher;

import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Context;
import android.content.pm.LauncherActivityInfo;
import android.content.pm.LauncherApps;
import android.os.Process;
import android.os.UserHandle;
import android.os.UserManager;

import java.util.ArrayList;
import java.util.List;

// Same launcher UI as MainActivity, but backed by the work profile's apps.
public class WorkActivity extends MainActivity {

    private LauncherApps launcherApps;
    private UserHandle workUser;

    @Override
    protected List<AppEntry> loadApps() {
        launcherApps = (LauncherApps) getSystemService(Context.LAUNCHER_APPS_SERVICE);
        UserManager um = (UserManager) getSystemService(Context.USER_SERVICE);

        workUser = null;
        for (UserHandle profile : um.getUserProfiles()) {
            if (!profile.equals(Process.myUserHandle())) {
                workUser = profile;
                break;
            }
        }

        List<AppEntry> result = new ArrayList<>();
        if (workUser == null) {
            return result;
        }
        for (LauncherActivityInfo info : launcherApps.getActivityList(null, workUser)) {
            result.add(new AppEntry(
                    info.getLabel(), info.getBadgedIcon(0), info.getComponentName()));
        }
        result.sort(BY_LABEL);
        return result;
    }

    @Override
    protected void launch(ComponentName component) {
        if (launcherApps == null || workUser == null) {
            return;
        }
        try {
            launcherApps.startMainActivity(component, workUser, null, null);
        } catch (ActivityNotFoundException e) {
            // App was uninstalled or disabled after the list was built.
        }
    }

    @Override
    protected void showAppInfo(ComponentName component) {
        if (launcherApps != null && workUser != null) {
            launcherApps.startAppDetailsActivity(component, workUser, null, null);
        }
    }

    @Override
    protected UserHandle appUser() {
        return workUser;
    }

    @Override
    protected void onTwoFingerSwipeUp() {
        finish();
    }

    @Override
    protected void requestDefaultHomeIfNeeded() {
        // The work launcher is never the HOME app.
    }
}
