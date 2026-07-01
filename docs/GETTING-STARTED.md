# Khởi tạo Discord server và Red bot từ con số 0

Tài liệu này đi theo thứ tự an toàn: **test server → Discord application → bot account → invite → Red instance → ImperialSetup → production**.

## 1. Chọn mô hình triển khai

| Mô hình | Dùng khi | Ưu điểm | Hạn chế |
|---|---|---|---|
| Một Red bot | Server cá nhân nhỏ | Dễ cài và vận hành | Mọi chức năng cùng failure domain |
| Hai Red instance | Music cần tách khỏi reminders/mod | Tách reliability và permission | Tốn thêm tài nguyên |
| Production bot + test bot | Thường thử cogs hoặc tự viết code | An toàn nhất cho phát triển | Cần thêm application và test server |

Khuyến nghị: bắt đầu với **một production bot + một test bot**, không cần tạo bot riêng chỉ để phân loại channel.

## 2. Tạo test server

1. Trong Discord, chọn **Add a Server**.
2. Tạo server riêng, ví dụ `Imperial Lab`.
3. Không mời người khác trong giai đoạn thử nghiệm.
4. Bật Developer Mode khi cần sao chép ID để debug; không commit ID nhạy cảm vào repo public.

Mọi thay đổi `optimize`, community cog mới, webhook mới hoặc automation chưa kiểm chứng nên chạy ở test server trước.

## 3. Tạo Discord application và bot

Trong Discord Developer Portal:

1. Chọn **New Application**.
2. Đặt tên, ví dụ `Imperial Red`.
3. Mở trang **Bot** và tạo bot user.
4. Giữ **Public Bot** tắt nếu bot chỉ dùng cho server của bạn.
5. Giữ **Require OAuth2 Code Grant** tắt.
6. Bật ba privileged gateway intents Red yêu cầu:
   - Presence Intent;
   - Server Members Intent;
   - Message Content Intent.
7. Chỉ cung cấp bot token trực tiếp cho Red trong luồng thiết lập cục bộ.

Bot token phải được giữ bí mật. Không gửi qua Discord, ảnh chụp màn hình, issue, commit, cấu hình public hoặc script cài đặt.

## 4. Mời bot bằng quyền tối thiểu

Cấp trước các quyền cơ bản:

- View Channels;
- Send Messages;
- Embed Links;
- Attach Files;
- Read Message History;
- Add Reactions;
- Connect và Speak nếu dùng Audio;
- Manage Channels cho ImperialSetup;
- Manage Roles khi ImperialSetup phải tạo hoặc gán role.

Không bật `Administrator` mặc định. Sau khi bot vào server:

1. Mở **Server Settings → Roles**.
2. Đưa role bot lên trên các role mà nó cần tạo/chỉnh/gán.
3. Giữ role chủ server và admin con người ở trên role bot.
4. Không dùng integration-managed bot role như role quản trị con người.

## 5. Chuẩn bị cấu trúc tối thiểu

Trước khi chạy ImperialSetup, chỉ cần một channel bot nhìn thấy và trả lời được:

```text
🤖 BOOTSTRAP
└── #bot-bootstrap
```

Cho bot View Channel, Send Messages, Embed Links, Attach Files và Read Message History tại đây. Không cần dựng toàn bộ category thủ công.

## 6. Cài Red trên máy host

- [Windows 10/11](INSTALLATION.md#a-windows-1011-x86-64)
- [Ubuntu 24.04 LTS](INSTALLATION.md#b-ubuntu-2404-lts)

Khi chạy `redbot-setup`:

1. Đặt instance name rõ ràng, ví dụ `ImperialBot` hoặc `ImperialTest`.
2. JSON phù hợp với server cá nhân đơn giản.
3. Chỉ chọn PostgreSQL khi đã biết backup, restore và vận hành database.
4. Đặt data path ngoài repository Git.
5. Khởi động instance và hoàn tất cấu hình trong luồng tương tác của Red.
6. Chọn prefix ít xung đột, ví dụ `!` hoặc `?`.

> `[p]` nghĩa là prefix của bot. Các lệnh `[p]...` được gửi trong Discord, không chạy trong CMD, PowerShell hoặc Bash.

## 7. Smoke test Red

Trong Discord:

```text
[p]ping
[p]help
[p]cogs
```

Nếu bot không phản hồi, xử lý process, bot token, intents, prefix và channel permissions trước khi cài community cog.

## 8. Cài ImperialSetup

```text
[p]load downloader
[p]repo add DyuRedOps https://github.com/Dyu20705/red-cogs
[p]cog install DyuRedOps imperialsetup
[p]load imperialsetup
```

Nếu repository đã được thêm:

```text
[p]repo list
[p]cog update imperialsetup
[p]reload imperialsetup
```

## 9. Chạy flow an toàn

### Chỉ đọc

```text
[p]deche diagnose
[p]deche audit
[p]deche plan
```

Lưu báo cáo trước khi thay đổi. Nếu có duplicate hoặc ambiguous names, xử lý thủ công trước.

### Reconcile

```text
[p]deche reconcile CONFIRM
[p]deche status
```

Kiểm tra role được tạo/đổi tên, channel được di chuyển, tài nguyên lạ được giữ nguyên và bot vẫn xem được category private.

### Optimize

```text
[p]deche optimize CONFIRM
[p]deche diagnose
```

Kiểm tra permission từng category, đặc biệt `🔒 NỘI CÁC`, `🤖 BOT`, `📚 STUDY`, `💻 DEVELOPMENT`.

### Launch

```text
[p]deche launch CONFIRM
[p]deche status
```

Starter embeds chỉ được gửi vào channel trống.

## 10. Đưa sang production

Chỉ chuyển sang server chính sau khi:

- test server hoàn thành không có 403;
- role hierarchy rõ ràng;
- backup Red đã tạo;
- `plan` không có mapping bất ngờ;
- các channel private vẫn private;
- Audio, reminders, GitHub feeds và logs được route đúng nơi;
- bạn biết cách dừng bot và restore backup.

## 11. Checklist hoàn tất

- [ ] Bot token nằm ngoài Git và được lưu an toàn.
- [ ] Bot không có Administrator.
- [ ] Role bot ở đúng vị trí.
- [ ] Test server tồn tại.
- [ ] Red chạy trong virtual environment.
- [ ] Auto-start đã cấu hình.
- [ ] Backup đầu tiên đã tạo và kiểm tra archive.
- [ ] ImperialSetup audit/plan đã được lưu.
- [ ] Log channel chỉ người tin cậy nhìn thấy.
- [ ] Community cogs đã được review trước khi cài.
