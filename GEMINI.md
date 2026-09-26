# Quy tắc bắt buộc đối với AI Assistant (LUẬT CỨNG)

> File này là luật cứng của dự án MarketLink / Techwiz. Mọi AI Assistant (Claude, Gemini, ...) **phải đọc file này ở đầu mỗi phiên làm việc** và tuân thủ tuyệt đối. Luật trong file này được ưu tiên cao hơn mọi skill, hướng dẫn hay thói quen mặc định khác.

1. **KHÔNG TỰ Ý THAY ĐỔI FILE**:
   - AI tuyệt đối KHÔNG được tự ý tạo mới, đè hoặc chỉnh sửa bất kỳ file nào trong dự án (`write_to_file`, `replace_file_content`, `Write`, `Edit`, `sed -i`, ...) khi chưa được người dùng xác nhận rõ ràng.

2. **QUY TRÌNH SUY LUẬN - KHÔNG PHỎNG ĐOÁN**:
   - AI tuyệt đối KHÔNG được tự ý phỏng đoán, suy luận vô căn cứ.
   - Không được tự ý giả định những thứ không có thật và truyền tải thông tin đó cho người dùng khiến người dùng hiểu nhầm.
   - Mọi kết luận phải dựa trên nội dung thực tế đã kiểm tra (code, tài liệu, kết quả lệnh). Điều gì chưa kiểm tra được thì phải nói rõ là chưa xác minh.

3. **CHỈ HƯỚNG DẪN HOẶC TRUY VẤN**:
   - Khi người dùng hỏi hoặc yêu cầu tư vấn, AI chỉ được phép phân tích, giải thích và đưa ra mã code hướng dẫn dạng Markdown trong ô chat để người dùng tự xem và quyết định.

4. **TUÂN THỦ QUY TRÌNH HỎI Ý KIẾN, CHỈNH SỬA**:
   - Khi người dùng hỏi, yêu cầu kiểm tra code, hoặc chỉnh sửa code, phải trả lời và thông báo cho người dùng dạng "sau khi phân tích...", "tôi đã kiểm tra...", "tôi đã phát hiện...", "theo ý kiến chuyên môn của tôi..." sau đó phải trình bày phương án/kế hoạch.
   - Liệt kê các file mà AI sẽ chỉnh sửa để người dùng biết, rồi hỏi và chờ người dùng đồng ý ("Đồng ý", "Làm đi", "OK") mới được phép thực thi thao tác chỉnh sửa file.
   - Không được tự ý sửa xong rồi mới trình bày.

# Project Agent Rules

## Core Principle

Do not stop at identifying a problem.
When a defect is confirmed, fix it and verify the fix.

The task is not complete until the required verification has been executed.

## Working Mode

For non-trivial coding tasks:

1. Inspect the existing implementation.
2. Identify affected files and dependencies.
3. Create a concise implementation plan.
4. Implement the changes.
5. Run targeted tests.
6. Analyze failures.
7. Fix confirmed failures.
8. Re-run affected tests.
9. Run the relevant regression suite.
10. Run the full test suite when requested.
11. Report the final test result.

Do not declare success based only on code inspection.

## Testing

Prefer:

- targeted tests after each logical change
- regression tests after fixing a defect
- full test suite at the end of a large task

If a test fails:

- inspect the actual failure
- determine whether it is caused by the current changes
- fix the implementation when appropriate
- rerun the failing test
- continue until the verification phase is complete

Do not simply report failing tests and stop.

## Code Changes

Before modifying code:

- inspect existing architecture
- reuse existing services/selectors/serializers
- avoid unnecessary architectural changes
- do not invent APIs, models, fields, or business rules

Preserve existing behavior unless the task explicitly requires changing it.

## Security

For security-related tasks, explicitly check:

- authentication
- authorization
- object-level authorization / BOLA / IDOR
- privilege escalation
- JWT lifecycle
- refresh-token rotation
- token blacklist
- WebSocket authentication
- Redis TTL behavior
- file upload validation
- Excel formula injection
- input validation
- ownership checks
- race conditions
- transaction boundaries

Do not claim a security issue exists without inspecting the actual implementation.

## Verification Rule

Never finish a task with:

"Code looks correct."

A task is considered complete only after the applicable automated verification has been executed.

## Long-Running Tasks

For large tasks:

- continue working through multiple edit/test/fix cycles
- do not stop after the first successful test
- do not ask for confirmation between normal implementation steps
- use the terminal to execute the required verification
- preserve the task objective throughout the entire execution