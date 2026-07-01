# Red Cogs Cheatsheet

`[p]` means your Red prefix. If your prefix is `!`, `[p]ping` is `!ping`.

## Quick Health

```text
[p]ping
[p]cogs
[p]deche diagnose
[p]deche status
[p]devset status
[p]botops health
[p]musicstatus now
[p]llset info
```

## Install, Update, Reload

```text
[p]repo add red-cogs https://github.com/Dyu20705/red-cogs
[p]cog list red-cogs
[p]cog install red-cogs <cog>
[p]cog update
[p]load <cog>
[p]reload <cog>
[p]unload <cog>
```

## ImperialSetup

```text
[p]deche audit
[p]deche plan
[p]deche reconcile CONFIRM
[p]deche optimize CONFIRM
[p]deche launch CONFIRM
[p]deche status
```

## DevelopmentOps

```text
[p]devset repo add owner/repository
[p]devset repo primary owner/repository
[p]devset channel feed #github-feed
[p]devset channel review #code-review
[p]devset forum #bugs-and-ideas
[p]devset schedule 7 5
[p]devset timezone Asia/Bangkok
[p]devset status
[p]devset refreshpr 123
```

## BotOps

```text
[p]botops set audit #audit-and-mod-log
[p]botops set errors #bot-errors
[p]botops set logs #bot-logs
[p]botops status
[p]botops health
[p]botops test all
```

## StudyOps

```text
[p]studyset owner @you
[p]studyset channel daily #goals-and-progress
[p]goal add Finish review
[p]goal done 1
[p]pomo start 25 5 4 Focus topic
[p]studyset status
```

## ImperialAutomation

```text
[p]ia setchannel feeds #all-feeds
[p]ia feed add dev https://example.com/feed.xml Example
[p]ia feed checknow
[p]ia music guide
[p]ia music panel
[p]listen lock
```

## MusicStatus

```text
[p]musicstatus setchannel #now-playing
[p]musicstatus now
[p]musicstatus reset
```

## Host Commands

```powershell
python scripts/redctl.py doctor
python scripts/redctl.py check
python scripts/redctl.py watch
.\scripts\windows\doctor.ps1
```

```bash
python3 scripts/redctl.py doctor
python3 scripts/redctl.py check
scripts/linux/doctor.sh
sudo systemctl status red@YOUR_INSTANCE.service
journalctl -u red@YOUR_INSTANCE.service -n 100 --no-pager
```
