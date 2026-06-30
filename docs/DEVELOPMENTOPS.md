# DevelopmentOps deployment guide

DevelopmentOps connects GitHub events to Discord channels, review threads, forum posts, and scheduled development goals.

## Runtime configuration

The cog reads these process environment variables:

- `DEVELOPMENTOPS_WEBHOOK_SECRET`
- `DEVELOPMENTOPS_GITHUB_TOKEN` (optional)
- `DEVELOPMENTOPS_HOST` (default `127.0.0.1`)
- `DEVELOPMENTOPS_PORT` (default `8765`)

Keep the listener on loopback. Expose only the `/github` route through a controlled HTTPS reverse proxy or secure tunnel.

### Ubuntu systemd

Create a root-readable environment file:

```bash
sudo install -m 600 /dev/null /etc/redbot-developmentops.env
sudo nano /etc/redbot-developmentops.env
```

Add this line to the `[Service]` section of `red@.service`:

```ini
EnvironmentFile=/etc/redbot-developmentops.env
```

Then reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart red@imperial
journalctl -u red@imperial -n 100 --no-pager
```

### Windows PowerShell

Set the variables in the same PowerShell session or service configuration that starts Red, then start the instance:

```powershell
$env:DEVELOPMENTOPS_HOST = "127.0.0.1"
$env:DEVELOPMENTOPS_PORT = "8765"
redbot imperial
```

## Install

Run as the Red bot owner in Discord:

```text
[p]load downloader
[p]repo add red-cogs https://github.com/Dyu20705/red-cogs
[p]cog install red-cogs developmentops
[p]load developmentops
[p]devset status
```

The GitHub receiver remains disabled until its required runtime value is present.

## Repository and channel mapping

```text
[p]devset repo add OWNER/REPOSITORY
[p]devset repo primary OWNER/REPOSITORY
[p]devset channel feed #github-feed
[p]devset channel review #code-review
[p]devset channel daily #goals-and-progress
[p]devset channel release #github-feed
[p]devset status
```

Use `[p]help devset` to verify the exact command syntax available in the installed version.

## Daily goals and PR review

```text
[p]devset schedule 7 5
[p]devset postgoals
[p]devset reviewlabel review-needed
[p]devset refreshpr 123 OWNER/REPOSITORY
```

The current scheduler uses UTC+7.

## Discord Forum and GitHub Issues

Create a Forum channel such as `bugs-and-ideas`, then configure it:

```text
[p]devset forum #bugs-and-ideas
[p]devset forumsync true
[p]devset status
```

Managed tags can include `bug`, `feature`, `question`, `ui-ux`, `performance`, `blocked`, and `resolved`.

When forum synchronization is enabled, the cog may copy the configured forum post content, attachment URLs, and creator ID into a GitHub Issue. Only enable it where members have been informed about that data flow.

## GitHub webhook

In repository settings:

1. Add a webhook.
2. Use an HTTPS payload URL ending in `/github`.
3. Select `application/json`.
4. Use the same signing value configured for the Red process.
5. Select only the event groups needed by the server.
6. Send a test delivery and check for HTTP `202`.

Local health check:

```bash
curl http://127.0.0.1:8765/healthz
```

## Reverse proxy example

```nginx
location = /github {
    proxy_pass http://127.0.0.1:8765/github;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    client_max_body_size 2m;
}

location = /healthz {
    proxy_pass http://127.0.0.1:8765/healthz;
}
```

Use HTTPS and add request rate limiting at the proxy.

## Troubleshooting

```text
[p]devset status
```

```bash
ss -ltnp | grep 8765
journalctl -u red@imperial -n 200 --no-pager
curl -i http://127.0.0.1:8765/healthz
```

Check that the variables belong to the correct Red process, the service was restarted after configuration changes, the port is free, the repository is registered, and the Discord destination channels are configured.

## Known limits

- The HTTP listener runs inside the Red process.
- Delivery deduplication and active dispatch tasks are not durable across restarts.
- The scheduler timezone is fixed to UTC+7.
- Forum/Issue mappings need manual review when changing the primary repository or deleting Discord threads.

A larger deployment should separate ingress and durable queueing from the Discord bot process.
