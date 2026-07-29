package com.ross.speechtotext;

import android.media.MediaMetadataRetriever;
import android.media.MediaRecorder;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;

/**
 * Records compressed audio locally and submits it to the Transcriptions API.
 */
final class UploadTranscriber implements Transcriber {
    private static final int SAMPLE_RATE = 16_000;
    private static final int AMPLITUDE_POLL_MS = 50;
    private static final int API_CONNECT_TIMEOUT_MS = 10_000;
    private static final int API_READ_TIMEOUT_MS = 20_000;
    private static final String MODEL = "gpt-4o-mini-transcribe";
    private static final String PROMPT = "audio is english and simplified chinese.";

    private final String apiKey;
    private final int audioBitrate;
    private final File audioFile;
    private final Listener listener;

    private volatile boolean recording;
    private MediaRecorder recorder;
    private Thread amplitudeThread;

    UploadTranscriber(String apiKey, int audioBitrate, File audioFile, Listener listener) {
        this.apiKey = apiKey;
        this.audioBitrate = audioBitrate;
        this.audioFile = audioFile;
        this.listener = listener;
    }

    @Override
    public void start() throws Exception {
        recorder = new MediaRecorder();
        recorder.setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION);
        recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
        recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
        recorder.setAudioEncodingBitRate(audioBitrate);
        recorder.setAudioSamplingRate(SAMPLE_RATE);
        recorder.setAudioChannels(1);
        recorder.setOutputFile(audioFile.getAbsolutePath());
        recorder.prepare();
        recorder.start();

        recording = true;
        amplitudeThread = new Thread(this::pollAmplitude, "UploadAudioAmplitude");
        amplitudeThread.start();
    }

    @Override
    public void stop() {
        recording = false;
        MediaRecorder currentRecorder = recorder;
        recorder = null;
        if (currentRecorder != null) {
            try {
                currentRecorder.stop();
            } catch (Exception ignored) {
            }
            currentRecorder.release();
        }
        Thread thread = amplitudeThread;
        if (thread != null && thread != Thread.currentThread()) {
            try {
                thread.join(1_000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        amplitudeThread = null;
    }

    @Override
    public String finish() throws Exception {
        if (!audioFile.exists() || audioFile.length() == 0) {
            throw new Exception("No audio recorded");
        }
        if (apiKey.isEmpty()) throw new Exception("API key not configured");

        String boundary = "----Boundary" + System.currentTimeMillis();
        HttpURLConnection connection = (HttpURLConnection) new URL(
                "https://api.openai.com/v1/audio/transcriptions").openConnection();
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setConnectTimeout(API_CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(API_READ_TIMEOUT_MS);
        connection.setRequestProperty("Authorization", "Bearer " + apiKey);
        connection.setRequestProperty(
                "Content-Type", "multipart/form-data; boundary=" + boundary);

        try {
            try (DataOutputStream out = new DataOutputStream(connection.getOutputStream())) {
                writeFormField(out, boundary, "model", MODEL);
                writeFormField(out, boundary, "prompt", PROMPT);

                out.writeBytes("--" + boundary + "\r\n");
                out.writeBytes(
                        "Content-Disposition: form-data; name=\"file\";"
                                + " filename=\"recording.m4a\"\r\n");
                out.writeBytes("Content-Type: audio/mp4\r\n\r\n");
                try (FileInputStream input = new FileInputStream(audioFile)) {
                    byte[] buffer = new byte[4096];
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        out.write(buffer, 0, count);
                    }
                }
                out.writeBytes("\r\n--" + boundary + "--\r\n");
            }

            int status = connection.getResponseCode();
            InputStream response = status >= 200 && status < 300
                    ? connection.getInputStream()
                    : connection.getErrorStream();
            String body = readBody(response);
            JSONObject json = new JSONObject(body);
            if (json.has("text")) return json.getString("text");
            throw new Exception(body);
        } finally {
            connection.disconnect();
        }
    }

    @Override
    public String getFinishingMessage() {
        if (!audioFile.exists()) return null;
        return "Uploading & transcribing\u2026\nAudio: "
                + formatAudioDuration(audioFile) + " \u00b7 " + formatFileSize(audioFile.length());
    }

    @Override
    public boolean canRetry() {
        return audioFile.exists() && audioFile.length() > 0;
    }

    @Override
    public void close() {
        stop();
        audioFile.delete();
    }

    private void pollAmplitude() {
        while (recording) {
            MediaRecorder currentRecorder = recorder;
            if (currentRecorder != null) {
                try {
                    listener.onAmplitude(AudioLevel.fromNormalizedAmplitude(
                            currentRecorder.getMaxAmplitude() / 32767.0));
                } catch (Exception ignored) {
                }
            }
            try {
                Thread.sleep(AMPLITUDE_POLL_MS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            }
        }
    }

    private static String readBody(InputStream input) throws Exception {
        if (input == null) return "";
        try (InputStream response = input;
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = response.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
            return output.toString("UTF-8");
        }
    }

    private static void writeFormField(
            DataOutputStream out, String boundary, String name, String value) throws Exception {
        out.writeBytes("--" + boundary + "\r\n");
        out.writeBytes("Content-Disposition: form-data; name=\"" + name + "\"\r\n\r\n");
        out.writeBytes(value + "\r\n");
    }

    private static String formatAudioDuration(File file) {
        MediaMetadataRetriever retriever = new MediaMetadataRetriever();
        try {
            retriever.setDataSource(file.getAbsolutePath());
            String value = retriever.extractMetadata(
                    MediaMetadataRetriever.METADATA_KEY_DURATION);
            long totalSeconds = Math.max(0, Math.round(Long.parseLong(value) / 1000.0));
            long hours = totalSeconds / 3600;
            long minutes = (totalSeconds % 3600) / 60;
            long seconds = totalSeconds % 60;
            return hours > 0
                    ? String.format(Locale.getDefault(), "%d:%02d:%02d", hours, minutes, seconds)
                    : String.format(Locale.getDefault(), "%d:%02d", minutes, seconds);
        } catch (Exception ignored) {
            return "duration unknown";
        } finally {
            try {
                retriever.release();
            } catch (Exception ignored) {
            }
        }
    }

    private static String formatFileSize(long bytes) {
        if (bytes < 1024) return bytes + " B";
        double kibibytes = bytes / 1024.0;
        if (kibibytes < 1024) {
            return String.format(Locale.getDefault(), "%.1f KB", kibibytes);
        }
        return String.format(Locale.getDefault(), "%.1f MB", kibibytes / 1024.0);
    }
}
