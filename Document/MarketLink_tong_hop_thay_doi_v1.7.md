# MarketLink — Tóm tắt thay đổi tài liệu (v1.7)

> Chỉ ghi **nội dung mới** sau khi cập nhật.
> Tài liệu gốc: `Document/doc/MarketLink_requirement_analysis_ok (5).md` (D-001 → D-039).
> Mục 1 → 7 tóm tắt v1.7 (D-029 → D-035). Thay đổi v1.9 (D-037 → D-039 và các thay đổi của nhánh Admin) tóm tắt ở **mục 8**. Chi tiết v1.8 (D-036) xem change log §8 của tài liệu gốc.
> Các file đã đồng bộ: `MarketLink_requirement_analysis_ok (5).md`, `MarketLink_Implementation_Notes.md`, `MarketLink_phan_cong(new).md`, `Document/skill/SKILL.md`, `Document/skill/django-backend_skill.md`.

---

## 1. Quyết định mới

| Mã | Chủ đề | Nội dung mới |
| :---: | :--- | :--- |
| D-029 | Tồn kho, hết hạn, khách không đến | Khách đặt đơn **không trừ kho**, chỉ kiểm tra còn đủ. **Farmer duyệt đơn mới trừ kho**; thiếu hàng thì báo lỗi, đơn vẫn chờ duyệt. Chỉ cộng trả kho cho đơn đã bị trừ. Đơn chờ duyệt quá giờ nhận tự **hết hạn**: không đổi kho, không tính lỗi cho khách. **Khách không đến**: Farmer bấm ngay khi hết khung nhận, hàng trả về kho online, khách bị tính 1 lần vào cờ At risk; đã báo "Không đến" thì không thể Hoàn thành. Farmer được từ chối đơn đã duyệt tới **giờ bắt đầu nhận**, bắt buộc lý do, có tùy chọn đánh dấu hết hàng |
| D-030 | Sửa đơn & yêu cầu thay đổi | Đơn **chờ duyệt**: khách sửa, áp dụng ngay. Đơn **đã duyệt**: khách gửi **yêu cầu thay đổi**, đơn giữ nguyên nội dung cũ. Farmer chọn **Chấp nhận** (trừ / trả chênh lệch kho), **Giữ đơn cũ**, hoặc **Hủy cả đơn**. Gửi yêu cầu trước giờ chốt; ngày nhận mới từ hôm nay đến 7 ngày tới; Farmer không xử lý tới giờ nhận thì yêu cầu tự hủy; mỗi đơn chỉ 1 yêu cầu đang chờ. Món thêm / tăng phải đang bán công khai. Chỉ chính chủ đơn được sửa |
| D-031 | Ngày hoạt động của Farmer | Khai **khi đăng ký**, bắt buộc ≥ 1 ngày, sửa được ở hồ sơ sạp. Khung giờ nhận và ngày khách chọn phải vừa là ngày chợ họp vừa là ngày hoạt động của Farmer. Bỏ một ngày thì khung giờ ngày đó tự tắt; còn đơn mở vào thứ đó thì bị chặn |
| D-032 | Tọa độ Farmer | Hệ thống **tự tra tọa độ từ địa chỉ** (OpenStreetMap Nominatim) khi đăng ký / đổi địa chỉ. Tra không được thì để trống, dùng vị trí chợ. Farmer có thể kéo ghim để chỉnh, không bắt buộc |
| D-033 | Quyền Admin với đơn | Admin **không** hủy / sửa từng đơn. Chỉ khi đình chỉ Farmer hoặc khóa khách thì hệ thống tự đóng đơn mở, hoàn kho đơn đã duyệt / sẵn sàng. Lý do Admin nhập chỉ lưu nội bộ, không vào lịch sử đơn và email |
| D-034 | Phạm vi | **Mọi tính năng trong tài liệu đều bắt buộc**: thông báo in-app + email, yêu thích, đặt lại nhanh, cảnh báo có hàng lại, chatbot AI. Bỏ nhóm "Điểm cộng" |
| D-035 | "Track Deliveries" | Hiểu là khách theo dõi trạng thái đơn nhận tại chợ và tình trạng còn hàng (đề bài loại trừ giao hàng) |

