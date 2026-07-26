package com.ross.launcher;

import android.app.Activity;
import android.app.ActivityManager;
import android.app.AlertDialog;
import android.app.role.RoleManager;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.LauncherApps;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.content.pm.ShortcutInfo;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Process;
import android.os.UserHandle;
import android.provider.MediaStore;
import android.provider.Settings;
import android.provider.Telephony;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.GridLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.Iterator;
import java.util.List;

public class MainActivity extends Activity {

    protected static final Comparator<AppEntry> BY_LABEL =
            (a, b) -> a.label.toString().compareToIgnoreCase(b.label.toString());

    // Two-finger swipe up (of this many dp) opens the work-profile launcher.
    private static final int SWIPE_THRESHOLD_DP = 80;

    // Vertical room reserved under the icon for the label (text + margins).
    private static final int LABEL_RESERVE_DP = 26;

    // The system launcher icon size looks small in a sparse full-screen grid, so
    // the icon cap is scaled up by this factor for a comfortable maximum.
    private static final float ICON_SCALE = 1.5f;

    private float twoFingerStartY = -1;
    private boolean twoFingerTriggered;

    static class AppEntry {
        final CharSequence label;
        final Drawable icon;
        final ComponentName component;
        final String shortcutPackage;
        final String shortcutId;
        final UserHandle user;

        AppEntry(CharSequence label, Drawable icon, ComponentName component) {
            this.label = label;
            this.icon = icon;
            this.component = component;
            this.shortcutPackage = null;
            this.shortcutId = null;
            this.user = null;
        }

        AppEntry(CharSequence label, Drawable icon, ShortcutInfo shortcut) {
            this.label = label;
            this.icon = icon;
            this.component = null;
            this.shortcutPackage = shortcut.getPackage();
            this.shortcutId = shortcut.getId();
            this.user = shortcut.getUserHandle();
        }

        boolean isShortcut() {
            return shortcutId != null;
        }
    }

    private FrameLayout gridContainer;
    private GridLayout grid;
    private LinearLayout dock;
    private List<AppEntry> apps;
    private List<AppEntry> favorites;

