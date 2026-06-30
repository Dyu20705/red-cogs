# Cài đặt hoàn chỉnh: Discord → Red-DiscordBot → Duy Red Cogs

Tài liệu này đi từ con số 0 đến một bot chạy được trên Windows 10/11 hoặc Ubuntu 24.04 LTS.

> [!WARNING]
> Credential bot Discord là mật khẩu. Không gửi vào Discord, ảnh chụp, issue, log, `.env` hoặc commit. Khi nghi ngờ lộ, reset ngay trong Discord Developer Portal.

## 0. Chọn nơi chạy bot

| Mô hình | Phù hợp | Hạn chế |
|---|---|---|
| Windows PC | Thử nghiệm, phát triển | Tắt/sleep máy là bot offline |
| Ubuntu 24.04 VPS/home server | Chạy 24/7 | Cần SSH, systemd và backup |

Khuyến nghị: phát triển trên Windows, chạy lâu dài trên Ubuntu, và dùng bot/server thử nghiệm riêng cho thay đổi permission lớn.

## 1. Tạo server Discord

1. Mở Discord, nhấn dấu **+**.
2. Chọn **Create My Own**.
3. Đặt tên và ảnh đại diện.
4. Vào **Server Settings → Roles**. Sau khi mời bot, role bot phải nằm cao hơn role mà bot cần quản lý.

Không cần dựng toàn bộ category/channel thủ công; ImperialSetup sẽ audit, tái sử dụng phần khớp và tạo phần thiếu.

## 2. Tạo Discord application

1. Mở Discord Developer Portal.
2. Chọn **New Application**.
3. Trong **Installation**, tắt `User Install` nếu chỉ dùng bot trong server của bạn.
4. Trong **Bot**:
   - Có thể tắt `Public Bot`.
   - Tắt `Require OAuth2 Code Grant`.
   - Reset/copy bot credential và cất trong password manager.
5. Bật ba privileged intents:
   - Presence Intent
   - Server Members Intent
   - Message Content Intent
6. Lưu thay đổi.

Red sẽ tạo invite URL ở lần chạy đầu; không cần tự đoán permission integer.

# A. Windows 10/11 x86-64

## A1. Cài prerequisite

Cài:

- Python 3.11 x64
- Git for Windows
- Java 17 LTS x64 nếu dùng Audio
- PowerShell/Windows Terminal

Mở PowerShell mới và kiểm tra:

```powershell
py -3.11 --version
git --version
java -version
```

## A2. Tạo virtual environment

```powershell
py -3.11 -m venv "$env:USERPROFILE\redenv"
& "$env:USERPROFILE\redenv\Scripts\Activate.ps1"
```

Nếu PowerShell chặn script:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Đóng/mở PowerShell rồi kích hoạt lại. Dấu nhắc thường có `(redenv)`.

## A3. Cài Red

```powershell
python -m pip install --upgrade pip wheel
python -m pip install --upgrade Red-DiscordBot
redbot --version
```

## A4. Tạo instance

```powershell
redbot-setup
```

Gợi ý:

- Instance name: `imperial`
- Data path: mặc định hoặc thư mục riêng như `C:\RedData`
- Storage: JSON đủ cho bot cá nhân

Chạy lần đầu:

```powershell
redbot imperial
```

Dán credential khi Red hỏi và chọn prefix, ví dụ `!`.

> [!IMPORTANT]
> `[p]...` là lệnh gửi **trong Discord**. Không nhập `[p]cog update` hoặc `[p]restart` trong CMD/PowerShell.

## A5. Invite và role hierarchy

Mở invite URL do Red in trong console, chọn server và authorize. Sau đó:

1. Vào **Server Settings → Roles**.
2. Kéo role bot cao hơn `🏛️ Nội Các`, `🛡️ Cận Vệ` và role mà cog cần sửa.
3. Không cấp `Administrator` mặc định.

## A6. Nạp core cogs

Trong Discord, thay `!` bằng prefix thật:

```text
!load downloader general audio permissions mod modlog cleanup
!cogs
!ping
```

Nếu dùng Audio:

```text
!load audio
!llset info
!help Audio
```

## A7. Cài repository cogs

```text
!repo add red-cogs https://github.com/Dyu20705/red-cogs
!cog list red-cogs
!cog install red-cogs imperialsetup
!cog install red-cogs developmentops
!load imperialsetup
!load developmentops
!deche diagnose
!devset status
```

Cài local để phát triển:

```powershell
cd "$env:USERPROFILE"
git clone https://github.com/Dyu20705/red-cogs.git
```

Trong Discord:

```text
!addpath C:\Users\<TEN_USER>\red-cogs
!load imperialsetup
!load developmentops
```

`addpath` nhận thư mục cha chứa package cog.

## A8. Auto-restart Windows

Tạo `start-red.cmd`:

```bat
@ECHO OFF
:RED
CALL "%USERPROFILE%\redenv\Scripts\activate.bat"
python -O -m redbot imperial --no-prompt

IF %ERRORLEVEL% == 1 GOTO RESTART_RED
IF %ERRORLEVEL% == 26 GOTO RESTART_RED
EXIT /B %ERRORLEVEL%

:RESTART_RED
TIMEOUT /T 15
GOTO RED
```

