# browsercli Chrome extension

1. Open `chrome://extensions` in the Chrome profile you want to control.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select this `extension` directory.
4. Run `browsercli connect extension`.
5. Commands now use the active tab, for example `browsercli open
   https://example.com` followed by `browsercli snapshot` or
   `browsercli screenshot`.

`browsercli open --extension https://example.com` remains available as a
shortcut that selects the extension backend and navigates in one command.

The command navigates the active tab in the current Chrome window. The bridge
only listens on localhost. An **ON** badge appears while the extension is
connected. Chrome may suspend extensions that have been idle; browsercli waits
for the extension's automatic 30-second reconnect, or you can click its toolbar
icon to reconnect immediately.

Snapshot uses Chrome's debugger API while collecting the accessibility tree, so
Chrome briefly displays its standard debugging notification.
