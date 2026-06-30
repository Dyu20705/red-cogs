# ImperialSetup Adaptive v2.2

Phiên bản này dành cho server đã dựng một phần.

## Nguyên tắc

- Quét trước, không thay đổi ở bước audit/plan.
- Tái sử dụng role/category/channel đã có theo tên và alias.
- Có thể đổi tên chuẩn và đưa channel nhận diện được về đúng category.
- Chỉ tạo phần còn thiếu.
- Không xóa bất cứ role, category, channel hay tin nhắn nào.
- Category/channel không nhận diện được, ví dụ `MIU R|C`, được giữ nguyên.
- Nội dung mẫu chỉ được đăng vào channel hoàn toàn trống.
- Bước reconcile giữ permission hiện có.
- Bước optimize mới chuẩn hóa permission của phần thuộc blueprint.

## Cài trên Windows

Giải nén sao cho có:

```text
C:\red-cogs\
└─ imperialsetup\
   ├─ __init__.py
   ├─ blueprint.py
   ├─ imperialsetup.py
   └─ info.json
```

Trong Discord, thay `!` bằng prefix thật:

```text
!addpath C:\red-cogs
!reload imperialsetup
```

Nếu đây là lần đầu cài:

```text
!load imperialsetup
```

## Flow khuyến nghị

```text
!deche audit
!deche plan
!deche auto CONFIRM
!deche status
```

`auto` chạy lần lượt:

1. Reconcile: dùng lại phần đã dựng, tạo phần thiếu.
2. Optimize: chuẩn hóa permission và bố cục phần được nhận diện.
3. Launch: đăng starter content vào channel trống và tạo dashboard.

Có thể chạy từng bước:

```text
!deche reconcile CONFIRM
!deche optimize CONFIRM
!deche launch CONFIRM
```

## Với server trong ảnh của bạn

Cog sẽ cố gắng tái sử dụng:

- `About` → `📜 ABOUT`
- `NỘI CÁC` → `🔒 NỘI CÁC`
- `Bot` → `🤖 BOT`
- `NGỰ UYỂN` → `🌿 NGỰ UYỂN`
- `STUDY` → `📚 STUDY`
- `DEVELOPMENT` → `💻 DEVELOPMENT`
- `FEEDS` → `📰 FEEDS`
- `bot-errors` được giữ và khóa quyền đúng.
- `Nhạc Phường` được giữ và cấp Connect/Speak cho bot.
- `MIU R|C` được giữ nguyên vì mục đích chưa đủ rõ để tự gộp/xóa.

## Permission bot cần

- Manage Roles
- Manage Channels
- View Channels
- Send Messages
- Embed Links
- Attach Files
- Read Message History
- Connect
- Speak

`Manage Server` là tùy chọn; nếu có, cog sẽ đặt voice `AFK` làm AFK channel.

Không cần cấp Administrator.


## Sửa lỗi 403 Forbidden ở v2.1

Discord chỉ cho bot cấp những permission mà chính bot đang có. Bản cũ có thể cố
gán quyền quản trị bổ sung cho Nội Các/Cận Vệ hoặc channel overwrite, khiến API
trả về 403 dù Manage Roles và Manage Channels đã bật.

v2.1 tự lọc các quyền không khả dụng, hoàn thành phần còn lại thay vì dừng toàn bộ.

Nâng cấp:

```text
!reload imperialsetup
!deche audit
!deche reconcile CONFIRM
```


## v2.2: channel-aware permission checks

Discord evaluates channel overwrite changes against the bot's effective permissions
in the channel or parent category, not only the role's global permission toggles.

New command:

```text
!deche diagnose
```

It reports:

- bot top-role position
- whether every managed role is below the bot
- effective Manage Channels and Manage Roles in each category/channel
- the exact API operation, HTTP status, and Discord error code after a 403

Recommended recovery flow:

```text
!reload imperialsetup
!deche diagnose
!deche reconcile CONFIRM
```
