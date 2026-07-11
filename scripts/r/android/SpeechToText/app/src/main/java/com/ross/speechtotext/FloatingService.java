package com.ross.speechtotext;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.content.Context;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ComponentName;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.provider.Settings;
import androidx.preference.PreferenceManager;
import android.content.res.Configuration;

import android.graphics.Insets;
import android.graphics.PixelFormat;
import android.media.MediaRecorder;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.view.Gravity;
import android.view.HapticFeedbackConstants;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.view.WindowMetrics;
import android.widget.LinearLayout;
import android.widget.Toast;

import androidx.appcompat.view.ContextThemeWrapper;

import com.google.android.material.floatingactionbutton.FloatingActionButton;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

public class FloatingService extends Service {
    static void startIfReady(Context context) {
        String key = PreferenceManager.getDefaultSharedPreferences(context)
                .getString(MainActivity.KEY_OPENAI_API_KEY, "");
        if (Settings.canDrawOverlays(context) && !key.isEmpty()) {
            context.startForegroundService(new Intent(context, FloatingService.class));
        }
    }

    private static FloatingService instance;

    static FloatingService getInstance() {
        return instance;
    }

    private WindowManager windowManager;
    private LinearLayout container;
    private WindowManager.LayoutParams params;

    private FloatingActionButton floatingView;
    private FloatingActionButton cancelView;
    private WaveformView waveformView;
    private boolean onLeft = true;
    private int waveW, waveH;
    private boolean isDictating = false;
    private boolean isTranscribing = false;
    private ObjectAnimator spinAnimator;

    private MediaRecorder recorder;
    private File audioFile;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private static final int AMPLITUDE_POLL_MS = 50;
    private final Runnable amplitudePollRunnable = new Runnable() {
        @Override
        public void run() {
            if (recorder != null && isDictating) {
                float normalized = (float) Math.sqrt(recorder.getMaxAmplitude() / 32767.0);
                waveformView.addAmplitude(normalized);
                mainHandler.postDelayed(this, AMPLITUDE_POLL_MS);
            }
        }
    };
    private static final String CHANNEL_ID = "FloatingServiceChannel";
    private Context themedContext;
    private Notification notification;

    private String getPrefSuffix() {
        return getResources().getConfiguration().orientation == Configuration.ORIENTATION_LANDSCAPE
                ? "_landscape"
                : "_portrait";
    }

    private void savePosition() {
        SharedPreferences prefs = getSharedPreferences("FloatingButtonPrefs", MODE_PRIVATE);
        String suffix = getPrefSuffix();
        prefs.edit()
                .putInt("x" + suffix, params.x)
                .putInt("y" + suffix, params.y)
                .apply();
    }

    private void updatePositionFromPrefs() {
        SharedPreferences prefs = getSharedPreferences("FloatingButtonPrefs", MODE_PRIVATE);
        String suffix = getPrefSuffix();
        params.x = prefs.getInt("x" + suffix, prefs.getInt("x", 100));
        params.y = prefs.getInt("y" + suffix, prefs.getInt("y", 100));
        windowManager.updateViewLayout(container, params);
        // Re-dock to the nearest edge once laid out. getWidth() and the cutout
        // insets are only valid post-layout, and the saved x must be re-snapped
        // to this orientation's usable width (insets differ per orientation).
        container.post(this::savePositionToEdge);
    }

    // Width available to the container, excluding system bars and display cutout.
    // The window is positioned relative to this inset content area, so pinning
    // the right edge must use this (not the full display width), or the WM clamps
    // the window and it no longer sits flush.
    private int usableWidth() {
        WindowMetrics metrics = windowManager.getCurrentWindowMetrics();
        Insets insets = metrics.getWindowInsets().getInsets(
                WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
        return metrics.getBounds().width() - insets.left - insets.right;
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        updatePositionFromPrefs();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        createNotificationChannel();

        notification = new Notification.Builder(this, CHANNEL_ID)
                .setContentTitle("Speech To Text")
                .setContentText("Service is running")
                .setSmallIcon(R.drawable.ic_graphic_eq)
                .build();
        startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);

        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
        themedContext = com.google.android.material.color.DynamicColors.wrapContextIfAvailable(
                new ContextThemeWrapper(this, com.google.android.material.R.style.Theme_Material3_DayNight_NoActionBar));

        int layoutType = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY;
        int flags = WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;

        float density = getResources().getDisplayMetrics().density;
        waveW = (int) (72 * density);
        waveH = (int) (40 * density);

        floatingView = createFab(R.drawable.ic_graphic_eq);
        floatingView.setHapticFeedbackEnabled(true);
        floatingView.setOnClickListener(v -> toggleDictation());

        cancelView = createFab(R.drawable.ic_close);
        cancelView.setVisibility(View.GONE);
        cancelView.setOnClickListener(v -> {
            v.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP);
            cancelDictation();
        });

