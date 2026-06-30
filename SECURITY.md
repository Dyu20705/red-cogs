# Security policy

## Supported scope

Security fixes target the latest `main` branch. Đây là repository cog tự host, không phải dịch vụ bot được vận hành thay cho người dùng.

## Báo cáo lỗ hổng

Không mở public issue chứa credential, private log hoặc dữ liệu server nhạy cảm. Dùng GitHub private vulnerability reporting nếu repository đã bật; nếu chưa, liên hệ chủ repository bằng kênh riêng với reproduction đã redact.

## Khi credential bị lộ

### Discord bot credential

1. Reset credential ngay trong Discord Developer Portal.
2. Dừng process Red.
3. Cập nhật credential qua luồng setup được Red hỗ trợ.
4. Kiểm tra Git history, Actions log, Discord message và screenshot.
5. Xóa credential khỏi toàn bộ history nếu đã commit; xóa file ở commit mới là chưa đủ.
6. Khởi động lại và kiểm tra owner/intents/permission.

### GitHub credential hoặc webhook secret

1. Revoke/rotate credential hoặc thay webhook secret.
2. Restart Red để process nhận environment mới.
3. Cập nhật secret tại GitHub webhook.
4. Kiểm tra delivery/API audit log và repository changes.
5. Giảm scope/repository access trước khi cấp credential mới.

## ImperialSetup permission model

Không cần Discord `Administrator`. Cấp đúng permission và đặt role bot cao hơn role cần quản lý.

Trước `optimize`:

```text
[p]deche diagnose
[p]deche audit
[p]deche plan
```

Hardening layer giữ overwrite ngoài ownership boundary. Blueprint-owned overwrite vẫn được chuẩn hóa có chủ đích.

## DevelopmentOps threat model

- Receiver mặc định phải bind `127.0.0.1`.
- Public webhook phải đi qua HTTPS reverse proxy/tunnel có kiểm soát.
- Mọi GitHub payload phải có HMAC signature hợp lệ.
- Không log raw credential.
- Dùng fine-grained GitHub credential, giới hạn repository và quyền.
- Nên rate-limit `/github` ở reverse proxy.
- Không mở `/github` hoặc `/healthz` qua port raw nếu không cần.
- Forum sync có thể chuyển nội dung, attachment URL và creator ID sang GitHub; chỉ bật ở forum đã công bố chính sách này.

## Community cog và dependency

- Cài package trong Red virtual environment, không cài global bằng sudo.
- Đọc source, `info.json`, requirements và data statement trước khi cài cog ngoài.
- Test update có rủi ro trên bot/server phụ.
- Không public managed Lavalink port.

## Dữ liệu lưu trữ

- `imperialsetup`: không persist end-user data; đọc guild structure/permission khi chạy command.
- `developmentops`: lưu guild/channel/thread IDs, repository name, mapping Forum/Issue, PR thread và schedule trong Red Config.
- Credential chỉ được đọc từ process environment.

Backup Red Config là dữ liệu quản trị. Mã hóa/giới hạn quyền truy cập và không commit vào repository.
