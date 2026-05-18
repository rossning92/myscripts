package com.ross.speechtotext;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.InputMethod;
import android.view.accessibility.AccessibilityEvent;

public class TypeAccessibilityService extends AccessibilityService {
    private static TypeAccessibilityService instance;

    public static TypeAccessibilityService getInstance() {
        return instance;
    }

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        instance = null;
    }

    public boolean typeText(String text) {
        InputMethod inputMethod = getInputMethod();
        if (inputMethod == null) return false;
        InputMethod.AccessibilityInputConnection ic = inputMethod.getCurrentInputConnection();
        if (ic == null) return false;
        ic.commitText(text, 1, null);
        return true;
    }
}
