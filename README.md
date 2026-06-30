<p align="center">
  <img src="assets/banner.svg" alt="Duy Red Cogs banner" width="900">
</p>

<p align="center">
  <a href="https://github.com/Dyu20705/red-cogs/actions/workflows/quality.yml"><img alt="Quality checks" src="https://github.com/Dyu20705/red-cogs/actions/workflows/quality.yml/badge.svg"></a>
  <img alt="Red-DiscordBot 3.5+" src="https://img.shields.io/badge/Red--DiscordBot-3.5%2B-dc143c">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776ab">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
  <img alt="Security model" src="https://img.shields.io/badge/security-least%20privilege-6f42c1">
</p>

# Duy Red Cogs

Một repository cog dành cho **Red-DiscordBot** để vận hành server Discord cá nhân theo hướng có cấu trúc, an toàn và có thể kiểm tra lại.

Repository hiện có hai cog:

| Cog | Vai trò | Lệnh chính |
|---|---|---|
| [`imperialsetup`](imperialsetup/) | Audit, reconcile và khởi tạo cấu trúc server theo blueprint “Quân chủ chuyên chế” | `[p]deche` |
| [`developmentops`](developmentops/) | Kết nối GitHub với Discord: webhook feed, PR review thread, Forum ↔ Issue và daily goals | `[p]devset` |

> [!IMPORTANT]
> `[p]` là **prefix của Red**, không phải văn bản cần nhập nguyên. Nếu prefix là `!`, `[p]help` nghĩa là `!help`. Các lệnh `[p]...` được gửi **trong Discord**, không phải CMD/PowerShell/terminal.

## Vì sao dự án này không chỉ là “config”?

- `imperialsetup` là một **reconciler**: đọc trạng thái server, lập kế hoạch và đưa các resource được quản lý về trạng thái mong muốn.
- `developmentops` là một **integration service**: nhận webhook GitHub, gọi GitHub API và điều phối luồng công việc Discord.
- Repository có metadata Red, kiểm tra cấu trúc, unit test, secret scan và GitHub Actions CI.

## Bắt đầu nhanh

### 1. Cài Red và tạo bot

Hướng dẫn từ tạo Discord application đến chạy Red trên Windows 10/11 hoặc Ubuntu 24.04:

**[docs/INSTALLATION.md](docs/INSTALLATION.md)**

### 2. Thêm repository bằng Downloader

Chạy bằng tài khoản **Red bot owner** trong Discord:

```text
[p]load downloader
[p]repo add red-cogs https://github.com/Dyu20705/red-cogs
[p]cog list red-cogs
```

### 3. Cài ImperialSetup

```text
[p]cog install red-cogs imperialsetup
[p]load imperialsetup
[p]deche diagnose
[p]deche audit
[p]deche plan
```

Sau khi đọc báo cáo:

```text
[p]deche reconcile CONFIRM
[p]deche status
```

`optimize` và `launch` là các bước riêng, có chủ đích:

```text
[p]deche optimize CONFIRM
[p]deche launch CONFIRM
```

### 4. Cài DevelopmentOps

```text
[p]cog install red-cogs developmentops
[p]load developmentops
[p]devset status
```

Cog vẫn có thể load khi chưa cấu hình webhook secret, nhưng receiver GitHub sẽ bị vô hiệu hóa. Xem hướng dẫn environment variable, reverse proxy, GitHub webhook và lệnh cấu hình tại:

**[docs/DEVELOPMENTOPS.md](docs/DEVELOPMENTOPS.md)**

## ImperialSetup: luồng thay đổi an toàn

| Bước | Lệnh | Thay đổi server? | Mục đích |
|---|---|---:|---|
| Diagnose | `[p]deche diagnose` | Không | Kiểm tra role hierarchy và effective permission |
| Audit | `[p]deche audit` | Không | Inventory phần khớp, thiếu và không được quản lý |
| Plan | `[p]deche plan` | Không | Xem hành động dự kiến trước khi chạy |
| Reconcile | `[p]deche reconcile CONFIRM` | Có | Tái sử dụng, đổi tên, di chuyển và tạo phần thiếu |
| Optimize | `[p]deche optimize CONFIRM` | Có | Chuẩn hóa permission/topic/slowmode trong ownership boundary |
| Launch | `[p]deche launch CONFIRM` | Có | Seed channel trống và đăng dashboard |
| Status | `[p]deche status` | Không | Kiểm tra trạng thái sau triển khai |