Có thể đặt shortcut vào `shell:startup`, nhưng Windows sleep/hibernate vẫn làm bot mất kết nối.

# B. Ubuntu 24.04 LTS

## B1. Không chạy bằng root

Đăng nhập bằng user có `sudo`:

```bash
whoami
id
```

## B2. Cài prerequisite

```bash
sudo apt update
sudo apt -y install software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt -y install \
  python3.11 \
  python3.11-dev \
  python3.11-venv \
  git \
  openjdk-17-jre-headless \
  build-essential \
  nano
```

Kiểm tra:

```bash
python3.11 --version
git --version
java -version
```

## B3. Tạo venv và cài Red

```bash
python3.11 -m venv ~/redenv
source ~/redenv/bin/activate
python -m pip install --upgrade pip wheel
python -m pip install --upgrade Red-DiscordBot
redbot --version
redbot-setup
redbot imperial
```

Invite bot bằng URL trong console và sửa role hierarchy trong Discord.

## B4. Cài cogs

Trong Discord:

```text
!load downloader
!repo add red-cogs https://github.com/Dyu20705/red-cogs
!cog install red-cogs imperialsetup
!cog install red-cogs developmentops
!load imperialsetup
!load developmentops
!deche diagnose
!devset status
```

## B5. Chạy 24/7 bằng systemd

Kiểm tra username/path:

```bash
whoami
source ~/redenv/bin/activate
which python
```

Tạo service:

```bash
sudo nano /etc/systemd/system/red@.service
```

Thay `<USER>`:

```ini
[Unit]
Description=Red-DiscordBot instance %I
After=network-online.target
Wants=network-online.target

[Service]
Type=idle
User=<USER>
Group=<USER>
WorkingDirectory=/home/<USER>
ExecStart=/home/<USER>/redenv/bin/python -O -m redbot %I --no-prompt
Restart=on-abnormal
RestartSec=15
RestartForceExitStatus=1 26
TimeoutStopSec=30
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

Bật service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now red@imperial
systemctl status red@imperial --no-pager
journalctl -u red@imperial -n 100 --no-pager
```

Điều khiển:

```bash
sudo systemctl restart red@imperial
sudo systemctl stop red@imperial
journalctl -fu red@imperial
```

## B6. Firewall

Red chủ yếu kết nối outbound đến Discord; bot thông thường không cần public port. Nếu dùng UFW, cho phép SSH trước:

```bash
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status verbose
```

Không public managed Lavalink port.

# C. Khởi tạo server bằng ImperialSetup

Luồng an toàn:

```text
!deche diagnose
!deche audit
!deche plan
!deche reconcile CONFIRM
!deche status
```

Sau khi kiểm tra permission/backup:

```text
!deche optimize CONFIRM
!deche launch CONFIRM
!deche status
```

Hardening layer giữ overwrite của role/member ngoài blueprint. Khi nhiều channel cùng khớp tên/alias, mutation dừng để bạn xử lý ambiguity thay vì chọn ngẫu nhiên.

# D. Bật DevelopmentOps

DevelopmentOps đọc cấu hình nhạy cảm từ environment của process Red:

- `DEVELOPMENTOPS_WEBHOOK_SECRET`
- `DEVELOPMENTOPS_GITHUB_TOKEN` — tùy tính năng
- `DEVELOPMENTOPS_HOST` — mặc định `127.0.0.1`
- `DEVELOPMENTOPS_PORT` — mặc định `8765`

Giữ receiver bind loopback và đưa `/github` ra Internet qua HTTPS reverse proxy/tunnel. Sau khi đặt environment, restart Red rồi chạy:

```text
!load developmentops
!devset status
```

Xem [DEVELOPMENTOPS.md](DEVELOPMENTOPS.md).

# Kiểm tra cuối

```text
!ping
!cogs
!deche diagnose
!deche status
!devset status
!llset info
```

Checklist:

- Bot online và phản hồi.
- Role bot không dùng Administrator.
- `#bot-errors` chỉ staff/bot thấy.
- Bot Connect/Speak được trong voice music.
- Ubuntu service tự chạy lại sau reboot.
- DevelopmentOps chỉ listen loopback và webhook public dùng HTTPS.

# Nguồn chính thức

- Red install guides: <https://docs.discord.red/en/latest/install_guides/index.html>
- Windows: <https://docs.discord.red/en/latest/install_guides/windows.html>
- Ubuntu 24.04: <https://docs.discord.red/en/latest/install_guides/ubuntu-2404.html>
- Bot application/intents: <https://docs.discord.red/en/latest/bot_application_guide.html>
- Getting started: <https://docs.discord.red/en/latest/getting_started.html>
- systemd: <https://docs.discord.red/en/latest/autostart_systemd.html>
- Windows auto-restart: <https://docs.discord.red/en/latest/autostart_windows.html>
- Audio: <https://docs.discord.red/en/latest/cog_guides/audio.html>