---

## 2. Vòng đời đơn hàng (FSM) và tồn kho

| Cạnh | Chuyển trạng thái | Quy định mới | Tồn kho |
| :---: | :--- | :--- | :--- |
| T1 | Tạo → Chờ duyệt | Chỉ kiểm tra còn hàng; tối đa 10 đơn chờ duyệt chưa qua giờ nhận | Không đổi |
| T2 | Chờ duyệt → Đã duyệt | Trước giờ bắt đầu nhận; thiếu hàng thì báo lỗi | **Trừ** |
| T3 | Chờ duyệt → Từ chối | Lý do bắt buộc | Không đổi |
| T4 | Đã duyệt → Từ chối | Tới **trước giờ bắt đầu nhận** (không khóa nút sớm hơn); cũng là "Hủy cả đơn" khi có yêu cầu thay đổi | Cộng trả |
| T5 | Chờ duyệt → Khách hủy | Trước giờ chốt | Không đổi |
| T6 | Đã duyệt → Khách hủy | Trước giờ chốt | Cộng trả |
| ~~T7~~ | ~~Đã duyệt → Chờ duyệt~~ | **Bãi bỏ** — thay bằng yêu cầu thay đổi | — |
| T8 | Chờ duyệt → Hết hạn | Quét lười khi qua giờ bắt đầu nhận; không tính lỗi khách | Không đổi |
| T9 | Đã duyệt → Sẵn sàng | Sau giờ chốt; bị chặn khi còn yêu cầu thay đổi đang chờ | Không đổi |
| T10 | Sẵn sàng → Hoàn thành | Khách nhận hàng và trả tiền | Không đổi |
| T11 | Sẵn sàng → Không đến | Sau khi hết khung nhận | **Cộng trả** |
| T12 | Sẵn sàng → Từ chối (Admin) | Tự động khi đình chỉ Farmer | Cộng trả |
| T13 | Sẵn sàng → Hủy (Admin) | Tự động khi khóa khách; báo Farmer hàng đã trả về kho online | Cộng trả |
| **T14** | **Đã duyệt → Không đến** | **Mới**: sau khi hết khung nhận (Farmer chưa kịp bấm Sẵn sàng) | Cộng trả |

- Mẫu tồn kho tuần: `tồn kho mới = mẫu − số đang giữ`; "đang giữ" chỉ gồm đơn **đã duyệt / sẵn sàng chưa qua giờ nhận**. Đơn chờ duyệt chỉ hiện để đối soát.
- Cờ **At risk** của khách chỉ đếm đơn **Không đến**, không đếm đơn Hết hạn.
- Cảnh báo có hàng lại chỉ gửi khi Farmer chủ động nạp hàng; không gửi khi kho tăng do hủy / từ chối / không đến / Admin can thiệp.

---

## 3. Cơ sở dữ liệu

| Hạng mục | Nội dung mới |
| :--- | :--- |
| `farmer_profiles.operating_days` | Cột JSON mới: danh sách ngày hoạt động (1–7), ≥ 1 ngày (D-031) |
| `orders.pending_change` | Cột JSON mới: yêu cầu thay đổi đang chờ, NULL khi không có (D-030) |
| Số bảng | Giữ nguyên **24 bảng**, không thêm bảng |
| `products.stock_quantity` | Nghĩa mới: tồn kho khả dụng sau khi trừ đơn **đã duyệt** |
| Trường tính | `held_quantity` = đơn đã duyệt / sẵn sàng; thêm `pending_quantity` = đơn chờ duyệt (đối soát) |
| `order_status_history` | Mã cạnh T1–T6, T8–T14; sửa đơn chờ duyệt và sự kiện yêu cầu thay đổi ghi `transition = NULL` |
| Khóa dòng sản phẩm | Chỉ khóa khi trừ / cộng kho (duyệt đơn, chấp nhận thay đổi, hủy / từ chối / không đến đơn đã duyệt). Tạo đơn và sửa đơn chỉ đọc |
| Quét lười | Chạy ở transaction riêng, trước checkout / mẫu tuần; tự hủy thêm yêu cầu thay đổi quá hạn |

