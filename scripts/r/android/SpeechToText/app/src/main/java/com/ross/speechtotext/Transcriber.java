package com.ross.speechtotext;

/**
 * One speech-to-text session, independent of how audio reaches the provider.
 */
interface Transcriber extends AutoCloseable {
    interface Listener {
        void onAmplitude(float amplitude);
        void onFailure(String message);
    }

    void start() throws Exception;

    void stop();

    String finish() throws Exception;

    default String getFinishingMessage() {
        return null;
    }

    default boolean canRetry() {
        return false;
    }

    @Override
    void close();
}
