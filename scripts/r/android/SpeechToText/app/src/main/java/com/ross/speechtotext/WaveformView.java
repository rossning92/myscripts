package com.ross.speechtotext;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.drawable.GradientDrawable;
import android.view.View;

import java.util.Arrays;

public class WaveformView extends View {
    private static final int BAR_COUNT = 14;
    private final float[] amplitudes = new float[BAR_COUNT];
    private final float[] displayed = new float[BAR_COUNT];
    private final Paint barPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF rect = new RectF();
    private final float barWidth;
    private final float barGap;
    private final float cornerRadius;
    private final float minBarHeight;

    public WaveformView(Context context) {
        super(context);
        float d = context.getResources().getDisplayMetrics().density;
        barWidth = 3f * d;
        barGap = 1.5f * d;
        cornerRadius = 1.5f * d;
        minBarHeight = 2f * d;
        barPaint.setColor(0xFF65558F);

        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xFFFFFFFF);
        bg.setCornerRadius(18f * d);
        setBackground(bg);
        setElevation(4f * d);
        setClipToOutline(true);
    }

    public void addAmplitude(float amplitude) {
        System.arraycopy(amplitudes, 1, amplitudes, 0, BAR_COUNT - 1);
        amplitudes[BAR_COUNT - 1] = amplitude;
        invalidate();
    }

    public void clear() {
        Arrays.fill(amplitudes, 0);
        Arrays.fill(displayed, 0);
        invalidate();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float step = barWidth + barGap;
        float total = BAR_COUNT * step - barGap;
        float x0 = (getWidth() - total) / 2f;
        float cy = getHeight() / 2f;
        float maxH = getHeight() * 0.65f;

        for (int i = 0; i < BAR_COUNT; i++) {
            displayed[i] += (amplitudes[i] - displayed[i]) * 0.35f;
            float h = minBarHeight + displayed[i] * maxH;
            float left = x0 + i * step;
            rect.set(left, cy - h / 2f, left + barWidth, cy + h / 2f);
            canvas.drawRoundRect(rect, cornerRadius, cornerRadius, barPaint);
        }
        postInvalidateOnAnimation();
    }
}
