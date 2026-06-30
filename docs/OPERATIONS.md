# Vận hành, cập nhật, backup và xử lý lỗi

## 1. Hai cách cài cog

### Downloader — khuyến nghị cho vận hành

```text
[p]load downloader
[p]repo add red-cogs https://github.com/Dyu20705/red-cogs
[p]cog install red-cogs imperialsetup
[p]cog install red-cogs developmentops
[p]load imperialsetup
[p]load developmentops
```

Cập nhật:

```text
[p]cog update
[p]reload imperialsetup
[p]reload developmentops
```

### `addpath` — dùng khi phát triển local

```text
[p]addpath /path/to/red-cogs
[p]load imperialsetup
[p]load developmentops
```

Sau khi sửa code:

```text
[p]reload imperialsetup
[p]reload developmentops
```

> [!IMPORTANT]
> Đây là lệnh Discord. Không nhập `[p]reload` trong CMD/PowerShell/bash.

## 2. Quy trình thay đổi an toàn

1. Làm trên branch riêng.
2. Chạy validator/test/compile.
3. Backup Red data.
4. Chạy `diagnose`, `audit`, `plan`.
5. Chạy `reconcile` trước.
6. Kiểm tra thủ công trước `optimize`.
7. Chạy `status` sau thay đổi.

```bash
python scripts/validate_repo.py
python -m unittest discover -s tests -v
python -m compileall -q imperialsetup developmentops scripts tests
```

Trong Discord:

```text
[p]deche diagnose
[p]deche audit
[p]deche plan
[p]deche reconcile CONFIRM
[p]deche status
[p]deche optimize CONFIRM
[p]deche launch CONFIRM
```

## 3. Backup Red

Tìm data path:

```text
[p]datapath
```

Nguyên tắc:

- Dừng bot trước khi copy toàn bộ data path.
- Không commit data path, database hoặc backup.
- Giữ ít nhất một bản backup ngoài máy chạy bot.
- Kiểm tra archive có thể đọc, không chỉ kiểm tra file tồn tại.

### Windows

1. Trong Discord: `[p]shutdown`.
2. Copy data path sang thư mục backup có timestamp.
3. Khởi động Red lại.

Ví dụ PowerShell, thay `$Source`:

```powershell
$Source = "C:\RedData"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Destination = "$env:USERPROFILE\RedBackups\red-$Stamp"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Copy-Item -Recurse -Force "$Source\*" $Destination
```

### Ubuntu

```bash
sudo systemctl stop red@imperial
mkdir -p ~/red-backups
STAMP=$(date +%Y%m%d-%H%M%S)
tar -C /path/to -czf ~/red-backups/red-$STAMP.tar.gz red-data-directory
sudo systemctl start red@imperial
tar -tzf ~/red-backups/red-$STAMP.tar.gz | head
```

## 4. Restore

1. Dừng bot.
2. Đổi tên data path hiện tại, không xóa ngay.
3. Giải nén/copy backup vào đúng vị trí.
4. Sửa owner/permission file.
5. Khởi động, đọc log và kiểm tra cogs.

Ubuntu ví dụ:

```bash
sudo systemctl stop red@imperial
mv /path/to/red-data /path/to/red-data.before-restore
tar -xzf ~/red-backups/red-YYYYMMDD-HHMMSS.tar.gz -C /path/to
sudo chown -R <USER>:<USER> /path/to/red-data
sudo systemctl start red@imperial
journalctl -u red@imperial -n 100 --no-pager
```

Sau restore:

```text
[p]cogs
[p]deche status
[p]devset status
[p]llset info
```

DevelopmentOps lưu channel/thread/repository mapping trong Red Config. Restore sang server khác có thể làm ID cũ không còn hợp lệ; cần cấu hình lại.

## 5. Cập nhật Red

Backup và đọc changelog trước. Trong venv:

### Windows

```powershell
& "$env:USERPROFILE\redenv\Scripts\Activate.ps1"
redbot-update
```

### Ubuntu

```bash
source ~/redenv/bin/activate
redbot-update
```

Sau đó khởi động Red và cập nhật community cogs:

```text
[p]cog update
```

Không cập nhật Red và toàn bộ cogs ngay trước sự kiện quan trọng.

## 6. Log và health

### Red/Discord

```text
[p]ping
[p]cogs
[p]deche diagnose
[p]deche audit
[p]deche status
[p]devset status
[p]llset info
```

### Ubuntu

```bash
systemctl status red@imperial --no-pager
journalctl -u red@imperial -n 200 --no-pager
journalctl -fu red@imperial
curl -fsS http://127.0.0.1:8765/healthz
```

### Windows

Chạy Red từ PowerShell để xem traceback. Redact credential, webhook URL và dữ liệu riêng trước khi chia sẻ log.

## 7. Lỗi thường gặp

### `'[p]cog' is not recognized...`

Bạn đang nhập lệnh Discord vào terminal. Gửi lệnh trong channel bot nhìn thấy và thay `[p]` bằng prefix thật.

### Bot không phản hồi

Kiểm tra theo thứ tự:

1. Process Red còn chạy.
2. Bot online.
3. Message Content Intent đã bật.
4. Prefix đúng.
5. Bot có View Channel/Send Messages.
6. Console không có traceback.

### `403 Forbidden / Missing Access`

```text
[p]deche diagnose
```

Kiểm tra role hierarchy, effective `Manage Channels`, `Manage Roles`, category deny và integration-managed roles. Không giải quyết mặc định bằng `Administrator`.

### Audio không chạy

```bash
java -version
```

```text
[p]load audio
[p]llset info
[p]audioset restart
[p]help Audio
```

Không public Lavalink port. Với nhiều Audio bot trên cùng host, thiết kế unmanaged Lavalink riêng thay vì đổi port ngẫu nhiên.

### DevelopmentOps receiver không chạy

- Environment phải nằm trong **đúng process Red**.
- Restart process sau khi đổi environment.
- Kiểm tra port và health endpoint.
- Giữ bind loopback.

```bash
ss -ltnp | grep 8765
curl -i http://127.0.0.1:8765/healthz
```

### GitHub webhook trả 403

- Secret GitHub và process Red phải giống hệt.
- Reverse proxy không được sửa body.
- Header signature phải có.
- Xem GitHub delivery và Red log đã redact.

## 8. Rollback code

Với clone local:

```bash
git log --oneline --decorate -n 10
git switch --detach <GOOD_COMMIT>
```

Trong Discord:

```text
[p]reload imperialsetup
[p]reload developmentops
```

Quay lại branch:

```bash
git switch main
git pull --ff-only
```

## 9. Rotate DevelopmentOps credentials

1. Tạo secret/credential mới.
2. Cập nhật process environment hoặc systemd EnvironmentFile.
3. Cập nhật GitHub webhook.
4. Restart Red.
5. Gửi ping/test delivery.
6. Xác nhận secret cũ không còn được chấp nhận.

`reload developmentops` không thay environment của process đã chạy.

## 10. Checklist định kỳ

Hàng tuần:

- Xem log lỗi và dung lượng ổ.
- Chạy `deche status` và `devset status`.
- Kiểm tra Audio/Lavalink.
- Review cog update trước khi áp dụng.

Hàng tháng:

- Backup và thử đọc archive.
- Review role hierarchy.
- Kiểm tra credential không nằm trong repo/log.
- Chạy validator/tests.

Sau thay đổi lớn:

- Backup.
- Test trên bot/server phụ.
- Chạy `diagnose → audit → plan`.
- Kiểm tra custom overwrite sau `optimize`.
