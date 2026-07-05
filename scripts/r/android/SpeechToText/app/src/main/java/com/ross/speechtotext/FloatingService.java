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
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.provider.Settings;
import androidx.preference.PreferenceManager;
import android.content.res.Configuration;

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
    static void startIfReady(Context context) {
        String key = PreferenceManager.getDefaultSharedPreferences(context)
                .getString(MainActivity.KEY_OPENAI_API_KEY, "");
        if (Settings.canDrawOverlays(context) && !key.isEmpty()) {
            context.startForegroundService(new Intent(context, FloatingService.class));
        }
    }

    private WindowManager windowManager;
    private FloatingActionButton floatingView;
    private WindowManager.LayoutParams params;

    private FloatingActionButton cancelView;
    private WindowManager.LayoutParams cancelParams;
    private WaveformView waveformView;
    private WindowManager.LayoutParams waveformParams;
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
    private Process rootShell;
    private DataOutputStream rootStdin;
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

        floatingView = createFab(R.drawable.ic_graphic_eq);
        floatingView.setHapticFeedbackEnabled(true);

        params = createOverlayLayoutParams(layoutType, flags);

        cancelView = createFab(R.drawable.ic_close);
        cancelView.setVisibility(View.GONE);
        cancelView.setOnClickListener(v -> {
            v.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP);
            cancelDictation();
        });

        cancelParams = createOverlayLayoutParams(layoutType, flags);

        float density = getResources().getDisplayMetrics().density;
        waveformView = new WaveformView(themedContext);
        waveformView.setVisibility(View.GONE);
        waveformParams = createOverlayLayoutParams(layoutType, flags);
        waveformParams.width = (int) (72 * density);
        waveformParams.height = (int) (40 * density);

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
                            windowManager.updateViewLayout(floatingView, params);
                            if (isDictating) {
                                updateActionButtonPositions();
                            }
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

        floatingView.setOnClickListener(v -> {
            if (isTranscribing) return;
            v.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP);
            if (!isDictating) {
                enterDictationMode();
            } else {
                finishDictation();
            }
        });

        floatingView.setOnTouchListener(dragTouchListener);
        waveformView.setOnTouchListener(dragTouchListener);
        cancelView.setOnTouchListener(dragTouchListener);

        windowManager.addView(floatingView, params);
        windowManager.addView(cancelView, cancelParams);
        windowManager.addView(waveformView, waveformParams);
        updatePositionFromPrefs();
    }

    private FloatingActionButton createFab(int iconRes) {
        FloatingActionButton fab = new FloatingActionButton(themedContext);
        fab.setImageResource(iconRes);
        fab.setSize(FloatingActionButton.SIZE_MINI);
        fab.setUseCompatPadding(true);
        return fab;
    }

    private WindowManager.LayoutParams createOverlayLayoutParams(int layoutType, int flags) {
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT, layoutType, flags, PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.LEFT;
        return lp;
    }

    private void enterDictationMode() {
        isDictating = true;
        floatingView.setImageResource(R.drawable.ic_check);
        waveformView.clear();
        waveformView.setVisibility(View.VISIBLE);
        updateActionButtonPositions();
        cancelView.setVisibility(View.VISIBLE);
        startRecording();
        mainHandler.post(amplitudePollRunnable);
    }

    private void cancelDictation() {
        stopRecording();
        deleteAudioFile();
        exitDictationMode();
    }

    private void finishDictation() {
        stopRecording();
        exitDictationMode();
        if (audioFile == null || !audioFile.exists() || audioFile.length() == 0) {
            resetFabToDefault();
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
                SharedPreferences prefs = PreferenceManager.getDefaultSharedPreferences(FloatingService.this);
                boolean useRoot = prefs.getBoolean("enable_root", true);
                boolean typed = typeViaAccessibility(text)
                        || (useRoot && typeViaInputCommand(text));
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

    private boolean typeViaInputCommand(String text) {
        try {
            if (rootShell == null || !rootShell.isAlive()) {
                rootShell = Runtime.getRuntime().exec("su");
                rootStdin = new DataOutputStream(rootShell.getOutputStream());
            }
            String escaped = text.replace("%", "%%").replace(" ", "%s");
            rootStdin.writeBytes("input text '" + escaped.replace("'", "'\\''") + "'\n");
            rootStdin.flush();
            return true;
        } catch (Exception e) {
            rootShell = null;
            rootStdin = null;
            return false;
        }
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

    private void updateActionButtonPositions() {
        int screenWidth = windowManager.getCurrentWindowMetrics().getBounds().width();
        int fabW = floatingView.getWidth();
        int fabH = floatingView.getHeight();
        int waveW = waveformParams.width;
        int waveH = waveformParams.height;
        boolean onLeft = params.x + fabW / 2 < screenWidth / 2;

        if (onLeft) {
            waveformParams.x = params.x + fabW;
            cancelParams.x = params.x + fabW + waveW;
        } else {
            waveformParams.x = params.x - waveW;
            cancelParams.x = params.x - waveW - fabW;
        }

        waveformParams.y = params.y + (fabH - waveH) / 2;
        if (waveformView.getVisibility() == View.VISIBLE) {
            windowManager.updateViewLayout(waveformView, waveformParams);
        }

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
        if (rootShell != null) rootShell.destroy();
        mainHandler.removeCallbacks(amplitudePollRunnable);
        if (waveformView != null) windowManager.removeView(waveformView);
        if (floatingView != null) windowManager.removeView(floatingView);
        if (cancelView != null) windowManager.removeView(cancelView);
    }
}
