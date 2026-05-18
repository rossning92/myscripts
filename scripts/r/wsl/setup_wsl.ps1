# Setup WSL2 on Windows host

# Enable mirrored networking mode (Windows 11 22H2+)
Set-Content -Path "$env:USERPROFILE\.wslconfig" -Value "[wsl2]`nnetworkingMode=mirrored`nguiApplications=false"

# Auto-mount Google Drive (G:) on WSL login
wsl -u root -- mkdir -p /mnt/g
wsl -- bash -c 'grep -q "drvfs.*G:" ~/.profile 2>/dev/null || echo "
# Auto-mount Google Drive
if [ -d /mnt/g ] && ! mountpoint -q /mnt/g 2>/dev/null; then
    sudo mount -t drvfs G: /mnt/g 2>/dev/null
fi" >> ~/.profile'
wsl -u root -- bash -c 'echo "$(id -un 1000) ALL=(root) NOPASSWD: /usr/bin/mount -t drvfs G\: /mnt/g" > /etc/sudoers.d/gdrive-mount && chmod 440 /etc/sudoers.d/gdrive-mount'
wsl -- ln -sfn "/mnt/g/My Drive" ~/gdrive

# Passwordless sudo for the default user
$sudoScript = 'u=$(id -un 1000); echo "$u ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/$u && chmod 440 /etc/sudoers.d/$u'
[System.Text.Encoding]::UTF8.GetBytes($sudoScript) | wsl -u root -- bash

# Fix "Cannot make directory '/run/screen': Permission denied"
# WSL2 doesn't run systemd-tmpfiles by default, so /run/screen is never created.
$bootCmd = "command = mkdir -p /run/screen && chmod 777 /run/screen"
$wslConf = @"
[boot]
$bootCmd
"@
wsl -u root -- bash -c "grep -q '/run/screen' /etc/wsl.conf 2>/dev/null || echo '$wslConf' >> /etc/wsl.conf"

wsl --shutdown