---

## 4. API

| Mã | Nội dung mới |
| :--- | :--- |
| AU-02 | Đăng ký Farmer thêm `operating_days` (bắt buộc); tự tra tọa độ sau khi tạo tài khoản |
| PU-01 | Trả `max_placed_orders_per_customer: 10` (bỏ giới hạn theo Farmer) |
| PU-05, PU-06 | Lọc "Farmer có mặt ngày X" theo ngày hoạt động và khung giờ đang bật |
| PU-08 | Chỉ trả ngày là ngày chợ họp **và** ngày hoạt động của Farmer |
| CU-04 | Checkout không khóa, không trừ kho; đếm giới hạn bỏ đơn đã qua giờ nhận |
| CU-07 | Đơn chờ duyệt: áp dụng ngay. Đơn đã duyệt: lưu yêu cầu thay đổi |
| FA-02, FA-03 | Hồ sơ Farmer có `operating_days`; đổi địa chỉ thì tra lại tọa độ; bỏ ngày hoạt động có thể bị chặn nếu còn đơn mở |
| FA-08, FA-09 | Khung giờ phải thuộc ngày hoạt động của Farmer |
| FA-17 | Thêm `pending_quantity`; "đang giữ" theo quy định mới |
| FA-19 | Sắp xếp theo tab (chờ duyệt: đặt trước lên trước; đã xác nhận / sẵn sàng: giờ nhận gần nhất lên trước; lịch sử: mới nhất lên trước); thêm lọc `change_requested` |
| FA-20 | Thêm đếm `change_requests` |
| FA-23 | Duyệt đơn trừ kho; thêm lỗi `INSUFFICIENT_STOCK` |
| FA-24 | Từ chối tới trước giờ bắt đầu nhận; thêm tùy chọn `mark_sold_out`; bỏ lỗi `CUTOFF_PASSED` |
| FA-27 | "Không đến" cho cả đơn đã duyệt (T14) và đơn sẵn sàng (T11); cộng trả kho |
| **FA-34** | **Mới**: Farmer chấp nhận yêu cầu thay đổi |
| **FA-35** | **Mới**: Farmer từ chối yêu cầu thay đổi (giữ đơn cũ) |
| Chi tiết đơn | Thêm `pending_change`, `has_pending_change`; `allowed_actions` thêm `REQUEST_CHANGE`, `APPROVE_CHANGE`, `REJECT_CHANGE` |
| Thông báo | Thêm `ORDER_CHANGE_APPROVED`, `ORDER_CHANGE_REJECTED` (gửi khách, in-app) |
| Mã lỗi | Cập nhật ý nghĩa: `INSUFFICIENT_STOCK`, `CUTOFF_PASSED`, `PICKUP_ALREADY_STARTED`, `PICKUP_NOT_ENDED`, `SLOT_NOT_AVAILABLE`, `RESOURCE_IN_USE`, `FAILED_PRECONDITION` (không thêm mã mới) |
| Kiểm thử | Sửa CT-07, CT-13; thêm CT-20 → CT-23 |

---

## 5. Màn hình

| Màn hình | Nội dung mới |
| :--- | :--- |
| G-11 Đăng ký Farmer | Thêm ô Ngày hoạt động (bắt buộc); không nhập tọa độ |
| G-06 Hồ sơ Farmer công khai | Chip ngày hoạt động; bản đồ vị trí Farmer (nếu tra được) |
| C-02 Checkout | Ngày chọn thuộc ngày chợ họp và ngày hoạt động; ghi chú "kho chỉ giữ khi Farmer duyệt" |
| C-05 Chi tiết đơn (khách) | Khối "Change request" và badge "Change requested" |
| C-06 Sửa đơn | Đơn đã duyệt → nút "Send change request"; ngày nhận từ hôm nay đến 7 ngày tới |
| F-02 Đơn hàng Farmer | Sắp xếp theo tab; lọc "Change requested"; cảnh báo "Not enough stock" |
| F-03 Chi tiết đơn (Farmer) | Khối "Change request" 3 nút; hộp thoại Từ chối nhắc gọi khách + tùy chọn hết hàng; hộp thoại Không đến báo hàng trả về kho |
| F-04 Sản phẩm | Thêm cột "Chờ duyệt" (đối soát) |
| F-06 Mẫu tuần | Cột "Đang giữ" theo quy định mới + cột "Chờ duyệt" |
| F-07 Chợ & khung giờ | Chọn thứ chỉ trong ngày chợ họp ∩ ngày hoạt động; chip ngày hoạt động lấy từ hồ sơ |
| F-08 Hồ sơ sạp | Ô Ngày hoạt động; ghim bản đồ chỉ để chỉnh; nhắc khi không tra được vị trí |
| A-02, A-04 | Câu cảnh báo: chỉ hoàn kho đơn đã duyệt |

