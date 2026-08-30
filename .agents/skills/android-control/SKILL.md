---
name: android-control
description: Controls Android device features through Termux API commands. Use when the user asks to access the clipboard, camera, microphone, media, calls, SMS, contacts, Wi-Fi, sharing, or navigation on an Android device.
compatibility: Requires Android, Termux, Termux API, and the termux-api package.
---

# Android control

## Commands

| Task                 | Command                                                                    |
| -------------------- | -------------------------------------------------------------------------- |
| Take screenshot      | `run_script r/android/termux/screenshot.sh`                                |
| Read clipboard       | `termux-clipboard-get`                                                     |
| Set clipboard        | `printf %s "TEXT" \| termux-clipboard-set`                                 |
| Take photo           | `termux-camera-photo FILE.jpg`                                             |
| Record audio         | `termux-microphone-record -d SECONDS FILE.wav`                             |
| Play media           | `termux-media-player play FILE`                                            |
| Call number          | `termux-telephony-call NUMBER`                                             |
| Send SMS             | `termux-sms-send -n NUMBER "TEXT"`                                         |
| List SMS             | `termux-sms-list`                                                          |
| View call log        | `termux-call-log`                                                          |
| List contacts        | `termux-contact-list`                                                      |
| Wi-Fi information    | `termux-wifi-connectioninfo`                                               |
| Enable/disable Wi-Fi | `termux-wifi-enable true\|false`                                           |
| Scan Wi-Fi           | `termux-wifi-scaninfo`                                                     |
| Share text           | `printf %s "TEXT" \| termux-share`                                         |
| Share file           | `termux-share FILE`                                                        |
| Navigate             | `termux-open "https://www.google.com/maps/dir/?api=1&destination=ADDRESS"` |
