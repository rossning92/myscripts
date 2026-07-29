package com.ross.speechtotext;

final class AudioLevel {
    private static final float SILENCE_DB = -55f;
    private static final float FULL_SCALE_DB = -12f;
    private static final float MIN_NORMALIZED_AMPLITUDE = 0.0001f;

    private AudioLevel() {
    }

    static float fromNormalizedAmplitude(double amplitude) {
        double safeAmplitude = Math.max(MIN_NORMALIZED_AMPLITUDE, amplitude);
        float decibels = (float) (20.0 * Math.log10(safeAmplitude));
        float level = (decibels - SILENCE_DB) / (FULL_SCALE_DB - SILENCE_DB);
        return Math.max(0f, Math.min(1f, level));
    }
}
