"""Declarative blueprint for the Quân chủ chuyên chế Discord server."""

ROLE_SPECS = [
    {
        "name": "👑 Quân Vương",
        "aliases": ["Quân Vương", "Quan Vuong"],
        "colour": 0xF1C40F,
        "hoist": True,
        "permissions": {},
        "assign_owner": True,
    },
    {
        "name": "🏛️ Nội Các",
        "aliases": ["Nội Các", "Noi Cac"],
        "colour": 0x9B59B6,
        "hoist": True,
        "permissions": {
            "manage_channels": True,
            "manage_messages": True,
            "manage_threads": True,
            "manage_webhooks": True,
            "moderate_members": True,
            "kick_members": True,
        },
    },
    {
        "name": "🛡️ Cận Vệ",
        "aliases": ["Cận Vệ", "Can Ve"],
        "colour": 0x3498DB,
        "hoist": True,
        "permissions": {
            "manage_messages": True,
            "manage_threads": True,
            "moderate_members": True,
            "kick_members": True,
        },
    },
    {
        "name": "👤 Thần Dân",
        "aliases": ["Thần Dân", "Than Dan", "Member"],
        "colour": 0x95A5A6,
        "hoist": False,
        "permissions": {},
    },
]


CATEGORIES = [
    {
        "name": "📜 ABOUT",
        "aliases": ["About"],
        "policy": "public_read_only",
        "channels": [
            {
                "type": "text",
                "name": "welcome",
                "topic": "Cổng vào của Quân chủ chuyên chế.",
                "policy": "inherit",
                "seed": {
                    "title": "Chào mừng đến Quân chủ chuyên chế",
                    "description": (
                        "Đây là server cá nhân dành cho trò chuyện, nghe nhạc, "
                        "học tập và phát triển dự án.\n\n"
                        "Đọc **#rules**, xem **#server-guide**, rồi dùng các khu vực phù hợp."
                    ),
                },
            },
            {
                "type": "text",
                "name": "rules",
                "topic": "Nội quy ngắn gọn của server.",
                "policy": "inherit",
                "seed": {
                    "title": "📜 Sắc lệnh hoàng gia",
                    "description": (
                        "1. Tôn trọng mọi người.\n"
                        "2. Không spam, phá hoại hoặc lạm dụng bot.\n"
                        "3. Đăng nội dung đúng kênh.\n"
                        "4. Không chia sẻ token, mật khẩu hay dữ liệu riêng tư.\n"
                        "5. Quân Vương có quyền cập nhật nội quy khi cần."
                    ),
                },
            },
            {
                "type": "text",
                "name": "announcements",
                "topic": "Thông báo và thay đổi quan trọng.",
                "policy": "inherit",
                "seed": {
                    "title": "📢 Bảng cáo thị",
                    "description": "Các cập nhật quan trọng của server sẽ xuất hiện tại đây.",
                },
            },
            {
                "type": "text",
                "name": "server-guide",
                "topic": "Cách dùng server và Red DiscordBot.",
                "policy": "inherit",
                "seed": {
                    "title": "🧭 Hướng dẫn sử dụng",
                    "description": (
                        "• **BOT**: gọi lệnh và yêu cầu nhạc.\n"
                        "• **NGỰ UYỂN**: trò chuyện và voice.\n"
                        "• **STUDY**: học tập, tài liệu và tiến độ.\n"
                        "• **DEVELOPMENT**: dự án, code review và lỗi.\n"
                        "• **FEEDS**: cập nhật tự động.\n\n"
                        "Trong tài liệu Red, `[p]` là prefix. Nếu prefix là `!`, "
                        "hãy dùng `!help`, không nhập nguyên `[p]help`."
                    ),
                },
            },
        ],
    },
    {
        "name": "🔒 NỘI CÁC",
        "aliases": ["NỘI CÁC", "NOI CAC"],
        "policy": "private_staff",
        "channels": [
            {
                "type": "text",
                "name": "noi-cac-chat",
                "topic": "Trao đổi riêng của Quân Vương và Nội Các.",
                "policy": "inherit",
                "seed": {
                    "title": "🏛️ Phòng Nội Các",
                    "description": "Khu vực riêng để quản trị và bàn việc server.",
                },
            },
            {
                "type": "text",
                "name": "server-todo",
                "topic": "Danh sách việc cần làm cho server.",
                "policy": "inherit",
                "seed": {
                    "title": "✅ Việc cần xử lý",
                    "description": "Ghim roadmap, lỗi cần sửa và ý tưởng cải tiến tại đây.",
                },
            },
            {
                "type": "text",
                "name": "server-config",
                "topic": "Ghi chú cấu hình không chứa bí mật.",
                "policy": "inherit",
                "seed": {
                    "title": "⚙️ Sổ cấu hình",
                    "description": (
                        "Lưu prefix, danh sách cog và ghi chú vận hành.\n"
                        "**Không đăng token bot, API key hoặc mật khẩu.**"
                    ),
                },
            },
            {
                "type": "text",
                "name": "audit-and-mod-log",
                "topic": "Nhật ký quản trị và kiểm duyệt.",
                "policy": "inherit",
            },
            {
                "type": "voice",
                "name": "Phòng Nội Các",
                "policy": "inherit",
                "user_limit": 10,
            },
        ],
    },
    {
        "name": "🤖 BOT",
        "aliases": ["Bot"],
        "policy": "public_chat",
        "channels": [
            {
                "type": "text",
                "name": "bot-commands",
                "topic": "Dùng lệnh Red DiscordBot tại đây.",
                "policy": "inherit",
                "slowmode_delay": 1,
                "seed": {
                    "title": "🤖 Trung tâm điều khiển bot",
                    "description": (
                        "Bắt đầu với `!help` nếu prefix của bot là `!`.\n"
                        "Lệnh được gửi trong Discord, không phải cửa sổ CMD."
                    ),
                },
            },
            {
                "type": "text",
                "name": "music-request",
                "topic": "Yêu cầu nhạc và quản lý hàng đợi.",
                "policy": "inherit",
                "seed": {
                    "title": "🎵 Yêu cầu nhạc",
                    "description": (
                        "Vào **Nhạc Phường**, sau đó dùng lệnh Audio của Red tại kênh này.\n"
                        "Dùng `!help Audio` để xem đúng lệnh trên phiên bản đang cài."
                    ),
                },
            },
            {
                "type": "text",
                "name": "now-playing",
                "topic": "Trạng thái nhạc hiện tại do bot đăng.",
                "policy": "bot_post_only",
            },
            {
                "type": "text",
                "name": "bot-errors",
                "topic": "Lỗi của bot; chỉ Nội Các và bot nhìn thấy.",
                "policy": "private_staff_bot",
                "seed": {
                    "title": "🚨 Nhật ký lỗi bot",
                    "description": "Dùng kênh này để giữ traceback, cảnh báo và thông tin chẩn đoán.",
                },
            },
            {
                "type": "text",
                "name": "bot-logs",
                "topic": "Log vận hành của bot.",
                "policy": "private_staff_bot",
            },
        ],
    },
    {
        "name": "🌿 NGỰ UYỂN",
        "aliases": ["NGỰ UYỂN", "NGU UYEN"],
        "policy": "public_chat",
        "channels": [
            {
                "type": "text",
                "name": "dai-sanh",
                "topic": "Trò chuyện chung.",
                "policy": "inherit",
                "seed": {
                    "title": "🌿 Đại sảnh",
                    "description": "Khu trò chuyện chung của server.",
                },
            },
            {
                "type": "text",
                "name": "media-and-memes",
                "topic": "Ảnh, video và meme.",
                "policy": "inherit",
            },
            {
                "type": "text",
                "name": "chia-se-hom-nay",
                "topic": "Chia sẻ việc đã làm, điều thú vị hoặc nhật ký ngắn.",
                "policy": "inherit",
            },
            {
                "type": "voice",
                "name": "🎧 Nhạc Phường",
                "aliases": ["Nhạc Phường"],
                "policy": "inherit",
                "user_limit": 0,
            },
            {
                "type": "voice",
                "name": "🍵 Phòng Trà",
                "aliases": ["Phòng Trà"],
                "policy": "inherit",
                "user_limit": 10,
            },
            {
                "type": "voice",
                "name": "🔇 AFK",
                "aliases": ["AFK"],
                "policy": "inherit",
                "user_limit": 0,
            },
        ],
    },
    {
        "name": "📚 STUDY",
        "aliases": ["STUDY"],
        "policy": "public_chat",
        "channels": [
            {
                "type": "text",
                "name": "study-chat",
                "topic": "Trao đổi học tập.",
                "policy": "inherit",
                "seed": {
                    "title": "📚 Hàn Lâm Viện",
                    "description": "Trao đổi bài học, mục tiêu và tiến độ tại đây.",
                },
            },
            {
                "type": "text",
                "name": "questions",
                "topic": "Đặt câu hỏi học tập; nên dùng thread cho từng câu hỏi.",
                "policy": "inherit",
            },
            {
                "type": "text",
                "name": "resources",
                "topic": "Tài nguyên học tập đã chọn lọc.",
                "policy": "staff_post_only",
                "seed": {
                    "title": "📖 Thư khố",
                    "description": "Tài liệu học tập đã được chọn lọc sẽ được ghim tại đây.",
                },
            },
            {
                "type": "text",
                "name": "study-log",
                "topic": "Nhật ký học mỗi ngày.",
                "policy": "inherit",
            },
            {
                "type": "text",
                "name": "goals-and-progress",
                "topic": "Mục tiêu tuần, tháng và tiến độ.",
                "policy": "inherit",
            },
            {
                "type": "voice",
                "name": "Study Room",
                "policy": "inherit",
                "user_limit": 10,
            },
            {
                "type": "voice",
                "name": "Pomodoro",
                "policy": "inherit",
                "user_limit": 10,
            },
        ],
    },
    {
        "name": "💻 DEVELOPMENT",
        "aliases": ["DEVELOPMENT"],
        "policy": "public_chat",
        "channels": [
            {
                "type": "text",
                "name": "dev-chat",
                "topic": "Trao đổi lập trình và hệ thống.",
                "policy": "inherit",
                "seed": {
                    "title": "💻 Công Bộ",
                    "description": "Không gian cho code, hệ thống, DevOps và dự án cá nhân.",
                },
            },
            {
                "type": "text",
                "name": "arcaea-viewer",
                "topic": "Thảo luận dự án Arcaea Viewer.",
                "policy": "inherit",
            },
            {
                "type": "text",
                "name": "code-review",
                "topic": "Mỗi yêu cầu review nên mở một thread riêng.",
                "policy": "inherit",
            },
            {
                "type": "text",
                "name": "bugs-and-ideas",
                "topic": "Lỗi, tính năng và ý tưởng cải tiến.",
                "policy": "inherit",
            },
            {
                "type": "text",
                "name": "snippets",
                "topic": "Đoạn code, lệnh và ghi chú kỹ thuật ngắn.",
                "policy": "inherit",
            },
            {
                "type": "text",
                "name": "github-feed",
                "topic": "Commit, issue, pull request và release từ GitHub.",
                "policy": "bot_post_only",
            },
            {
                "type": "voice",
                "name": "Dev Room",
                "policy": "inherit",
                "user_limit": 10,
            },
        ],
    },
    {
        "name": "📰 FEEDS",
        "aliases": ["FEEDS"],
        "policy": "public_read_only",
        "channels": [
            {
                "type": "text",
                "name": "all-feeds",
                "topic": "Thông báo tự động từ GitHub, YouTube và nguồn khác.",
                "policy": "bot_post_only",
                "seed": {
                    "title": "📰 Dòng tin",
                    "description": "Các integration và bot có thể đăng cập nhật tự động tại đây.",
                },
            },
        ],
    },
]