        waveformView = new WaveformView(themedContext);
        waveformView.setVisibility(View.GONE);

        container = new LinearLayout(themedContext);
        container.setOrientation(LinearLayout.HORIZONTAL);
        container.setGravity(Gravity.CENTER_VERTICAL);

        View.OnTouchListener dragTouchListener = new View.OnTouchListener() {
            private int initialX, initialY;
            private float initialTouchX, initialTouchY;
            private static final int CLICK_THRESHOLD = 10;
            private boolean isDragging = false;

            @Override
            public boolean onTouch(View v, MotionEvent event) {
                switch (event.getAction()) {
                    case MotionEvent.ACTION_DOWN:
                        isDragging = false;
                        initialX = params.x;
                        initialY = params.y;
                        initialTouchX = event.getRawX();
                        initialTouchY = event.getRawY();
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        float dX = Math.abs(event.getRawX() - initialTouchX);
                        float dY = Math.abs(event.getRawY() - initialTouchY);
                        if (dX > CLICK_THRESHOLD || dY > CLICK_THRESHOLD) {
                            isDragging = true;
                            params.x = initialX + (int) (event.getRawX() - initialTouchX);
                            params.y = initialY + (int) (event.getRawY() - initialTouchY);
                            windowManager.updateViewLayout(container, params);
                        }
                        return true;
                    case MotionEvent.ACTION_UP:
                        if (isDragging) {
                            savePositionToEdge();
                        } else {
                            v.performClick();
                        }
                        return true;
                }
                return false;
            }
        };
        floatingView.setOnTouchListener(dragTouchListener);
        waveformView.setOnTouchListener(dragTouchListener);
        cancelView.setOnTouchListener(dragTouchListener);

        applyChildOrder();

