# Public demo and laptop backend

Dashboard: https://holycow-herd-monitor.freebream261.chatgpt.site

The dashboard is hosted on Cloudflare through Sites and works with the laptop off.
Its herd, map and cattle data remain synthetic demo observations. Favorites and
attached recordings belong to each visitor's browser.

## Turn the backend on

Double-click **Start Demo Backend.cmd** in this folder. Wait for **CONNECTED**,
then open the public dashboard. Flight log and Notifications reconnect automatically.
Keep the launcher window open and the laptop awake and online during the demo.
The launcher waits until both public backend routes respond successfully before
printing CONNECTED. A new tunnel can take up to three minutes to become reachable.

The launcher starts the local Python flight service, the notification worker,
an authenticated HTTP gateway and a Cloudflare Quick Tunnel. It automatically
registers its new tunnel URL with the hosted dashboard and renews the connection
every 25 seconds. There is no need to copy a new URL or redeploy after each start.

Notifications uses the existing `backend/.env` configuration, including the
configured Telegram chat. While connected, anyone visiting the public dashboard
can request the labeled Telegram demo (subject to the existing 30-second cooldown),
view demo notification history, process the fixed scene and review its detections.
This is a shared presentation demo, not a production rancher account system.

Close an existing local flight service before launching: ports 8765 and 8880
must be free. An existing notification worker on port 8870 is reused only after
it accepts the configured service credential, avoiding a second Telegram poller.

## Turn the backend off

Press **Ctrl+C** in the launcher window, or use **Stop Demo Backend.cmd**. It unregisters the tunnel and stops its
services it started, including child inference jobs. A reused notification worker
continues running locally but is disconnected from the public dashboard.
If the laptop loses power or connectivity,
the registration expires within 90 seconds. Dashboard pages remain available;
backend requests show an offline message. Completed reviews stay in the laptop SQLite files.

## Troubleshooting

Logs: `backend/state/laptop-notifications.log`, `laptop-flight.log`, and
`laptop-tunnel.log`. The private connection key is in ignored
`backend/.env.laptop.json`. Do not share or commit that file.
The motion input is prepared at `ml/motion-demo-assets/playback.mp4`; see DEMO.md.
The matching connection key is stored as a secret in the hosted Site.

Quick Tunnels are temporary demo infrastructure and have no uptime guarantee.
Restart the launcher to obtain and automatically register a fresh connection.
The laptop needs outbound HTTPS access, including access to Telegram and any
configured feedback model provider. No router port forwarding is required.

For an isolated end-to-end connectivity check with temporary data and **no
Telegram polling or messages**, run:

```powershell
backend/.venv/Scripts/python.exe -m backend.laptop_demo --check
```

Only one launcher or connectivity check may run at a time. The check temporarily
connects its isolated backend to the public dashboard and disconnects on completion.
