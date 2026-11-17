import android.content.ClipData;
import android.net.Uri;
import android.os.IBinder;
import java.lang.reflect.Method;

public final class ReadClipboardUri {
    public static void main(String[] args) {
        try {
            readClipboard();
        } catch (ReflectiveOperationException | RuntimeException error) {
            Throwable cause = error.getCause();
            System.err.println("Android clipboard read failed: "
                    + (cause == null ? error : cause).getMessage());
            System.exit(1);
        }
    }

    private static void readClipboard() throws ReflectiveOperationException {
        Class<?> serviceManager = Class.forName("android.os.ServiceManager");
        IBinder binder = (IBinder) serviceManager.getMethod("getService", String.class)
                .invoke(null, "clipboard");
        Class<?> stub = Class.forName("android.content.IClipboard$Stub");
        Object clipboard = stub.getMethod("asInterface", IBinder.class).invoke(null, binder);
        Class<?> clipboardInterface = Class.forName("android.content.IClipboard");
        int user = (int) Class.forName("android.os.UserHandle").getMethod("myUserId").invoke(null);

        // Termux:API shares the terminal's UID and will open the granted URI.
        String caller = "com.termux.api";
        ClipData clip;
        try {
            Method read = clipboardInterface.getMethod("getPrimaryClip",
                    String.class, String.class, int.class, int.class);
            clip = (ClipData) read.invoke(clipboard, caller, null, user, 0);
        } catch (NoSuchMethodException noDeviceArgument) {
            try {
                Method read = clipboardInterface.getMethod("getPrimaryClip",
                        String.class, String.class, int.class);
                clip = (ClipData) read.invoke(clipboard, caller, null, user);
            } catch (NoSuchMethodException noAttributionArgument) {
                Method read = clipboardInterface.getMethod("getPrimaryClip", String.class, int.class);
                clip = (ClipData) read.invoke(clipboard, caller, user);
            }
        }

        if (clip != null && clip.getDescription().hasMimeType("image/*")) {
            for (int index = 0; index < clip.getItemCount(); index++) {
                Uri uri = clip.getItemAt(index).getUri();
                if (uri != null && "content".equals(uri.getScheme())) {
                    System.out.println(uri);
                    return;
                }
            }
        }
        System.err.println("No image URI on the clipboard. Keep Termux in focus.");
        System.exit(1);
    }
}
