package com.ross.speechtotext;

import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder.AudioSource;
import android.util.Base64;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/**
 * Owns one realtime transcription session, including microphone capture and the
 * Realtime API protocol. Its lifecycle is start, stop capture, finish or close.
 */
final class RealtimeTranscriber implements Transcriber {
    private static final int SAMPLE_RATE = 24_000;
    private static final int AUDIO_CHUNK_BYTES = 4_800;
    private static final int CONNECT_TIMEOUT_MS = 10_000;
    private static final int TRANSCRIPT_TIMEOUT_MS = 20_000;
    private static final String MODEL = "gpt-live-transcribe";

    private final String apiKey;
    private final Transcriber.Listener listener;
    private final Object lock = new Object();
    private final ByteArrayOutputStream pendingAudio = new ByteArrayOutputStream();
    private final CountDownLatch connected = new CountDownLatch(1);
    private final CountDownLatch completed = new CountDownLatch(1);

    private volatile boolean recording;
    private AudioRecord recorder;
    private Thread audioThread;
    private OkHttpClient httpClient;
    private WebSocket socket;
    private boolean sessionReady;
    private final StringBuilder transcript = new StringBuilder();
    private String error;

    RealtimeTranscriber(String apiKey, Transcriber.Listener listener) {
        this.apiKey = apiKey;
        this.listener = listener;
    }

    @Override
    public void start() throws Exception {
        if (apiKey.isEmpty()) throw new Exception("API key not configured");
        httpClient = new OkHttpClient.Builder()
                .connectTimeout(CONNECT_TIMEOUT_MS, TimeUnit.MILLISECONDS)
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .build();
        Request request = new Request.Builder()
                .url("wss://api.openai.com/v1/realtime?intent=transcription")
                .header("Authorization", "Bearer " + apiKey)
                .build();

        recording = true;
        socket = httpClient.newWebSocket(request, new SocketListener());
        audioThread = new Thread(this::captureAudio, "RealtimeAudio");
        audioThread.start();
    }

