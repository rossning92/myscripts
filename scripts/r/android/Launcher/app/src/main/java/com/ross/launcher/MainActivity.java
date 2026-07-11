package com.ross.launcher;

import android.app.Activity;
import android.app.role.RoleManager;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.MediaStore;
import android.provider.Telephony;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.GridLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

public class MainActivity extends Activity {

    private static class AppEntry {
        final CharSequence label;
        final Drawable icon;
        final ComponentName component;

        AppEntry(CharSequence label, Drawable icon, ComponentName component) {
            this.label = label;
            this.icon = icon;
            this.component = component;
        }
    }

    private GridLayout grid;
    private LinearLayout dock;
    private List<AppEntry> apps;
    private List<AppEntry> favorites;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.BLACK);
        int pad = dp(4);
        root.setPadding(pad, pad, pad, pad);

        grid = new GridLayout(this);
        root.addView(grid, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        dock = new LinearLayout(this);
        dock.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams dockParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(84));
        dockParams.topMargin = dp(4);
        root.addView(dock, dockParams);

        setContentView(root);

        apps = loadApps();
        favorites = extractFavorites(apps);
        if (favorites.isEmpty()) {
            dock.setVisibility(View.GONE);
        }
        grid.post(this::populate);

        requestDefaultHomeIfNeeded();
    }

    private void requestDefaultHomeIfNeeded() {
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
        populateGrid();
        populateDock();
    }

    private void populateGrid() {
        int width = grid.getWidth() - grid.getPaddingLeft() - grid.getPaddingRight();
        int height = grid.getHeight() - grid.getPaddingTop() - grid.getPaddingBottom();
        int n = apps.size();
        if (n == 0 || width <= 0 || height <= 0) {
            return;
        }

        int cols = bestColumns(n, width, height);
        int rows = (int) Math.ceil((double) n / cols);
        grid.setColumnCount(cols);
        grid.setRowCount(rows);

        float labelSizePx = labelSize(height / rows);
        for (int i = 0; i < n; i++) {
            GridLayout.LayoutParams params = new GridLayout.LayoutParams();
            params.width = 0;
            params.height = 0;
            params.rowSpec = GridLayout.spec(i / cols, 1f);
            params.columnSpec = GridLayout.spec(i % cols, 1f);
            grid.addView(createCell(apps.get(i), labelSizePx), params);
        }
    }

    private void populateDock() {
        int height = dock.getHeight();
        if (height <= 0) {
            return;
        }
        float labelSizePx = labelSize(height);
        for (AppEntry app : favorites) {
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                    0, ViewGroup.LayoutParams.MATCH_PARENT, 1f);
            dock.addView(createCell(app, labelSizePx), params);
        }
    }

    private float labelSize(int cellHeightPx) {
        return clamp(cellHeightPx * 0.14f, sp(8), sp(13));
    }

    // Pull the common apps (phone, messaging, browser, camera) out of the grid list
    // so they can live in the fixed bottom dock. Order defines dock order.
    private List<AppEntry> extractFavorites(List<AppEntry> all) {
        List<AppEntry> favs = new ArrayList<>();
        for (String pkg : favoritePackages()) {
            for (Iterator<AppEntry> it = all.iterator(); it.hasNext(); ) {
                AppEntry app = it.next();
                if (app.component.getPackageName().equals(pkg)) {
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

    private View createCell(AppEntry app, float labelSizePx) {
        LinearLayout cell = new LinearLayout(this);
        cell.setOrientation(LinearLayout.VERTICAL);
        cell.setGravity(Gravity.CENTER);
        int pad = dp(2);
        cell.setPadding(pad, pad, pad, pad);
        cell.setOnClickListener(v -> launch(app.component));

        ImageView icon = new ImageView(this);
        icon.setImageDrawable(app.icon);
        icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
        cell.addView(icon, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

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

    private List<AppEntry> loadApps() {
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
        result.sort((a, b) -> a.label.toString().compareToIgnoreCase(b.label.toString()));
        return result;
    }

    private void launch(ComponentName component) {
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
