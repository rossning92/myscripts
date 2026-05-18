package com.ross.speechtotext;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.Configuration;
import android.content.res.ColorStateList;
import android.graphics.PixelFormat;
import android.media.MediaRecorder;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.view.Gravity;
import android.view.HapticFeedbackConstants;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.animation.LinearInterpolator;
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
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class FloatingService extends Service {
    private WindowManager windowManager;
    private FloatingActionButton floatingView;
    private WindowManager.LayoutParams params;

    private FloatingActionButton cancelView;
    private WindowManager.LayoutParams cancelParams;
    private boolean isDictating = false;
    private boolean isTranscribing = false;
    private ObjectAnimator spinAnimator;

    private MediaRecorder recorder;
    private File audioFile;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private static final String CHANNEL_ID = "FloatingServiceChannel";
    private static final int FAB_BG_COLOR = 0xFFF7F2FA;
    private static final int FAB_ICON_COLOR = 0xFF65558F;

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
        windowManager.updateViewLayout(floatingView, params);
        if (isDictating) {
            updateActionButtonPositions();
        }
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
        createNotificationChannel();

        Notification notification = new Notification.Builder(this, CHANNEL_ID)
                .setContentTitle("Speech To Text")
                .setContentText("Service is running")
                .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                .build();
        startForeground(1, notification);

        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);

        int layoutType = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY;
        int flags = WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;

        floatingView = createFab(android.R.drawable.ic_btn_speak_now);
        floatingView.setBackgroundTintList(ColorStateList.valueOf(FAB_BG_COLOR));
        floatingView.setImageTintList(ColorStateList.valueOf(FAB_ICON_COLOR));
        floatingView.setHapticFeedbackEnabled(true);

        params = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT, layoutType, flags, PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.TOP | Gravity.LEFT;

        SharedPreferences prefs = getSharedPreferences("FloatingButtonPrefs", MODE_PRIVATE);
        String suffix = getPrefSuffix();
        params.x = prefs.getInt("x" + suffix, prefs.getInt("x", 100));
        params.y = prefs.getInt("y" + suffix, prefs.getInt("y", 100));

        cancelView = createFab(android.R.drawable.ic_menu_close_clear_cancel);
        cancelView.setBackgroundTintList(ColorStateList.valueOf(0xFFFFDAD6));
        cancelView.setImageTintList(ColorStateList.valueOf(0xFF93000A));
        cancelView.setVisibility(View.GONE);
        cancelView.setOnClickListener(v -> {
            v.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP);
            cancelDictation();
        });

        cancelParams = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT, layoutType, flags, PixelFormat.TRANSLUCENT);
        cancelParams.gravity = Gravity.TOP | Gravity.LEFT;

        floatingView.setOnTouchListener(new View.OnTouchListener() {
            private int initialX, initialY;
            private float initialTouchX, initialTouchY;
            private static final int CLICK_THRESHOLD = 10;
            private static final int LONG_PRESS_TIMEOUT = 500;
            private final Handler longPressHandler = new Handler(Looper.getMainLooper());
            private boolean isLongPressed = false;

            private final Runnable longPressRunnable = () -> {
                isLongPressed = true;
                floatingView.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
            };

            @Override
            public boolean onTouch(View v, MotionEvent event) {
                if (isTranscribing) return true;
                switch (event.getAction()) {
                    case MotionEvent.ACTION_DOWN:
                        isLongPressed = false;
                        longPressHandler.postDelayed(longPressRunnable, LONG_PRESS_TIMEOUT);
                        v.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP);
                        initialX = params.x;
                        initialY = params.y;
                        initialTouchX = event.getRawX();
                        initialTouchY = event.getRawY();
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        float dX = Math.abs(event.getRawX() - initialTouchX);
                        float dY = Math.abs(event.getRawY() - initialTouchY);
                        if (dX > CLICK_THRESHOLD || dY > CLICK_THRESHOLD) {
                            if (!isLongPressed) {
                                longPressHandler.removeCallbacks(longPressRunnable);
                            }
                            params.x = initialX + (int) (event.getRawX() - initialTouchX);
                            params.y = initialY + (int) (event.getRawY() - initialTouchY);
                            windowManager.updateViewLayout(floatingView, params);
                            if (isDictating) {
                                updateActionButtonPositions();
                            }
                        }
                        return true;
                    case MotionEvent.ACTION_UP:
                        longPressHandler.removeCallbacks(longPressRunnable);
                        if (isLongPressed) {
                            savePositionToEdge();
                            return true;
                        }
                        float deltaX = Math.abs(event.getRawX() - initialTouchX);
                        float deltaY = Math.abs(event.getRawY() - initialTouchY);
                        if (deltaX < CLICK_THRESHOLD && deltaY < CLICK_THRESHOLD) {
                            if (!isDictating) {
                                enterDictationMode();
                            } else {
                                finishDictation();
                            }
                        } else {
                            savePositionToEdge();
                        }
                        return true;
                }
                return false;
            }

            private void savePositionToEdge() {
                int screenWidth = windowManager.getCurrentWindowMetrics().getBounds().width();
                int viewWidth = floatingView.getWidth();
                int targetX = (params.x + viewWidth / 2 < screenWidth / 2) ? 0 : screenWidth - viewWidth;

                ValueAnimator animator = ValueAnimator.ofInt(params.x, targetX);
                animator.setDuration(200);
                animator.addUpdateListener(animation -> {
                    params.x = (int) animation.getAnimatedValue();
                    windowManager.updateViewLayout(floatingView, params);
                    if (isDictating) {
                        updateActionButtonPositions();
                    }
                });
                animator.addListener(new AnimatorListenerAdapter() {
                    @Override
                    public void onAnimationEnd(Animator animation) {
                        savePosition();
                    }
                });
                animator.start();
            }
        });

        windowManager.addView(floatingView, params);
        windowManager.addView(cancelView, cancelParams);
    }

    private FloatingActionButton createFab(int iconRes) {
        ContextThemeWrapper ctx = new ContextThemeWrapper(this, com.google.android.material.R.style.Theme_Material3_DayNight_NoActionBar);
        FloatingActionButton fab = new FloatingActionButton(ctx);
        fab.setImageResource(iconRes);
        fab.setSize(FloatingActionButton.SIZE_MINI);
        return fab;
    }


    private void enterDictationMode() {
        isDictating = true;
        floatingView.setImageResource(android.R.drawable.ic_menu_send);
        floatingView.setBackgroundTintList(ColorStateList.valueOf(0xFFD0BCFF));
        floatingView.setImageTintList(ColorStateList.valueOf(0xFF381E72));
        updateActionButtonPositions();
        cancelView.setVisibility(View.VISIBLE);
        startRecording();
    }

    private void cancelDictation() {
        stopRecording();
        deleteAudioFile();
        exitDictationMode();
    }

    private void finishDictation() {
        stopRecording();
        isDictating = false;
        cancelView.setVisibility(View.GONE);
        if (audioFile == null || !audioFile.exists() || audioFile.length() == 0) {
            exitTranscribingMode();
            Toast.makeText(this, "No audio recorded", Toast.LENGTH_SHORT).show();
            return;
        }
        enterTranscribingMode();
        File file = audioFile;
        audioFile = null;
        executor.execute(() -> {
            try {
                String text = transcribe(file);
                mainHandler.post(() -> {
                    exitTranscribingMode();
                    typeText(text);
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    exitTranscribingMode();
                    Toast.makeText(this, "Error: " + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            } finally {
                file.delete();
            }
        });
    }

    private void enterTranscribingMode() {
        isTranscribing = true;
        floatingView.setImageResource(android.R.drawable.ic_popup_sync);
        floatingView.setBackgroundTintList(ColorStateList.valueOf(0xFFE8DEF8));
        floatingView.setImageTintList(ColorStateList.valueOf(0xFF65558F));
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
        floatingView.setImageResource(android.R.drawable.ic_btn_speak_now);
        floatingView.setBackgroundTintList(ColorStateList.valueOf(FAB_BG_COLOR));
        floatingView.setImageTintList(ColorStateList.valueOf(FAB_ICON_COLOR));
    }

    private void exitDictationMode() {
        isDictating = false;
        resetFabToDefault();
        cancelView.setVisibility(View.GONE);
    }

    private void startRecording() {
        try {
            audioFile = new File(getCacheDir(), "recording.m4a");
            recorder = new MediaRecorder();
            recorder.setAudioSource(MediaRecorder.AudioSource.MIC);
            recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            recorder.setAudioEncodingBitRate(128000);
            recorder.setAudioSamplingRate(44100);
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
    }

    private void deleteAudioFile() {
        if (audioFile != null) {
            audioFile.delete();
            audioFile = null;
        }
    }

    private String transcribe(File file) throws Exception {
        String apiKey = BuildConfig.OPENAI_API_KEY;
        if (apiKey.isEmpty()) throw new Exception("OPENAI_API_KEY not set in local.properties");

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

    private void typeText(String text) {
        TypeAccessibilityService service = TypeAccessibilityService.getInstance();
        if (service != null && service.typeText(text)) {
            return;
        }
        ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
        clipboard.setPrimaryClip(ClipData.newPlainText("transcription", text));
        Toast.makeText(this, "Copied to clipboard", Toast.LENGTH_SHORT).show();
    }

    private void updateActionButtonPositions() {
        cancelParams.x = params.x - floatingView.getWidth() - 4;
        cancelParams.y = params.y;
        windowManager.updateViewLayout(cancelView, cancelParams);
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
        if (spinAnimator != null) spinAnimator.cancel();
        stopRecording();
        deleteAudioFile();
        executor.shutdownNow();
        if (floatingView != null) windowManager.removeView(floatingView);
        if (cancelView != null) windowManager.removeView(cancelView);
    }
}