    @Override
    public void stop() {
        recording = false;
        releaseRecorder();
        Thread thread = audioThread;
        if (thread != null && thread != Thread.currentThread()) {
            try {
                thread.join(1_000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        audioThread = null;
    }

    @Override
    public String finish() throws Exception {
        String earlyError = getError();
        if (earlyError != null) throw new Exception(earlyError);
        if (!connected.await(CONNECT_TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
            throw new Exception(errorOr("Timed out connecting to Realtime API"));
        }
        throwIfFailed();
        sendEvent(new JSONObject().put("type", "input_audio_buffer.commit"),
                "Realtime connection closed before finalizing");
        if (!completed.await(TRANSCRIPT_TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
            throw new Exception(errorOr("Timed out waiting for final transcript"));
        }
        throwIfFailed();

        String text;
        synchronized (lock) {
            text = transcript.toString().trim();
        }
        if (text.isEmpty()) throw new Exception("No speech was transcribed");
        return text;
    }

    @Override
    public void close() {
        stop();
        WebSocket currentSocket = socket;
        socket = null;
        if (currentSocket != null) currentSocket.close(1000, "Done");
        OkHttpClient currentClient = httpClient;
        httpClient = null;
        if (currentClient != null) {
            currentClient.dispatcher().executorService().shutdown();
            currentClient.connectionPool().evictAll();
        }
    }

    private void captureAudio() {
        try {
            int minBuffer = AudioRecord.getMinBufferSize(
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT);
            if (minBuffer <= 0) throw new Exception("24 kHz microphone recording is unavailable");

            recorder = new AudioRecord(
                    AudioSource.VOICE_RECOGNITION,
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    Math.max(minBuffer * 2, AUDIO_CHUNK_BYTES));
            if (recorder.getState() != AudioRecord.STATE_INITIALIZED) {
                throw new Exception("Could not initialize realtime microphone recording");
            }
            recorder.startRecording();
            byte[] buffer = new byte[Math.max(minBuffer, AUDIO_CHUNK_BYTES / 2)];
            while (recording) {
                int count = recorder.read(buffer, 0, buffer.length);
                if (count > 0) {
                    appendAudio(buffer, count);
                    listener.onAmplitude(calculateAmplitude(buffer, count));
                } else if (count < 0) {
                    throw new Exception("Microphone read failed: " + count);
                }
            }
        } catch (Exception e) {
            if (recording) fail(e.getMessage());
        } finally {
            releaseRecorder();
        }
    }

    private void appendAudio(byte[] pcm, int count) throws Exception {
        synchronized (lock) {
            if (!sessionReady) {
                pendingAudio.write(pcm, 0, count);
            } else {
                sendAudioEvent(pcm, 0, count);
            }
        }
    }

    // Capture starts before the handshake; flush that audio under the same lock
    // used by live chunks so microphone order is preserved exactly.
    private void markSessionReady() throws Exception {
        synchronized (lock) {
            byte[] pending = pendingAudio.toByteArray();
            for (int offset = 0; offset < pending.length; offset += AUDIO_CHUNK_BYTES) {
                sendAudioEvent(
                        pending, offset, Math.min(AUDIO_CHUNK_BYTES, pending.length - offset));
            }
            pendingAudio.reset();
            sessionReady = true;
        }
    }

    private void sendAudioEvent(byte[] pcm, int offset, int count) throws Exception {
        JSONObject event = new JSONObject()
                .put("type", "input_audio_buffer.append")
                .put("audio", Base64.encodeToString(pcm, offset, count, Base64.NO_WRAP));
        sendEvent(event, "Realtime connection closed while sending audio");
    }

    private void sendEvent(JSONObject event, String failureMessage) throws Exception {
        WebSocket currentSocket = socket;
        if (currentSocket == null || !currentSocket.send(event.toString())) {
            throw new Exception(failureMessage);
        }
    }

    private static float calculateAmplitude(byte[] pcm, int count) {
        long sumSquares = 0;
        int samples = count / 2;
        for (int i = 0; i + 1 < count; i += 2) {
            int sample = (short) ((pcm[i] & 0xff) | (pcm[i + 1] << 8));
            sumSquares += (long) sample * sample;
        }
        if (samples == 0) return 0;
        double rms = Math.sqrt(sumSquares / (double) samples);
        return AudioLevel.fromNormalizedAmplitude(rms / 32768.0);
    }

    private synchronized void releaseRecorder() {
        if (recorder == null) return;
        try {
            if (recorder.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) {
                recorder.stop();
            }
        } catch (Exception ignored) {
        }
        recorder.release();
        recorder = null;
    }

    private void fail(String message) {
        synchronized (lock) {
            if (error == null) {
                error = message == null ? "Realtime transcription failed" : message;
            }
        }
        connected.countDown();
        completed.countDown();
        listener.onFailure(errorOr("Realtime transcription failed"));
    }

    private String getError() {
        synchronized (lock) {
            return error;
        }
    }

    private String errorOr(String fallback) {
        String currentError = getError();
        return currentError == null ? fallback : currentError;
    }

    private void throwIfFailed() throws Exception {
        String currentError = getError();
        if (currentError != null) throw new Exception(currentError);
    }

    private final class SocketListener extends WebSocketListener {
        @Override
        public void onOpen(WebSocket webSocket, Response response) {
            try {
                JSONObject format = new JSONObject()
                        .put("type", "audio/pcm")
                        .put("rate", SAMPLE_RATE);
                JSONObject input = new JSONObject()
                        .put("format", format)
                        .put("transcription", new JSONObject().put("model", MODEL))
                        .put("turn_detection", JSONObject.NULL);
                JSONObject session = new JSONObject()
                        .put("type", "transcription")
                        .put("audio", new JSONObject().put("input", input));
                sendEvent(
                        new JSONObject().put("type", "session.update").put("session", session),
                        "Could not configure Realtime session");
            } catch (Exception e) {
                fail(e.getMessage());
            }
        }

        @Override
        public void onMessage(WebSocket webSocket, String text) {
            try {
                JSONObject event = new JSONObject(text);
                String type = event.optString("type");
                switch (type) {
                    case "session.created":
                        validateSession(event, "OpenAI created a non-transcription Realtime session");
                        break;
                    case "session.updated":
                        if (validateSession(
                                event, "OpenAI rejected the transcription session configuration")) {
                            markSessionReady();
                            connected.countDown();
                        }
                        break;
                    case "conversation.item.input_audio_transcription.delta":
                    case "transcription.delta":
                        synchronized (lock) {
                            transcript.append(event.optString("delta"));
                        }
                        break;
                    case "conversation.item.input_audio_transcription.completed":
                    case "transcription.completed":
                        String finalTranscript = event.optString("transcript");
                        if (!finalTranscript.isEmpty()) {
                            synchronized (lock) {
                                transcript.setLength(0);
                                transcript.append(finalTranscript);
                            }
                        }
                        completed.countDown();
                        break;
                    case "error":
                        JSONObject apiError = event.optJSONObject("error");
                        fail(apiError == null ? text : apiError.optString("message", text));
                        break;
                    default:
                        break;
                }
            } catch (Exception e) {
                fail("Invalid Realtime response: " + e.getMessage());
            }
        }

        private boolean validateSession(JSONObject event, String message) {
            JSONObject session = event.optJSONObject("session");
            if (session == null || !"transcription".equals(session.optString("type"))) {
                fail(message);
                return false;
            }
            return true;
        }

        @Override
        public void onFailure(WebSocket webSocket, Throwable throwable, Response response) {
            String message = throwable.getMessage();
            if (response != null) {
                message = "Realtime API HTTP " + response.code() + ": " + message;
            }
            fail(message);
        }
    }
}