### Permission tối thiểu

Không cần cấp `Administrator`. Role bot phải nằm cao hơn các role mà bot cần tạo/sửa.

- Manage Roles
- Manage Channels
- View Channels
- Send Messages
- Embed Links
- Attach Files
- Read Message History
- Connect
- Speak

`Manage Server` chỉ cần khi muốn ImperialSetup tự đặt AFK channel.

### Preserve-first thực sự nghĩa là gì?

Lớp hardening chỉ thay overwrite thuộc blueprint:

- `@everyone`
- `👑 Quân Vương`
- `🏛️ Nội Các`
- `🛡️ Cận Vệ`
- bot member

Overwrite của role/member khác được giữ lại. Resource không nhận diện được cũng không bị xóa.

## DevelopmentOps: phạm vi chính

- Nhận GitHub webhook có kiểm tra HMAC SHA-256.
- Route push, PR, issue, workflow, release và deployment event vào channel phù hợp.
- Tạo/refresh thread review cho PR.
- Đồng bộ Discord Forum post thành GitHub Issue và trạng thái resolved.
- Đăng DEVELOPMENT GOALS theo lịch UTC+7.
- Không lưu GitHub token hoặc webhook secret trong Red Config; secret được đọc từ process environment.

> [!WARNING]
> Không public trực tiếp port receiver `8765`. Giữ service bind ở `127.0.0.1` và đưa ra Internet qua HTTPS reverse proxy/tunnel có kiểm soát.

## Cấu trúc repository

```text
red-cogs/
├─ imperialsetup/
│  ├─ blueprint.py
│  ├─ imperialsetup.py
│  ├─ hardening.py
│  ├─ safety.py
│  └─ info.json
├─ developmentops/
│  ├─ developmentops.py
│  ├─ README.md
│  └─ info.json
├─ docs/
│  ├─ INSTALLATION.md
│  ├─ OPERATIONS.md
│  ├─ DEVELOPMENTOPS.md
│  ├─ ARCHITECTURE.md
│  └─ TOOLS.md
├─ scripts/validate_repo.py
├─ tests/test_safety.py
├─ assets/banner.svg
├─ info.json
├─ SECURITY.md
├─ CONTRIBUTING.md
└─ LICENSE
```

## Tài liệu

- [Cài Discord application và Red trên Windows/Ubuntu](docs/INSTALLATION.md)
- [Cài cog, update, backup, restore, logs và rollback](docs/OPERATIONS.md)
- [Triển khai và cấu hình DevelopmentOps](docs/DEVELOPMENTOPS.md)
- [Audit kiến trúc, giới hạn và hướng refactor](docs/ARCHITECTURE.md)
- [Bộ công cụ cho bot, study, development, feeds và music](docs/TOOLS.md)
- [Security policy](SECURITY.md)
- [Contributing guide](CONTRIBUTING.md)

## Kiểm tra chất lượng local

Các kiểm tra dependency-free không cần cài Red:

```bash
python scripts/validate_repo.py
python -m unittest discover -s tests -v
python -m compileall -q imperialsetup developmentops scripts tests
```

Runtime behavior vẫn phải được kiểm tra trên bot/server phát triển riêng trước khi áp dụng vào server chính.

## Giới hạn đã biết

- ImperialSetup hiện vẫn nhận diện resource chủ yếu bằng tên/alias; lưu resource ID + schema version sẽ tốt hơn trong phiên bản tiếp theo.
- Hai engine chính còn lớn và trộn nhiều trách nhiệm; xem [kiến trúc đề xuất](docs/ARCHITECTURE.md).
- `developmentops` dùng timezone UTC+7 cố định và receiver nằm trong cùng process Red; production quy mô lớn nên tách ingress/queue khỏi bot.
- Không có transaction Discord đa bước; backup và `audit → plan` vẫn bắt buộc trước thay đổi lớn.

## License

Phát hành theo [MIT License](LICENSE).
