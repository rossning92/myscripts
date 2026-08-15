#!/system/bin/sh
BASEDIR=$(dirname "$0")
DEX="$BASEDIR"/rish_shizuku.dex

if [ ! -f "$DEX" ]; then
  echo "Cannot find $DEX, please check the tutorial in Shizuku app"
  exit 1
fi

if [ $(getprop ro.build.version.sdk) -ge 34 ]; then
  DEX_PERMISSIONS=$(/system/bin/stat -c %A "$DEX")
  if echo "$DEX_PERMISSIONS" | grep -q w; then
    echo "On Android 14+, app_process cannot load writable dex."
    echo "Attempting to remove the write permission..."
    chmod 400 $DEX
    DEX_PERMISSIONS=$(/system/bin/stat -c %A "$DEX")
  fi
  if echo "$DEX_PERMISSIONS" | grep -q w; then
    echo "Cannot remove the write permission of $DEX."
    echo "You can copy to file to terminal app's private directory (/data/data/<package>, so that remove write permission is possible"
    exit 1
  fi
fi

# Replace "PKG" with the application id of your terminal app
export RISH_APPLICATION_ID="com.termux"
/system/bin/app_process -Djava.class.path="$DEX" /system/bin --nice-name=rish rikka.shizuku.shell.ShizukuShellLoader "$@"
