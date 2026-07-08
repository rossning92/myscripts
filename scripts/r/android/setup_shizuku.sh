set -e

echo 'Install Shizuku (latest GitHub release)...'
tag=$(curl -sI "https://github.com/RikkaApps/Shizuku/releases/latest" | grep -i '^location:' | tr -d '\r' | sed -E 's#.*/tag/##')
apk=$(curl -sSL "https://github.com/RikkaApps/Shizuku/releases/expanded_assets/$tag" | grep -oE 'shizuku[^"]*-release\.apk' | head -1)
curl -sSL -o shizuku.apk "https://github.com/RikkaApps/Shizuku/releases/download/$tag/$apk"
adb install -r shizuku.apk
rm shizuku.apk

# Shizuku must be re-started after every reboot (it runs as the adb "shell" user, not persisted).
echo 'Start Shizuku service...'
shizuku_lib=$(adb shell dumpsys package moe.shizuku.privileged.api | grep legacyNativeLibraryDir | cut -d= -f2- | tr -d '[:space:]')
adb shell "$shizuku_lib"/arm64/libshizuku.so
