defaults write com.apple.finder AppleShowAllFiles YES

# Disable auto-brightness (newer macOS, Catalina+)
defaults write com.apple.iokit.AmbientLightSensor "Automatic Display Enabled" -bool false
# Disable auto-brightness (older macOS, pre-Catalina)
defaults write com.apple.BezelServices dAuto -bool false

# Enable dark mode
defaults write NSGlobalDomain AppleInterfaceStyle Dark

# Disable Tips notifications
defaults write com.apple.TipsNotifications Enabled -bool false

# Enable double-tap to drag (without drag lock)
defaults write com.apple.AppleMultitouchTrackpad Dragging -bool true
defaults write com.apple.AppleMultitouchTrackpad DragLock -bool false

# Set wallpaper to solid Space Gray Pro
osascript -e 'tell application "Finder" to set desktop picture to POSIX file "/System/Library/Desktop Pictures/Solid Colors/Space Gray Pro.png"'