---

## 6. Phân công (`MarketLink_phan_cong(new).md`)

| Hạng mục | Nội dung mới |
| :--- | :--- |
| Giờ công | Bỏ toàn bộ cột và số giờ |
| Nguyên tắc | Thao tác do role nào thực hiện thì nhánh role đó làm |
| Yêu cầu thay đổi | Gửi yêu cầu (CU-07) → **Customer**; chấp nhận / từ chối (FA-34, FA-35) và tự hủy → **Farmer** |
| Chatbot P5 | Bắt buộc (bỏ "Bonus", bỏ "nếu kịp") |
| Hợp đồng mới | Migration 2 cột v1.7; hàm kiểm tra tồn kho (Farmer → Customer); gửi yêu cầu thay đổi (Customer → Farmer) |
| Dịch vụ kho | Customer không còn dùng; chỉ Farmer và Admin (qua FSM) |
| Deploy P7 | Cho phép máy chủ gọi Nominatim |
| Test ngày 5 | Sửa luồng 1–3; thêm luồng 4 (yêu cầu thay đổi + khách không đến) |

---

## 7. Quy chuẩn backend (`SKILL.md`, `django-backend_skill.md`)

| Hạng mục | Nội dung mới |
| :--- | :--- |
| Nguồn chuẩn | Trỏ tới tài liệu v1.7; `SKILL.md` là file skill chuẩn |
| Service chưa có | Hàm kiểm tra tồn kho, `validate_pickup_date()`, `change_request.py` (Farmer), `modify.py` viết lại theo D-030 (Customer), `geocoding.py` (Farmer) |
| Khóa dòng | Chỉ khóa sản phẩm khi trừ / cộng kho |
| FSM | Thêm mục 7.5 Tồn kho theo cạnh và 7.6 Yêu cầu thay đổi đơn |
| Settings | Thêm `BOOKING_HORIZON_DAYS = 7`, cấu hình Nominatim |
| Upload ảnh | Tối đa **2 MB** |

---

## 8. Bổ sung v1.9

### 8.1 Quyết định mới

| Mã | Chủ đề | Nội dung mới |
| :---: | :--- | :--- |
| D-037 | Admin đóng chợ | Đóng chợ (AD-17) **không còn bị chặn** khi còn đơn mở. Admin nhập lý do và gõ đúng chữ **`Confirm`** để chống bấm nhầm (backend kiểm tra lại). Mọi đơn mở tại chợ bị từ chối với lý do hệ thống "chợ đóng" (`MARKET_CLOSED_BY_ADMIN`), hoàn kho đơn đã duyệt / sẵn sàng, xóa yêu cầu thay đổi; mọi khung giờ của chợ tắt. **Không** đình chỉ Farmer. Khách có đơn bị hủy và Farmer có sạp tại chợ nhận **một** thông báo `MARKET_CLOSED` (in-app + email, kèm lý do Admin nhập — ngoại lệ của D-033). Mở lại chợ không tự bật khung giờ. Lịch đóng cửa tạm thời theo ngày vẫn bị chặn khi còn đơn mở |
| D-038 | Bảo mật backend | Chỉ tin IP do proxy gắn vào (`NUM_PROXIES`, Render = 1); giới hạn đăng nhập sai theo email (20 lần/giờ); cấu hình mặc định an toàn (`DEBUG` mặc định tắt, production bắt buộc có `SECRET_KEY`); ảnh upload giới hạn 36 megapixel và được mã hóa lại (xóa EXIF / GPS); báo cáo Excel không để tên thành công thức; logout / khóa khách thì đóng kết nối WebSocket |
| D-039 | Dọn tài khoản không dùng | Lệnh `purge_stale_accounts`: xóa khách và sạp chưa được duyệt, không đăng nhập ≥ 3 tháng, chưa từng có đơn. Mặc định chỉ liệt kê, `--apply` mới xóa, có ghi nhật ký. **Chưa được chạy `--apply`** cho tới khi đăng nhập cập nhật `last_login` |