    private LauncherApps launcherAppsService;
    private LauncherApps.Callback appsCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.BLACK);
        int pad = dp(4);
        root.setPadding(pad, pad, pad, pad);

        gridContainer = new FrameLayout(this);
        root.addView(gridContainer, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        grid = new GridLayout(this);
        gridContainer.addView(grid, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER));

        dock = new LinearLayout(this);
        dock.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams dockParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(84));
        dockParams.topMargin = dp(4);
        root.addView(dock, dockParams);

        setContentView(root);

        reload();
        // Re-lay out whenever the window size changes (e.g. split-screen resize),
        // not just once - cell sizes and column count are computed from the bounds.
        // Listen on root so both gridContainer and dock are already laid out (and
        // have valid heights) when populate() runs.
        root.addOnLayoutChangeListener(
                (v, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom) -> {
                    if (right - left != oldRight - oldLeft
                            || bottom - top != oldBottom - oldTop) {
                        populate();
                    }
                });

        requestDefaultHomeIfNeeded();
        registerAppsCallback();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (launcherAppsService != null && appsCallback != null) {
            launcherAppsService.unregisterCallback(appsCallback);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Refresh after becoming the default home app or accepting a pin request.
        if (grid != null) {
            reload();
        }
    }

    // The app list is a one-time snapshot taken in onCreate, so rebuild it whenever
    // a package is installed/removed/changed for the profile this launcher shows.
    private void registerAppsCallback() {
        launcherAppsService = (LauncherApps) getSystemService(Context.LAUNCHER_APPS_SERVICE);
        appsCallback = new LauncherApps.Callback() {
            @Override
            public void onPackageAdded(String packageName, UserHandle user) {
                reloadIfRelevant(user);
            }

            @Override
            public void onPackageRemoved(String packageName, UserHandle user) {
                reloadIfRelevant(user);
            }

            @Override
            public void onPackageChanged(String packageName, UserHandle user) {
                reloadIfRelevant(user);
            }

            @Override
            public void onPackagesAvailable(String[] names, UserHandle user, boolean replacing) {
                reloadIfRelevant(user);
            }

            @Override
            public void onPackagesUnavailable(String[] names, UserHandle user, boolean replacing) {
                reloadIfRelevant(user);
            }

            @Override
            public void onShortcutsChanged(
                    String packageName, List<ShortcutInfo> shortcuts, UserHandle user) {
                reloadIfRelevant(user);
            }
        };
        launcherAppsService.registerCallback(appsCallback);
    }

    private void reloadIfRelevant(UserHandle user) {
        if (user.equals(appUser())) {
            reload();
        }
    }

    private void reload() {
        apps = loadApps();
        favorites = extractFavorites(apps);
        dock.setVisibility(favorites.isEmpty() ? View.GONE : View.VISIBLE);
        populate();
    }

    @Override
    public boolean dispatchTouchEvent(MotionEvent ev) {
        switch (ev.getActionMasked()) {
            case MotionEvent.ACTION_POINTER_DOWN:
                if (ev.getPointerCount() == 2) {
                    twoFingerStartY = avgY(ev);
                    twoFingerTriggered = false;
                }
                break;
            case MotionEvent.ACTION_MOVE:
                if (ev.getPointerCount() >= 2 && twoFingerStartY >= 0 && !twoFingerTriggered
                        && twoFingerStartY - avgY(ev) > dp(SWIPE_THRESHOLD_DP)) {
                    twoFingerTriggered = true;
                    onTwoFingerSwipeUp();
                }
                break;
            case MotionEvent.ACTION_POINTER_UP:
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                twoFingerStartY = -1;
                break;
        }
        return super.dispatchTouchEvent(ev);
    }

    private static float avgY(MotionEvent ev) {
        return (ev.getY(0) + ev.getY(1)) / 2f;
    }

    protected void onTwoFingerSwipeUp() {
        startActivity(new Intent(this, WorkActivity.class));
        overridePendingTransition(0, 0);
    }

    protected void requestDefaultHomeIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            return;
        }
        RoleManager rm = getSystemService(RoleManager.class);
        if (rm != null && rm.isRoleAvailable(RoleManager.ROLE_HOME)
                && !rm.isRoleHeld(RoleManager.ROLE_HOME)) {
            // Must use startActivityForResult, plain startActivity silently skips the dialog.
            startActivityForResult(rm.createRequestRoleIntent(RoleManager.ROLE_HOME), 0);
        }
    }

    private void populate() {
        grid.removeAllViews();
        dock.removeAllViews();
        populateGrid();
        populateDock();
    }

    private void populateGrid() {
        int width = gridContainer.getWidth();
        int height = gridContainer.getHeight();
        int n = apps.size();
        if (n == 0 || width <= 0 || height <= 0) {
            return;
        }

        int cols = bestColumns(n, width, height);
        int rows = (int) Math.ceil((double) n / cols);
        grid.setColumnCount(cols);
        grid.setRowCount(rows);

        // Size the icon to the available cell, but never larger than the cap. The
        // grid wraps this content and the container centers it.
        int available = Math.min(width / cols, height / rows);
        int iconPx = iconSize(available);
        int cell = iconPx + dp(LABEL_RESERVE_DP);
        float labelSizePx = labelSize(cell);
        for (int i = 0; i < n; i++) {
            GridLayout.LayoutParams params = new GridLayout.LayoutParams(
                    GridLayout.spec(i / cols), GridLayout.spec(i % cols));
            params.width = cell;
            params.height = cell;
            grid.addView(createCell(apps.get(i), iconPx, labelSizePx), params);
        }
    }

    private void populateDock() {
        int height = dock.getHeight();
        if (height <= 0) {
            return;
        }
        int iconPx = iconSize(height);
        float labelSizePx = labelSize(height);
        for (AppEntry app : favorites) {
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                    0, ViewGroup.LayoutParams.MATCH_PARENT, 1f);
            dock.addView(createCell(app, iconPx, labelSizePx), params);
        }
    }

    private float labelSize(int cellHeightPx) {
        return clamp(cellHeightPx * 0.14f, sp(11), sp(13));
    }

    // Pull the common apps (phone, messaging, browser, camera) out of the grid list
    // so they can live in the fixed bottom dock. Order defines dock order.
    private List<AppEntry> extractFavorites(List<AppEntry> all) {
        List<AppEntry> favs = new ArrayList<>();
        for (String pkg : favoritePackages()) {
            for (Iterator<AppEntry> it = all.iterator(); it.hasNext(); ) {
                AppEntry app = it.next();
                if (!app.isShortcut() && app.component.getPackageName().equals(pkg)) {
                    favs.add(app);
                    it.remove();
                    break;
                }
            }
        }
        return favs;
    }

    private List<String> favoritePackages() {
        PackageManager pm = getPackageManager();
        List<String> pkgs = new ArrayList<>();
        addResolved(pkgs, pm, new Intent(Intent.ACTION_DIAL));
        String sms = Telephony.Sms.getDefaultSmsPackage(this);
        if (sms != null) {
            pkgs.add(sms);
        }
        addResolved(pkgs, pm, new Intent(Intent.ACTION_VIEW, Uri.parse("http://example.com"))
                .addCategory(Intent.CATEGORY_BROWSABLE));
        addResolved(pkgs, pm, new Intent(MediaStore.INTENT_ACTION_STILL_IMAGE_CAMERA));
        addResolved(pkgs, pm, new Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0")));
        return pkgs;
    }

    private void addResolved(List<String> pkgs, PackageManager pm, Intent intent) {
        ResolveInfo info = pm.resolveActivity(intent, 0);
        if (info != null && info.activityInfo != null
                && !"android".equals(info.activityInfo.packageName)
                && !pkgs.contains(info.activityInfo.packageName)) {
            pkgs.add(info.activityInfo.packageName);
        }
    }

    private View createCell(AppEntry app, int iconSizePx, float labelSizePx) {
        LinearLayout cell = new LinearLayout(this);
        cell.setOrientation(LinearLayout.VERTICAL);
        cell.setGravity(Gravity.CENTER);
        int pad = dp(2);
        cell.setPadding(pad, pad, pad, pad);
        cell.setOnClickListener(v -> launch(app));
        cell.setOnLongClickListener(v -> {
            showActions(app);
            return true;
        });

        ImageView icon = new ImageView(this);
        icon.setImageDrawable(app.icon);
        icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
        cell.addView(icon, new LinearLayout.LayoutParams(iconSizePx, iconSizePx));

        TextView label = new TextView(this);
        label.setText(app.label);
        label.setSingleLine(true);
        label.setEllipsize(TextUtils.TruncateAt.END);
        label.setGravity(Gravity.CENTER);
        label.setTextColor(Color.WHITE);
        label.setTextSize(TypedValue.COMPLEX_UNIT_PX, labelSizePx);
        LinearLayout.LayoutParams labelParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        labelParams.topMargin = dp(2);
        cell.addView(label, labelParams);

        return cell;
    }

    // Maximize square cell size so every app fits on one screen without scrolling.
    private int bestColumns(int n, int width, int height) {
        int best = 1;
        double bestCell = 0;
        for (int c = 1; c <= n; c++) {
            int r = (int) Math.ceil((double) n / c);
            double cell = Math.min((double) width / c, (double) height / r);
            if (cell > bestCell) {
                bestCell = cell;
                best = c;
            }
        }
        return best;
    }

    protected List<AppEntry> loadApps() {
        PackageManager pm = getPackageManager();
        Intent query = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);

        List<AppEntry> result = new ArrayList<>();
        for (ResolveInfo info : pm.queryIntentActivities(query, 0)) {
            if (info.activityInfo.packageName.equals(getPackageName())) {
                continue;
            }
            ComponentName component = new ComponentName(
                    info.activityInfo.packageName, info.activityInfo.name);
            result.add(new AppEntry(info.loadLabel(pm), info.loadIcon(pm), component));
        }
        result.addAll(loadPinnedShortcuts(Process.myUserHandle()));
        result.sort(BY_LABEL);
        return result;
    }

    private List<AppEntry> loadPinnedShortcuts(UserHandle user) {
        LauncherApps launcherApps =
                (LauncherApps) getSystemService(Context.LAUNCHER_APPS_SERVICE);
        List<AppEntry> result = new ArrayList<>();
        if (launcherApps == null || !launcherApps.hasShortcutHostPermission()) {
            return result;
        }

        LauncherApps.ShortcutQuery query = new LauncherApps.ShortcutQuery()
                .setQueryFlags(LauncherApps.ShortcutQuery.FLAG_MATCH_PINNED);
        List<ShortcutInfo> shortcuts;
        try {
            shortcuts = launcherApps.getShortcuts(query, user);
        } catch (IllegalStateException | SecurityException e) {
            return result;
        }
        if (shortcuts == null) {
            return result;
        }
        for (ShortcutInfo shortcut : shortcuts) {
            Drawable icon = launcherApps.getShortcutBadgedIconDrawable(shortcut, 0);
            if (icon == null) {
                try {
                    icon = getPackageManager().getApplicationIcon(shortcut.getPackage());
                } catch (PackageManager.NameNotFoundException ignored) {
                    continue;
                }
            }
            CharSequence label = shortcut.getShortLabel();
            if (label == null || label.length() == 0) {
                label = shortcut.getLongLabel();
            }
            if (label == null || label.length() == 0) {
                label = shortcut.getPackage();
            }
            result.add(new AppEntry(label, icon, shortcut));
        }
        return result;
    }

    private void showActions(AppEntry app) {
        if (app.isShortcut()) {
            new AlertDialog.Builder(this)
                    .setTitle(app.label)
                    .setItems(new CharSequence[] {"App info", "Remove shortcut"},
                            (dialog, which) -> {
                                if (which == 0) {
                                    showAppInfo(new ComponentName(
                                            app.shortcutPackage, app.shortcutPackage));
                                } else {
                                    removeShortcut(app);
                                }
                            })
                    .show();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle(app.label)
                .setItems(new CharSequence[] {"App info", "Uninstall"}, (dialog, which) -> {
                    if (which == 0) {
                        showAppInfo(app.component);
                    } else {
                        uninstall(app.component);
                    }
                })
                .show();
    }

    private void removeShortcut(AppEntry app) {
        if (launcherAppsService == null || app.user == null) {
            return;
        }
        LauncherApps.ShortcutQuery query = new LauncherApps.ShortcutQuery()
                .setPackage(app.shortcutPackage)
                .setQueryFlags(LauncherApps.ShortcutQuery.FLAG_MATCH_PINNED);
        List<ShortcutInfo> pinned = launcherAppsService.getShortcuts(query, app.user);
        List<String> remainingIds = new ArrayList<>();
        if (pinned != null) {
            for (ShortcutInfo shortcut : pinned) {
                if (!shortcut.getId().equals(app.shortcutId)) {
                    remainingIds.add(shortcut.getId());
                }
            }
        }
        launcherAppsService.pinShortcuts(app.shortcutPackage, remainingIds, app.user);
        reload();
    }

    protected void showAppInfo(ComponentName component) {
        startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.fromParts("package", component.getPackageName(), null)));
    }

    protected void uninstall(ComponentName component) {
        Intent intent = new Intent(Intent.ACTION_UNINSTALL_PACKAGE,
                Uri.fromParts("package", component.getPackageName(), null));
        intent.putExtra(Intent.EXTRA_USER, appUser());
        startActivity(intent);
    }

    protected UserHandle appUser() {
        return Process.myUserHandle();
    }

    protected void launch(ComponentName component) {
        Intent intent = new Intent(Intent.ACTION_MAIN)
                .addCategory(Intent.CATEGORY_LAUNCHER)
                .setComponent(component)
                .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
        try {
            startActivity(intent);
        } catch (ActivityNotFoundException e) {
            // App was uninstalled or disabled after the list was built.
        }
    }

    private void launch(AppEntry app) {
        if (!app.isShortcut()) {
            launch(app.component);
            return;
        }
        try {
            launcherAppsService.startShortcut(
                    app.shortcutPackage, app.shortcutId, null, null, app.user);
        } catch (ActivityNotFoundException | IllegalStateException e) {
            reload();
        }
    }

    // Icon size (px) that fills the given cell, capped so a few apps don't blow up.
    private int iconSize(int availablePx) {
        return Math.min(availablePx - dp(LABEL_RESERVE_DP), maxIconPx());
    }

    // The cap: the system launcher icon size, scaled up for a comfortable maximum.
    private int maxIconPx() {
        ActivityManager am = (ActivityManager) getSystemService(ACTIVITY_SERVICE);
        return Math.round(am.getLauncherLargeIconSize() * ICON_SCALE);
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private float sp(float value) {
        return value * getResources().getDisplayMetrics().scaledDensity;
    }

    private static float clamp(float value, float min, float max) {
        return Math.max(min, Math.min(max, value));
    }
}
