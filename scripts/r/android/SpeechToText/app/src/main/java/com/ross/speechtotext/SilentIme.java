package com.ross.speechtotext;

import android.inputmethodservice.InputMethodService;
import android.view.View;
import android.view.inputmethod.InputConnection;

// A keyboard that draws nothing (its input view is pinned to 1px). Used while
// dictating over apps like AVNC so no keyboard bar covers the screen. When it is
// the active, shown keyboard it owns the live input connection and commits the
// transcription itself.
public class SilentIme extends InputMethodService {
    private static SilentIme instance;

    public static SilentIme getInstance() {
        return instance;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (instance == this) instance = null;
    }

    @Override
    public View onCreateInputView() {
        // The IME container ignores a LayoutParams height of 0 (stretches it to
        // full screen), so pin the measured height to 1px - imperceptible, but
        // genuinely shown so the input connection stays active.
        return new View(this) {
            @Override
            protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
                setMeasuredDimension(MeasureSpec.getSize(widthMeasureSpec), 1);
            }
        };
    }

    @Override
    public boolean onEvaluateFullscreenMode() {
        return false;
    }

    @Override
    public boolean onEvaluateInputViewShown() {
        return true;
    }

    public boolean typeText(String text) {
        InputConnection ic = getCurrentInputConnection();
        if (ic == null) return false;
        return ic.commitText(text, 1);
    }
}