### 8.2 Vòng đời đơn hàng (FSM)

| Hạng mục | Nội dung mới |
| :--- | :--- |
| T3 / T4 / T12 do Admin | Nhận lý do hệ thống `FARMER_SUSPENDED_BY_ADMIN` (đình chỉ Farmer, mặc định) hoặc `MARKET_CLOSED_BY_ADMIN` (đóng chợ) |
| Lõi FSM | `transition_order()` thêm `admin_reason` và `notify_customer` (chỉ dùng cho Admin). Đóng chợ không gửi `ORDER_DECLINED` theo từng đơn, vì khách đã nhận `MARKET_CLOSED` |

### 8.3 Cơ sở dữ liệu

| Hạng mục | Nội dung mới |
| :--- | :--- |
| `customer_profiles.image` | Cột ảnh mới (migration `accounts/0008`); chưa có API ghi |
| `NotificationType` | Thêm `MARKET_CLOSED` (migration `notifications/0004`) |
| `AuditAction` | Thêm `FARMER_UPDATED`, `CUSTOMER_UPDATED` (`system/0004`), `ACCOUNT_PURGED` (`system/0005`) |
| `ChangeReason` | Thêm `MARKET_CLOSED_BY_ADMIN` (không cần migration) |
| Số bảng | Giữ nguyên **30 bảng** (24 + 6 bảng lịch sử từ v1.8) |

### 8.4 API

| Mã | Nội dung mới |
| :--- | :--- |
| AD-17 | Body `{ reason, confirmation: "Confirm" }`; response thêm `cancelled_orders`; chợ đã đóng → `400 INVALID_STATUS_TRANSITION`; bỏ lỗi `RESOURCE_IN_USE` |
| **AD-03b, AD-10b** | **Mới**: Admin sửa thông tin liên lạc của sạp (`stall_name`, `contact_person`, `phone`, `description`, `order_cutoff_hours`) và của khách (`full_name`, `phone`, `address`) |
| AD-02, AD-09, AD-14, AD-20, AD-22, AD-29 | Thêm `ordering`; giá trị lạ → `400` |
| **AD-34** | **Mới**: `GET /api/admin/audit-trail/<model>/<id>/` — lịch sử thay đổi của một bản ghi, mới nhất trước |
| AU-03, AU-09 | Thêm giới hạn `login_email`: 20 lần sai / giờ / email |
| AU-08 | Vé WebSocket mang `sid`; socket bị đóng (`4401`) khi logout hoặc khi tài khoản bị khóa |

### 8.5 Màn hình

| Màn hình | Nội dung mới |
| :--- | :--- |
| A-05 Danh sách chợ | Nút "Ngừng hoạt động" luôn bấm được; hộp thoại hiện số đơn sẽ bị từ chối, ô Lý do và ô gõ `Confirm` |
| A-03, A-04 | Form sửa thông tin liên lạc (AD-03b, AD-10b) |
| Danh sách Admin | Sắp xếp theo cột (tham số `ordering`) |

### 8.6 Việc còn mở

Danh sách đầy đủ kèm nhánh phụ trách ở **§8.1 "Việc còn mở sau v1.9"** của tài liệu gốc. Quan trọng nhất: backend kiểm tra chữ `Confirm`, mẫu email `MARKET_CLOSED`, đăng nhập cập nhật `last_login` (chặn D-039), và khôi phục AU-01 bị xóa khi merge nhánh Admin.
