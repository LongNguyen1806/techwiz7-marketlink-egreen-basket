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

5. **PHÂN ĐỊNH PHẠM VI TEST (SCOPE-AWARE TESTING & TOKEN OPTIMIZATION)**:
   - **Khi làm việc trên Frontend (`frontend/`):**
     - TUYỆT ĐỐI KHÔNG chạy kiểm tra backend (`pytest`, `python manage.py test`,...). Việc chạy pytest backend khi đang làm việc ở frontend là hoàn toàn vô nghĩa, làm tốn thời gian và gây lãng phí nghiêm trọng token ngữ cảnh.
     - Chỉ thực hiện kiểm tra tương thích cho frontend: ví dụ `npm run build` hoặc build check khi cần xác thực.
   - **Khi làm việc trên Backend (`backend/`):**
     - Chỉ chạy đúng file test mục tiêu liên quan trực tiếp đến module/tính năng đang làm (ví dụ: `pytest backend/.../test_target.py -q`).
     - KHÔNG tự ý chạy toàn bộ test suite trừ khi người dùng yêu cầu rõ ràng.
   - Luôn sử dụng cờ rút gọn output (`-q`) để tránh in hàng trăm dòng log làm tràn context window.

