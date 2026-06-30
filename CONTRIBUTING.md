# Contributing

## Development setup

Dùng Python 3.11+:

```bash
git clone https://github.com/Dyu20705/red-cogs.git
cd red-cogs
python scripts/validate_repo.py
python -m unittest discover -s tests -v
python -m compileall -q imperialsetup developmentops scripts tests
```

Các check trên không cần Red. Runtime behavior vẫn phải test trên bot/server phát triển riêng.

## Workflow

1. Tạo branch có scope rõ.
2. Cập nhật docs cùng behavior.
3. Thêm unit test cho logic có thể tách khỏi Discord/Red.
4. Chạy validator, tests và compile.
5. Test cog load/unload/reload.
6. Test permission/webhook failure path.
7. Mở PR có risk, evidence và rollback note.

## ImperialSetup rules

- Canonical name/alias không được collision sau normalization.
- Không xóa resource chỉ dựa trên tên.
- Không ghi đè custom overwrite ngoài ownership boundary.
- Starter content phải idempotent và không đè message có sẵn.
- Mutating command phải có confirmation rõ.

## DevelopmentOps rules

- Không commit credentials hoặc payload thật.
- External content phải dùng `AllowedMentions.none()` khi đăng.
- Webhook verification phải chạy trước JSON dispatch.
- Network request cần timeout/error handling.
- Managed labels/mapping phải giữ dữ liệu ngoài ownership boundary.
- Thay đổi data handling phải cập nhật `end_user_data_statement` và docs.

## Commit style

```text
feat: add profile-aware blueprint loading
fix: preserve custom channel overwrites
docs: document DevelopmentOps reverse proxy
test: cover overwrite ownership merge
```

## PR checklist

- [ ] Không có credential hoặc Red runtime data.
- [ ] `python scripts/validate_repo.py` pass.
- [ ] Unit tests pass.
- [ ] Python compile pass.
- [ ] README/docs đúng với command thực tế.
- [ ] Permission/data-transfer risk được giải thích.
- [ ] Runtime test trên development server hoàn tất.
- [ ] Có rollback path.
