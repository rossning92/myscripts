# browsercli Chrome extension

1. Open `chrome://extensions` in the Chrome profile you want to control.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select this `extension` directory.
4. Run `browsercli connect extension`.
5. Commands initially use the active tab. `browsercli open https://example.com`
   loads a new tab in the background and then selects it without explicitly focusing
   Chrome. Subsequent commands control that tab. Follow it with `browsercli snapshot`
   or `browsercli screenshot`.

`open` uses the saved backend, initially a headless browser. Backend choices persist
across daemon restarts. Named sessions use the managed browser and do not support
extension mode.

The bridge only listens on localhost. An **ON** badge appears while the extension is
connected. Chrome may suspend extensions that have been idle; browsercli waits
for the extension's automatic 30-second reconnect, or you can click its toolbar
icon to reconnect immediately.

Snapshot uses Chrome's debugger API while collecting the accessibility tree, so
Chrome briefly displays its standard debugging notification.

When developing browsercli, reload the unpacked extension once after installing
this version. After that, it detects changes to its source files through the
local daemon and reloads itself before accepting another command.
