<p align="center">
  <a href="https://github.com/Dyu20705/red-cogs/actions/workflows/quality.yml"><img alt="Quality checks" src="https://github.com/Dyu20705/red-cogs/actions/workflows/quality.yml/badge.svg"></a>
  <img alt="Red-DiscordBot 3.5+" src="https://img.shields.io/badge/Red--DiscordBot-3.5%2B-dc143c">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776ab">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
  <img alt="Security model" src="https://img.shields.io/badge/security-least%20privilege-6f42c1">
</p>

# 🏰 Duy Red Cogs

Bộ cog **Red-DiscordBot** dành cho server cá nhân: dựng cấu trúc Discord, theo dõi vận hành, kết nối GitHub, tự động hóa feed/nhạc, quản lý học tập và hiển thị tình trạng bot.

## Danh mục cog

| Cog | Vai trò | Lệnh chính |
|---|---|---|
| [`imperialsetup`](imperialsetup/) | Audit, lập kế hoạch và reconcile cấu trúc/permission server theo blueprint | `[p]deche` |
| [`developmentops`](developmentops/) | GitHub webhook, feed, PR review thread và Discord Forum ↔ GitHub Issue | `[p]devset` |
| [`botops`](botops/) | Audit log, incident/error reporting và traceback đã redact | `[p]botops` |
| [`imperialautomation`](imperialautomation/) | RSS/digest, Audio controls, queue quota, now-playing panel và private listening room | `[p]ia` |
| [`studyops`](studyops/) | Daily goals, Pomodoro, study log, weekly progress và temporary study rooms | `[p]studyset` |
| [`musicstatus`](musicstatus/) | Bảng health định kỳ cho Red, latency, uptime, Lavalink và active music rooms | `[p]musicstatus` |

> [!IMPORTANT]
> `[p]` là prefix của Red. Nếu prefix là `!`, `[p]help` nghĩa là `!help`. Các lệnh này được gửi **trong Discord**, không phải CMD/PowerShell/terminal.

## Bắt đầu

### 1. Cài Red và tạo bot

Xem hướng dẫn đầy đủ cho Discord application, Windows 10/11 và Ubuntu 24.04:

**[docs/INSTALLATION.md](docs/INSTALLATION.md)**

### 2. Thêm repository

Chạy bằng tài khoản Red bot owner trong Discord:

```text
[p]load downloader
[p]repo add red-cogs https://github.com/Dyu20705/red-cogs
[p]cog list red-cogs
```

Cài đúng cog bạn cần, ví dụ:

```text
[p]cog install red-cogs imperialsetup
[p]cog install red-cogs botops
[p]cog install red-cogs developmentops
[p]load imperialsetup
[p]load botops
[p]load developmentops
```

Không nên load cả sáu cog chỉ vì chúng tồn tại. Mỗi cog thêm permission, trạng thái và log cần vận hành.

## ImperialSetup: luồng an toàn

```text
[p]deche diagnose
[p]deche audit
[p]deche plan
[p]deche reconcile CONFIRM
[p]deche status
```

Chỉ chạy chuẩn hóa mạnh sau khi đã review plan và backup:

```text
[p]deche optimize CONFIRM
[p]deche launch CONFIRM
```

Hardening layer chỉ thay overwrite thuộc blueprint (`@everyone`, Quân Vương, Nội Các, Cận Vệ và bot). Overwrite của role/member tùy chỉnh được giữ lại; mutation dừng khi nhiều channel cùng khớp một tên/alias.

## Permission model

Không cấp `Administrator` mặc định. Role bot phải nằm cao hơn role mà cog cần quản lý. ImperialSetup thường cần:

- Manage Roles, Manage Channels
- View Channels, Send Messages, Embed Links
- Attach Files, Read Message History
- Connect, Speak

`Manage Server` chỉ cần nếu muốn cog tự đặt AFK channel.

## DevelopmentOps security

- Webhook payload được xác minh bằng HMAC SHA-256.
- Listener mặc định bind `127.0.0.1:8765`.
- Chỉ đưa `/github` ra Internet qua HTTPS reverse proxy/tunnel có kiểm soát.
- Credential GitHub và webhook secret được đọc từ process environment, không lưu trong Red Config.
- Forum sync có thể chuyển nội dung, attachment URL và creator ID sang GitHub Issue; chỉ bật khi thành viên đã được thông báo.

Xem **[docs/DEVELOPMENTOPS.md](docs/DEVELOPMENTOPS.md)**.

## Tài liệu

- [Command reference tự generate](docs/COMMANDS.md)
- [Cheatsheet thao tác nhanh](docs/CHEATSHEET.md)
- [Cài Discord application và Red trên Windows/Ubuntu](docs/INSTALLATION.md)
- [Update, backup, restore, logs, rollback và troubleshooting](docs/OPERATIONS.md)
- [Triển khai DevelopmentOps](docs/DEVELOPMENTOPS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Development](docs/DEVELOPMENT.md)
- [Data handling](docs/DATA_HANDLING.md)
- [Upgrade guide](docs/UPGRADE.md)
- [Runtime smoke test plan](docs/RUNTIME_TEST_PLAN.md)
- [Tools và chiến lược tự động hóa server](docs/TOOLS.md)
- [Security policy](SECURITY.md)
- [Contributing guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Kiểm tra chất lượng

```bash
python scripts/redctl.py check
```

CI kiểm tra metadata, unit test, Python syntax, generated docs freshness, shell syntax, và smoke checks cho tooling.

## Giới hạn đã biết

- ImperialSetup vẫn nhận diện resource chủ yếu bằng tên/alias; vNext nên lưu resource ID và schema version.
- Một số cog còn là file lớn, trộn nhiều trách nhiệm.
- DevelopmentOps có receiver và queue in-process; dedupe không bền qua restart và timezone hiện cố định UTC+7.
- Discord không có transaction đa bước; backup và `audit → plan` vẫn bắt buộc.

## License

Phát hành theo [MIT License](LICENSE).
