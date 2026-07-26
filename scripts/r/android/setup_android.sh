set -e

echo 'Disable window animation...'
adb shell settings put global window_animation_scale 0
adb shell settings put global transition_animation_scale 0
adb shell settings put global animator_duration_scale 0

# https://github.com/agnostic-apollo/Android-Docs/blob/master/en/docs/apps/processes/phantom-cached-and-empty-processes.md#commands-to-disable-phantom-process-killing-and-tldr
echo 'Disable the phantom processes killing'
# Same as enabling "Disable child process restrictions" in Developer Options.
adb shell settings put global settings_enable_monitor_phantom_procs false
android_version=$(adb shell getprop ro.build.version.release | tr -d '[:space:]')
if [ "$android_version" -ge "14" ] && adb shell command -v su >/dev/null 2>&1; then
    adb shell su -c "setprop persist.sys.fflag.override.settings_enable_monitor_phantom_procs false"
fi

# Reduce the height of the status bar / display cutout (Pixel 9/10)
echo 'Reduce status bar height (hole cutout emulation)...'
adb shell cmd overlay enable com.android.internal.display.cutout.emulation.hole

echo 'Show battery percentage in the status bar...'
adb shell settings put system status_bar_show_battery_percent 1

echo 'Set screen timeout to 5 minutes...'
adb shell settings put system screen_off_timeout 300000

echo 'Disable adaptive tone (Pixel only)...'
adb shell settings put secure display_white_balance_enabled 0

echo 'Turn on Battery saver (sticky) and keep "turn off at 90%" disabled...'
adb shell settings put global low_power 1
adb shell settings put global low_power_sticky 1
adb shell settings put global low_power_sticky_auto_disable_enabled 0

install_fdroid() {
    pkg=$1
    vc=$(curl -sSL "https://f-droid.org/api/v1/packages/$pkg" | python3 -c "import sys,json;print(json.load(sys.stdin)['suggestedVersionCode'])")
    curl -sSL -o "/tmp/$pkg.apk" "https://f-droid.org/repo/${pkg}_${vc}.apk"
    adb install -r "/tmp/$pkg.apk"
    rm "/tmp/$pkg.apk"
}

echo 'Install AVNC...'
install_fdroid com.gaurav.avnc

echo 'Install KeePassDX...'
install_fdroid com.kunzisoft.keepass.libre

echo 'Set KeePassDX as autofill service...'
adb shell settings put secure autofill_service "com.kunzisoft.keepass.libre/com.kunzisoft.keepass.credentialprovider.autofill.KeeAutofillService"

echo 'Install Termux and Termux:API...'
install_fdroid com.termux
install_fdroid com.termux.api

echo 'Install Island...'
install_fdroid com.oasisfeng.island.fdroid

echo 'Install MuPDF...'
install_fdroid com.artifex.mupdf.viewer.app

echo 'Install Aves Libre...'
install_fdroid deckers.thibault.aves.libre

echo 'Install Aegis Authenticator...'
install_fdroid com.beemdevelopment.aegis

echo 'Setup Shizuku...'
sh "$(dirname "$0")/setup_shizuku.sh"