        params = createOverlayLayoutParams(layoutType, flags);
        windowManager.addView(container, params);
        updatePositionFromPrefs();
    }

    private LinearLayout.LayoutParams fabLayoutParams() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    // The FAB hugs the docked edge and the action buttons grow inward, so their
    // order reverses with the edge.
    private void applyChildOrder() {
        container.removeAllViews();
        if (onLeft) {
            container.addView(floatingView, fabLayoutParams());
            container.addView(waveformView, new LinearLayout.LayoutParams(waveW, waveH));
            container.addView(cancelView, fabLayoutParams());
        } else {
            container.addView(cancelView, fabLayoutParams());
            container.addView(waveformView, new LinearLayout.LayoutParams(waveW, waveH));
            container.addView(floatingView, fabLayoutParams());
        }
    }

    private FloatingActionButton createFab(int iconRes) {
        FloatingActionButton fab = new FloatingActionButton(themedContext);
        fab.setImageResource(iconRes);
        fab.setSize(FloatingActionButton.SIZE_MINI);
        fab.setUseCompatPadding(true);
        fab.setCompatElevation(0f);
        return fab;
    }

    private WindowManager.LayoutParams createOverlayLayoutParams(int layoutType, int flags) {
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT, layoutType, flags, PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.LEFT;
        return lp;
    }

    private void toggleDictation() {
        if (isTranscribing) return;
        floatingView.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP);
        if (!isDictating) {
            enterDictationMode();
        } else {
            finishDictation();
        }
    }

    // Invoked by the accessibility service on the hardware long-press hotkey.
    void onHotkey() {
        mainHandler.post(this::toggleDictation);
    }

    boolean isDictating() {
        return isDictating;
    }

    // Enter confirms the current dictation (stop, transcribe, type).
    void onConfirmKey() {
        mainHandler.post(() -> {
            if (isDictating && !isTranscribing) finishDictation();
        });
    }

    // Escape cancels the current dictation without transcribing.
    void onCancelKey() {
        mainHandler.post(() -> {
            if (isDictating) cancelDictation();
        });
    }

    private void enterDictationMode() {
        isDictating = true;
        switchToSilentIme();
        floatingView.setImageResource(R.drawable.ic_check);
        waveformView.clear();
        waveformView.setVisibility(View.VISIBLE);
        cancelView.setVisibility(View.VISIBLE);
        repinToEdge();
        startRecording();
        mainHandler.post(amplitudePollRunnable);
    }

    private void cancelDictation() {
        stopRecording();
        deleteAudioFile();
        exitDictationMode();
        restorePreviousIme();
    }

    private void finishDictation() {
        stopRecording();
        exitDictationMode();
        if (audioFile == null || !audioFile.exists() || audioFile.length() == 0) {
            resetFabToDefault();
            restorePreviousIme();
            Toast.makeText(this, "No audio recorded", Toast.LENGTH_SHORT).show();
            return;
        }
        enterTranscribingMode();
        File file = audioFile;
        audioFile = null;
        executor.execute(() -> {
            try {
                String text = transcribe(file);
                mainHandler.post(() -> exitTranscribingMode());
                boolean typed = typeViaIme(text) || typeViaAccessibility(text);
                if (!typed) {
                    mainHandler.post(() -> {
                        ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                        clipboard.setPrimaryClip(ClipData.newPlainText("transcription", text));
                        Toast.makeText(this, "Copied to clipboard", Toast.LENGTH_SHORT).show();
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    exitTranscribingMode();
                    Toast.makeText(this, "Error: " + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            } finally {
                file.delete();
                mainHandler.post(this::restorePreviousIme);
            }
        });
    }

    private void enterTranscribingMode() {
        isTranscribing = true;
        floatingView.setImageResource(android.R.drawable.ic_popup_sync);
        spinAnimator = ObjectAnimator.ofFloat(floatingView, "alpha", 1f, 0.3f);
        spinAnimator.setDuration(600);
        spinAnimator.setRepeatCount(ValueAnimator.INFINITE);
        spinAnimator.setRepeatMode(ValueAnimator.REVERSE);
        spinAnimator.start();
    }

    private void exitTranscribingMode() {
        isTranscribing = false;
        if (spinAnimator != null) {
            spinAnimator.cancel();
            spinAnimator = null;
        }
        floatingView.setAlpha(1f);
        resetFabToDefault();
    }

    private void resetFabToDefault() {
        floatingView.setImageResource(R.drawable.ic_graphic_eq);
    }

    private void exitDictationMode() {
        mainHandler.removeCallbacks(amplitudePollRunnable);
        waveformView.setVisibility(View.GONE);
        isDictating = false;
        resetFabToDefault();
        cancelView.setVisibility(View.GONE);
        repinToEdge();
    }

    private void startRecording() {
        try {
            startForeground(1, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
                            | ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            audioFile = new File(getCacheDir(), "recording.m4a");
            recorder = new MediaRecorder();
            recorder.setAudioSource(MediaRecorder.AudioSource.MIC);
            recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            recorder.setAudioEncodingBitRate(64000);
            recorder.setAudioSamplingRate(16000);
            recorder.setAudioChannels(1);
            recorder.setOutputFile(audioFile.getAbsolutePath());
            recorder.prepare();
            recorder.start();
        } catch (Exception e) {
            Toast.makeText(this, "Recording failed: " + e.getMessage(), Toast.LENGTH_SHORT).show();
            exitDictationMode();
        }
    }

    private void stopRecording() {
        if (recorder != null) {
            try {
                recorder.stop();
            } catch (Exception ignored) {
            }
            recorder.release();
            recorder = null;
        }
        try {
            startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } catch (Exception ignored) {
        }
    }

    private void deleteAudioFile() {
        if (audioFile != null) {
            audioFile.delete();
            audioFile = null;
        }
    }

    private String transcribe(File file) throws Exception {
        String apiKey = PreferenceManager.getDefaultSharedPreferences(this)
                .getString(MainActivity.KEY_OPENAI_API_KEY, "");
        if (apiKey.isEmpty()) throw new Exception("API key not configured");

        String boundary = "----Boundary" + System.currentTimeMillis();
        URL url = new URL("https://api.openai.com/v1/audio/transcriptions");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Authorization", "Bearer " + apiKey);
        conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);

        try (DataOutputStream out = new DataOutputStream(conn.getOutputStream())) {
            writeFormField(out, boundary, "model", "gpt-4o-mini-transcribe");
            writeFormField(out, boundary, "prompt", "audio is english and simplified chinese.");

            out.writeBytes("--" + boundary + "\r\n");
            out.writeBytes("Content-Disposition: form-data; name=\"file\"; filename=\"recording.m4a\"\r\n");
            out.writeBytes("Content-Type: audio/mp4\r\n\r\n");
            try (FileInputStream fis = new FileInputStream(file)) {
                byte[] buf = new byte[4096];
                int len;
                while ((len = fis.read(buf)) != -1) out.write(buf, 0, len);
            }
            out.writeBytes("\r\n--" + boundary + "--\r\n");
        }

        int code = conn.getResponseCode();
        InputStream is = (code >= 200 && code < 300) ? conn.getInputStream() : conn.getErrorStream();
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int len;
        while ((len = is.read(buf)) != -1) baos.write(buf, 0, len);
        String body = baos.toString("UTF-8");
        conn.disconnect();

        JSONObject json = new JSONObject(body);
        if (json.has("text")) return json.getString("text");
        throw new Exception(body);
    }

    private void writeFormField(DataOutputStream out, String boundary, String name, String value) throws Exception {
        out.writeBytes("--" + boundary + "\r\n");
        out.writeBytes("Content-Disposition: form-data; name=\"" + name + "\"\r\n\r\n");
        out.writeBytes(value + "\r\n");
    }

    private boolean typeViaAccessibility(String text) {
        TypeAccessibilityService service = TypeAccessibilityService.getInstance();
        return service != null && service.typeText(text);
    }

    // Commit via our own IME when it is the active keyboard (owns the live input
    // connection). InputConnection calls must run on the main thread.
    private boolean typeViaIme(String text) {
        SilentIme ime = SilentIme.getInstance();
        if (ime == null) return false;
        boolean[] result = {false};
        CountDownLatch latch = new CountDownLatch(1);
        mainHandler.post(() -> {
            try {
                result[0] = ime.typeText(text);
            } finally {
                latch.countDown();
            }
        });
        try {
            latch.await(2, TimeUnit.SECONDS);
        } catch (InterruptedException ignored) {
        }
        return result[0];
    }

    // While dictating, swap the visible keyboard for our silent IME so no
    // keyboard bar covers the screen (e.g. over AVNC), then restore the previous
    // keyboard afterwards. Requires WRITE_SECURE_SETTINGS (granted via adb).
    private String previousImeId;

    private String getCurrentImeId() {
        return Settings.Secure.getString(getContentResolver(), Settings.Secure.DEFAULT_INPUT_METHOD);
    }

    private void switchToSilentIme() {
        ComponentName ours = new ComponentName(this, SilentIme.class);
        String current = getCurrentImeId();
        ComponentName currentCn = current != null ? ComponentName.unflattenFromString(current) : null;
        if (ours.equals(currentCn)) return;
        try {
            previousImeId = current;
            // The framework registers IMEs by their short id; writing the full
            // form is rejected as "Unknown id" and bounces back to the old IME.
            Settings.Secure.putString(getContentResolver(), Settings.Secure.DEFAULT_INPUT_METHOD, ours.flattenToShortString());
        } catch (Exception e) {
            previousImeId = null;
        }
    }

    private void restorePreviousIme() {
        if (previousImeId == null) return;
        try {
            Settings.Secure.putString(getContentResolver(), Settings.Secure.DEFAULT_INPUT_METHOD, previousImeId);
        } catch (Exception ignored) {
        }
        previousImeId = null;
    }

    private int edgeTargetX() {
        return onLeft ? 0 : usableWidth() - container.getWidth();
    }

    // Re-pin the docked edge after the container's width changes (entering or
    // leaving dictation grows/shrinks it). Posted so the new width is measured.
    private void repinToEdge() {
        container.post(() -> {
            params.x = edgeTargetX();
            windowManager.updateViewLayout(container, params);
        });
    }

    private void savePositionToEdge() {
        boolean left = params.x + container.getWidth() / 2 < usableWidth() / 2;
        if (left != onLeft) {
            onLeft = left;
            applyChildOrder();
        }
        container.post(() -> {
            ValueAnimator animator = ValueAnimator.ofInt(params.x, edgeTargetX());
            animator.setDuration(200);
            animator.addUpdateListener(animation -> {
                params.x = (int) animation.getAnimatedValue();
                windowManager.updateViewLayout(container, params);
            });
            animator.addListener(new AnimatorListenerAdapter() {
                @Override
                public void onAnimationEnd(Animator animation) {
                    savePosition();
                }
            });
            animator.start();
        });
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    private void createNotificationChannel() {
        NotificationChannel serviceChannel = new NotificationChannel(
                CHANNEL_ID,
                "Floating Service Channel",
                NotificationManager.IMPORTANCE_LOW);
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(serviceChannel);
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        instance = null;
        restorePreviousIme();
        if (spinAnimator != null) spinAnimator.cancel();
        stopRecording();
        deleteAudioFile();
        executor.shutdownNow();
        mainHandler.removeCallbacks(amplitudePollRunnable);
        if (container != null) windowManager.removeView(container);
    }
}
