# MarketLink — Phân công công việc theo 3 nhánh

> Căn cứ: tài liệu thiết kế v1.9 (`MarketLink_requirement_analysis_ok (5).md` — D-001 → D-039, 30 bảng (24 + 6 bảng lịch sử), API gồm FA-31 → FA-37, AD-31 → AD-34, AD-03b, AD-10b).
> Việc còn mở sau v1.9 và nhánh phụ trách: xem §8.1 "Việc còn mở sau v1.9" của tài liệu thiết kế.
> Guest (trang công khai) thuộc nhánh **Admin**. Các phần **Nền tảng dùng chung** được chia hết cho 3 nhánh, không có phần nào "để chung".
> Theo D-034, **mọi tính năng trong tài liệu thiết kế đều bắt buộc**, không có phần "Bonus" hay "nếu kịp".

---

## 0. Nguyên tắc chia

1. **Mỗi nhánh làm trọn chiều dọc (BE + FE)** của role mình, để một người hiểu hết luồng từ API đến màn hình.
2. **Phần dùng chung giao cho nhánh dùng nó nhiều nhất hoặc gần nó nhất về nghiệp vụ**, và nhánh đó chịu trách nhiệm cung cấp đúng hạn cho các nhánh còn lại (mục 5).
3. **Thao tác do role nào thực hiện thì nhánh của role đó làm.** Ví dụ yêu cầu thay đổi đơn (D-030): khách gửi yêu cầu → nhánh Customer; Farmer chấp nhận / từ chối → nhánh Farmer; hệ thống tự hủy yêu cầu quá hạn → nhánh Farmer (nằm trong quét lười).

---

## 1. Tổng quan

| Nhánh | Người phụ trách | Phần role | Phần dùng chung được giao |
|---|---|---|---|
| **Customer** | *(Tuan_Tu)* | C1 → C8 | P2 Xác thực · P3 Khung frontend · P4-FE Thông báo · P5 Chatbot AI |
| **Farmer** | **Longnguyen** | F1 → F9 | P1 Khung backend · P4-BE Thông báo · P6 Dữ liệu và migration |
| **Admin (gộp Guest)** | *(Minh_Anh)* | G1 → G4, A1 → A9 | P7 Deploy |

---

## 2. Nhánh CUSTOMER

### 2.1 Tính năng của role

| # | Module | Backend | Frontend | Độ khó |
|---|---|---|---|---|
| C1 | Giỏ hàng nhiều Farmer | PU-08 pickup-options (chỉ ngày là ngày chợ họp **và** ngày hoạt động của Farmer — D-031; loại ngày chợ đóng cửa / Farmer nghỉ; không trả khung đã qua `cutoff_at`) | C-01 (Zustand persist, nhóm theo Farmer) | TB |
| C2 | **Checkout tạo N đơn** | CU-04 (idempotency, **chỉ kiểm tra tồn kho khả dụng, không khóa, không trừ kho — D-029**, giới hạn 10 đơn `PLACED` chưa qua giờ nhận — D-005 v1.5, quét lười chạy trước ở transaction riêng, snapshot giá, snapshot `stall_label`, notify) | C-02 (ghi chú "Stock is reserved only when the farmer accepts your order"), C-03 | **Cao** |
| C3 | Đơn của tôi, chi tiết, hủy | CU-05, 06, 08 (OCC; hủy gọi lõi FSM) | C-04, C-05 (SĐT Farmer + nút Gọi, D-026; badge "Change requested") | TB |
| C4 | **Sửa đơn & gửi yêu cầu thay đổi** | CU-07 (OCC): đơn `PLACED` sửa trực tiếp; đơn `ACCEPTED` **gửi yêu cầu thay đổi** — ghi `orders.pending_change` đúng định dạng Pass 4A, thay yêu cầu cũ, không đổi nội dung đơn, không trừ kho (D-030). Kiểm tra: trước `cutoff_at`; ngày nhận từ hôm nay đến 7 ngày tới, hợp lệ theo `validate_pickup_date()`; sản phẩm đang bán công khai; kho khả dụng đủ cho phần tăng. Ghi lịch sử, báo Farmer `ORDER_MODIFIED` | C-06 (cảnh báo "Your changes will be sent to the farmer for approval…"), khối "Change request" ở C-05 | **Cao** |
| C5 | Đặt lại đơn cũ | CU-09 | Nút ở C-04, C-05 | Thấp |
| C6 | Đánh giá sau khi hoàn tất | CU-10, 11 | C-07 | TB |
| C7 | Yêu thích 3 loại + danh sách người nhận restock | CU-12 → 17; selector `get_restock_subscribers()` | C-08 | TB |
| C8 | Dashboard + hồ sơ | CU-01, 02, 03 | C-00, C-10 | Thấp |

### 2.2 Phần dùng chung được giao

| # | Module | Nội dung |
|---|---|---|
| P2 | Xác thực | CustomUser manager, roles seed dùng chung với P6; AU-01 (đăng ký Customer; **chuẩn hóa + kiểm tra trùng số điện thoại — D-028**), AU-03 → 07 (đăng nhập, refresh, logout, me, đổi mật khẩu); **AU-09 đăng nhập Admin (cổng riêng, D-027)**; `ACCOUNT_LOCKED` kèm lý do khi đúng mật khẩu (D-024); blacklist Redis; throttle (*v1.9 — D-038:* thêm `login_email` đếm lần sai theo email, đã có); permission class theo role; *v1.9 — D-039:* **AU-03, AU-09 cập nhật `users.last_login` khi đăng nhập thành công** (chưa làm, chặn lệnh `purge_stale_accounts`). Màn hình G-09, G-10, **A-00 `/admin/login`** (`AdminAuthLayout`), trang đổi mật khẩu cho 3 role |
| P3 | Khung frontend | Router, 3 layout, ProtectedRoute, axios interceptor (refresh token, If-Match, Idempotency-Key), react-query, map mã lỗi → UI (§1.7 Pass 3), component chung: DataTable, StatusBadge, ConfirmDialog, EmptyState, **MapView / MapPicker gốc** (Leaflet: import CSS, sửa icon marker) |
| P4-FE | Thông báo (phía giao diện) | Chuông thông báo + đếm chưa đọc, client WebSocket (`react-use-websocket`, gọi lại `unread-count` khi kết nối lại), trang N-01, C-09, F-10, banner thông báo toàn sàn N-04; hiển thị cả 2 loại mới `ORDER_CHANGE_APPROVED`, `ORDER_CHANGE_REJECTED` (D-030) |
| P5 | Chatbot AI (**bắt buộc — D-034**) | CH-01, 4 công cụ chỉ đọc (dùng selector public của nhánh Admin), Gemini, công tắc `AI_CHAT_ENABLED`; widget N-03 |

---

## 3. Nhánh FARMER — Longnguyen (kiêm Lead backend)

### 3.1 Tính năng của role

| # | Module | Backend | Frontend | Độ khó |
|---|---|---|---|---|
| F1 | Đăng ký Farmer + banner trạng thái duyệt | AU-02: thêm **`operating_days` bắt buộc ≥ 1 ngày** (D-031); sau khi tạo tài khoản **tự tra tọa độ từ địa chỉ** qua Nominatim, ngoài transaction, lỗi thì để trống (D-032) | G-11 (thêm ô Ngày hoạt động), banner PENDING / SUSPENDED | TB |
| F2 | Hồ sơ sạp + ngày hoạt động + vị trí | FA-02, 03 (upload ảnh, cutoff 1–72; sửa `operating_days`: bỏ một ngày thì tắt khung giờ ngày đó, còn đơn mở vào thứ đó thì `RESOURCE_IN_USE`; đổi địa chỉ thì tra lại tọa độ; nhận tọa độ khi Farmer kéo ghim) | F-08 (ô Ngày hoạt động; MapPicker của P3 chỉ để chỉnh ghim, không bắt buộc; nhắc "Location not found") | TB–Cao |
| F3 | Chợ tham gia + khung pickup + cutoff + **lịch nghỉ bán** | FA-04 → 10 (khung chỉ đặt vào ngày chợ họp **và** ngày hoạt động của Farmer — D-031); **FA-31 → 33** (D-023); `stall_label` bắt buộc (D-026); service `validate_pickup_date()` (ngày hợp lệ theo A-019: ngày chợ họp và ngày hoạt động của Farmer, chợ không đóng cửa, Farmer không nghỉ, khung và chợ đang bật, từ hôm nay đến `BOOKING_HORIZON_DAYS`, trước `cutoff_at`) | F-07 (chip ngày hoạt động, khối Lịch nghỉ bán, nhãn "Đã tắt do chợ đổi lịch") | TB–Cao |
| F4 | Sản phẩm: CRUD, ảnh, hết hàng, lưu trữ | FA-11 → 16 (bảo mật upload, xóa mềm; trả thêm `pending_quantity` để đối soát); FA-14 gọi restock (D-025) | F-04 (cột "Chờ duyệt"), F-05 | TB |
| F5 | **Mẫu tồn kho tuần** | FA-17, 18 (công thức giữ hàng: "đang giữ" chỉ gồm đơn `ACCEPTED` / `READY_FOR_PICKUP` chưa qua giờ nhận — D-029; khóa dòng, quét lười, gọi restock) | F-06 (hộp thoại xem trước, cột "Chờ duyệt" tham khảo) | **Cao** |
| F6 | Danh sách đơn, đếm theo tab, danh sách soạn hàng, **nhóm đơn cùng khách + ngày nhận (D-005 v1.5)** | FA-19 → 22 (quét lười; sắp xếp theo tab: chờ duyệt `created_at` tăng dần, đã xác nhận / sẵn sàng `pickup_start_at` tăng dần, lịch sử `created_at` giảm dần; lọc `change_requested`); FA-20 thêm `change_requests` | F-02 (cảnh báo "Not enough stock" ở tab chờ duyệt), F-03 | TB |
| F7 | **Hành động FSM + lõi FSM + dịch vụ kho + xử lý yêu cầu thay đổi** | FA-23 → 27 (T2 khóa và trừ kho, thiếu → `INSUFFICIENT_STOCK`; T4 tới trước `pickup_start_at`, FA-24 bắt buộc khai báo món hết hàng khi T4 (`mark_sold_out` / `mark_sold_out_product_ids`, D-036); **FA-36** đánh dấu 1 món hết hàng trong đơn `PLACED` (D-036); T9 chặn khi còn yêu cầu thay đổi; T11 và **T14** cộng trả kho); **FA-34, FA-35** chấp nhận / từ chối yêu cầu thay đổi (D-030); ma trận `TRANSITIONS` v1.7 (bỏ T7, thêm T14), Triple-Gate, OCC, ghi `order_status_history`; `lock_products()`, `apply_stock_delta()`, hàm kiểm tra tồn kho khả dụng; `expire_overdue_orders()` (thêm tự hủy yêu cầu thay đổi quá hạn); *v1.9 — D-037:* `transition_order()` thêm `admin_reason` (`MARKET_CLOSED_BY_ADMIN`) và `notify_customer` cho cạnh Admin (đã làm) | Nút theo trạng thái trên F-02, F-03; khối "Change request" ở F-03 (3 nút: chấp nhận / giữ đơn cũ / hủy cả đơn) | **Rất cao** |
| F8 | Dashboard thống kê | FA-01 (tổng đơn, đơn chờ, doanh thu, bán chạy) | F-01 | TB |
| F9 | Xem và trả lời đánh giá | FA-28 → 30 | F-09 | Thấp |

### 3.2 Phần dùng chung được giao

| # | Module | Nội dung |
|---|---|---|
| P1 | Khung backend | `marketlink_core/`: `BaseModel`, `CreatedAtModel`, `HistoryRequestMeta`, `UUIDUploadTo`, `api_response`, exception handler + Error Catalog, phân trang, middleware `request_id`, `BasePolicy`, `log_security_event()`; settings (MySQL, CORS headers, TIME_ZONE, throttle rates, Redis cache, `BOOKING_HORIZON_DAYS`, cấu hình gọi Nominatim); *v1.9 — D-038 (đã làm):* `NUM_PROXIES`, cấu hình mặc định an toàn, kiểm tra và mã hóa lại ảnh upload dùng chung, đóng WebSocket khi logout / khóa khách |
| P4-BE | Thông báo (phía máy chủ) | Model `notifications`, `announcements`; hàm `notify()` (ghi DB + WebSocket + email qua `on_commit`); Channels + daphne, vé WebSocket AU-08, consumer; email Gmail SMTP qua thread pool + template; NO-01 → 04; **thêm 2 loại `ORDER_CHANGE_APPROVED`, `ORDER_CHANGE_REJECTED`**; câu thông báo khi Admin khóa khách đổi thành "hàng đã trả về kho online" (D-033) |
| P6 | Dữ liệu | 24 model, **chạy migration (chỉ Lead)**, data migration 3 role, seed demo (chợ, Farmer có `operating_days` và tọa độ ghi sẵn, sản phẩm, đơn, review, 3 kỳ nghỉ), xuất `.sql`, SY-01 health; **UNIQUE `phone` + hàm chuẩn hóa số điện thoại + migration (D-028)**; **v1.7: thêm cột `farmer_profiles.operating_days` và `orders.pending_change` + migration** |

Nhánh nặng backend nhất; các nhánh khác phụ thuộc vào P1, P6 ngay ngày 1.

---

## 4. Nhánh ADMIN (gộp Guest)

### 4.1 Trang công khai (Guest)

| # | Module | Backend | Frontend | Độ khó |
|---|---|---|---|---|
| G1 | Duyệt chợ + bản đồ + chợ gần tôi | PU-03, 04, 05 (Haversine, `upcoming_closures`; PU-05 lọc `day` theo ngày hoạt động của Farmer và có khung bật ngày đó — D-031) | G-02, G-03 (Leaflet, marker, chỉ đường, badge Đóng cửa) | TB |
| G2 | Danh mục và chi tiết sản phẩm, bộ lọc | PU-02, 10, 11, 12 (django-filter, **selector hiển thị công khai dùng chung**) | G-04, G-05 | TB |
| G3 | Hồ sơ Farmer công khai + danh bạ | PU-06, 07, 09 (`upcoming_closures`; `operating_days` lấy từ hồ sơ Farmer; lọc `day` như PU-05) | G-06 (chip ngày hoạt động, badge Nghỉ bán, giờ chốt cụ thể, bản đồ vị trí Farmer nếu có tọa độ), G-13 | Thấp |
| G4 | Trang chủ, About, Contact, 403/404 | PU-01 (**`max_placed_orders_per_customer: 10`**, bỏ giới hạn theo Farmer), PU-13 (đọc announcements) | G-01, 07, 08, 12 | Thấp |

### 4.2 Quản trị

| # | Module | Backend | Frontend | Độ khó |
|---|---|---|---|---|
| A1 | Dashboard | AD-01 | A-01 | Thấp |
| A2 | **Quản lý Farmer** | AD-02 → 08, *v1.9:* AD-03b sửa thông tin liên lạc, `ordering` cho AD-02 (xem trước ảnh hưởng, đình chỉ → T3/T4/T12 qua lõi FSM, **chỉ hoàn kho đơn đã duyệt / sẵn sàng** — D-029, xóa yêu cầu thay đổi đang chờ, thông báo; lý do Admin nhập chỉ lưu `status_reason` + `audit_logs`, không vào lịch sử đơn hay email — D-033) | A-02, A-03 | **Cao** |
| A3 | Quản lý khách hàng | AD-09 → 13, *v1.9:* AD-10b sửa thông tin liên lạc, `ordering` cho AD-09 (khóa → T5/T6/T13 qua lõi FSM, hoàn kho như A2; lưu / xóa `deactivation_reason`, D-024; **cờ `at_risk` / `no_show_count` chỉ đếm `NO_SHOW` qua T11, không đếm T14 + bộ lọc (D-028, D-036)**) | A-04 (cột Lý do khóa, badge At risk) | TB |
| A4 | **Chợ: CRUD, ngày mở cửa, giờ mở cửa, tọa độ, lịch đóng cửa** | AD-14 → 17 (AD-16 tự tắt khung + `MARKET_SCHEDULE_CHANGED`; ~~AD-17 chặn khi còn đơn mở — D-022~~ *v1.9 — D-037:* AD-17 nhận `{ reason, confirmation: "Confirm" }`, tự từ chối đơn mở qua lõi FSM với `admin_reason = MARKET_CLOSED_BY_ADMIN` và `notify_customer = false`, tắt khung giờ của chợ, gửi `MARKET_CLOSED` in-app + email cho khách và Farmer, chợ đã đóng → `400`); `ordering` cho AD-14; **AD-31 → 33** (D-023) | A-05 (hộp thoại đóng chợ: Lý do + gõ `Confirm`), A-06 (dùng MapPicker; khối Lịch đóng cửa tạm thời) | **Cao** |
| A5 | Danh mục sản phẩm | AD-18, 19 | A-07 | Thấp |
| A6 | Kiểm duyệt sản phẩm và review | AD-20 → 24, *v1.9:* `ordering` cho AD-20, AD-22 | A-08 | Thấp–TB |
| A7 | Báo cáo + xuất Excel | AD-25, 26 (openpyxl, ghi `EXPORT_DATA`) | A-09 | TB |
| A8 | Thông báo toàn sàn | AD-27, 28 | A-10 | Thấp |
| A9 | Nhật ký hệ thống | AD-29, 30, *v1.9:* `ordering` cho AD-29, **AD-34** lịch sử thay đổi theo bản ghi | A-11, khối lịch sử ở A-03 | Thấp |
| A10 *(v1.9)* | Dọn tài khoản không dùng (D-039) | Lệnh `purge_stale_accounts` (`ACCOUNT_PURGED`); chỉ chạy `--apply` sau khi AU-03 / AU-09 cập nhật `last_login` (nhánh Customer) | — | Thấp |

Admin **không** có chức năng hủy / sửa từng đơn (D-033).

### 4.3 Phần dùng chung được giao

| # | Module | Nội dung |
|---|---|---|
| P7 | Deploy | Render (daphne: HTTP + WebSocket), Upstash Redis, MySQL cloud, biến môi trường, HTTPS; **cho phép máy chủ gọi ra Nominatim (tra tọa độ — D-032)**; **dựng bản deploy thử từ ngày 2** |

---

## 5. Hợp đồng giữa các nhánh (ai cung cấp gì cho ai, hạn chót)

Đây là các điểm nối. Nhánh cung cấp phải xong **đúng hạn và đúng chữ ký hàm**; nhánh sử dụng không tự viết lại.

| Hạng mục | Nhánh cung cấp | Nhánh sử dụng | Hạn |
|---|---|---|---|
| `marketlink_core/` (envelope, exception, phân trang, policy, middleware, audit) | Farmer | Tất cả | **Cuối ngày 1** |
| 24 model + migration + seed tối thiểu (3 role, 1 Admin, 2 chợ, 2 Farmer, vài sản phẩm) | Farmer | Tất cả | **Cuối ngày 1** |
| **Migration v1.7**: `farmer_profiles.operating_days`, `orders.pending_change` (định dạng JSON theo Pass 4A — bắt buộc tuân thủ khi đọc / ghi) | Farmer | Tất cả | **Ngay sau khi chốt tài liệu v1.7** |
| Đăng nhập (2 cổng: `/login` Customer + Farmer, `/admin/login` Admin — D-027), refresh, `me`, permission class theo role | Customer | Tất cả | **Cuối ngày 1** |
| Khung FE: router, 3 layout, ProtectedRoute, interceptor, map lỗi, DataTable, StatusBadge, ConfirmDialog | Customer | Tất cả | **Cuối ngày 1** |
| MapView / MapPicker gốc | Customer | Admin (G1, A-06), Farmer (F-08) | Sáng ngày 2 |
| `notify(*, recipient, event_type, context)` (kể cả 2 loại thông báo mới v1.7) | Farmer | Tất cả | Giữa ngày 2 |
| Lõi FSM `transition_order(...)` + ma trận `TRANSITIONS` v1.7 (kho theo D-029, T14, bỏ T7, tự xóa `pending_change` khi đơn bị hủy / từ chối); *v1.9:* tham số `admin_reason`, `notify_customer` cho cạnh Admin | Farmer | Customer (hủy đơn), Admin (T3/T4/T12, T5/T6/T13; AD-17 đóng chợ dùng `MARKET_CLOSED_BY_ADMIN`) | Giữa ngày 2; phần v1.9 đã có |
| `validate_image_upload()` trả **bản ảnh đã mã hóa lại** (D-038) — nhánh dùng phải lưu giá trị trả về, không lưu file gốc | Farmer | Admin (ảnh chợ AD-15 / AD-16), Customer (ảnh khách, khi làm) | Đã có |
| Dịch vụ kho `lock_products()`, `apply_stock_delta()` | Farmer | Admin (hoàn kho khi đình chỉ / khóa, qua lõi FSM). Customer **không** dùng (D-029) | Giữa ngày 2 |
| Hàm **kiểm tra tồn kho khả dụng** (chỉ đọc, không khóa, không trừ) | Farmer | Customer (CU-04 checkout, CU-07 sửa đơn / gửi yêu cầu thay đổi) | Giữa ngày 2 |
| `expire_overdue_orders(*, farmer_id)` (kèm tự hủy yêu cầu thay đổi quá hạn) | Farmer | Customer (checkout) | Giữa ngày 2 |
| `validate_pickup_date()` (điều kiện ngày hợp lệ theo A-019, gồm ngày hoạt động của Farmer và không phải ngày quá khứ) | Farmer | Customer (PU-08, CU-04, CU-07) | Cuối ngày 2 |
| Selector hiển thị công khai (Farmer đã duyệt, sản phẩm không ẩn / không lưu trữ, chợ đang hoạt động) | Admin | Customer (chatbot, danh sách yêu thích, kiểm tra sản phẩm khi sửa đơn) | Cuối ngày 2 |
| Môi trường deploy thử | Admin | Tất cả | Cuối ngày 2 |
| Gửi yêu cầu thay đổi (CU-07, ghi `pending_change`) | Customer | Farmer (FA-34, FA-35 đọc và xử lý) | Ngày 3 |
| `get_restock_subscribers(product_id)` | Customer | Farmer (FA-14, FA-18) | Ngày 3 |

---

## 6. Quy tắc tránh xung đột code

| Quy tắc | Chi tiết |
|---|---|
| Sở hữu view theo role | Mỗi nhánh chỉ sửa `[app]/[role]/views_[role].py`, serializer và URL của role mình. Guest thuộc nhánh Admin (`views_public.py`) |
| Sở hữu service theo miền | Service dùng chung (FSM, kho, kiểm tra tồn kho, `notify`, `validate_pickup_date`, quét lười) chỉ nhánh cung cấp được sửa. Nhánh khác cần thay đổi thì nhắn yêu cầu |
| Yêu cầu thay đổi đơn (D-030) | Chia theo role thực hiện: phần **gửi** yêu cầu (CU-07) thuộc Customer; phần **chấp nhận / từ chối** (FA-34, FA-35) và **tự hủy khi quá hạn** thuộc Farmer. Hai bên chỉ đọc / ghi `orders.pending_change` đúng định dạng Pass 4A |
| Model và migration | **Chỉ nhánh Farmer (Lead) sửa `models.py` và chạy `makemigrations`**. Nhánh khác cần thêm cột thì gửi yêu cầu kèm lý do |
| Frontend | Mỗi nhánh sở hữu `pages/[role]/` của mình; `components/common/` và `lib/` thuộc nhánh Customer (P3) |
| Merge | Merge vào nhánh chính ít nhất 1 lần mỗi ngày; nhánh Farmer merge `marketlink_core` và model trước để các nhánh khác kéo về |
| Không xóa file của nhánh khác *(v1.9)* | Nhánh không xóa file thuộc nhánh khác để "làm gọn" nhánh mình: khi merge, lệnh xóa sẽ lan sang nhánh chính (sự cố v1.9: merge nhánh Admin xóa AU-01 đăng ký khách, backend không khởi động). Chạy `python manage.py check` và `pytest` trước khi commit merge |
| Frontend *(v1.9)* | Frontend chung dùng bản **JSX** của nhánh `Longnguyen`; khi merge, không đưa lại các file TypeScript của bộ frontend cũ |

---

## 7. Lịch theo ngày

| Ngày | Customer | Farmer (Longnguyen) | Admin |
|---|---|---|---|
| **1** | P2 đăng nhập / đăng ký, P3 khung FE | **P1 `marketlink_core/`, P6 model + migration + seed tối thiểu** | P7 chuẩn bị tài khoản deploy; G2 selector công khai + API sản phẩm |
| **2** | MapView gốc; C1 giỏ hàng, bắt đầu C2 | **F7 lõi FSM + kho + hàm kiểm tra tồn kho, P4-BE `notify()`**, F3 + `validate_pickup_date()`; migration v1.7 | Deploy thử; G1, G3, G4 |
| **3** | C2 checkout (xong), C3, C4 (gồm gửi yêu cầu thay đổi) | F4, F5, F6; F7 FA-34, FA-35 | A2, A3, A4 |
| **4** | C5 → C8, P4-FE thông báo, P5 chatbot | F1, F2 (ngày hoạt động, tra tọa độ), F8, F9, P4 WebSocket + email | A1, A5 → A9 |
| **5** | Sửa lỗi sau khi ghép · test luồng đầu cuối · seed demo đầy đủ · quay video · viết báo cáo · xuất `.sql` · ReadMe.doc | ← cả nhóm | ← cả nhóm |

**Bốn luồng test đầu cuối bắt buộc ngày 5**:
1. **Customer chủ trì**: khách đặt hàng ở 2 Farmer (kho chưa bị trừ) → Farmer duyệt (kho bị trừ) → sẵn sàng → hoàn tất → khách đánh giá.
2. **Farmer chủ trì**: Farmer báo nghỉ tuần → khách không chọn được ngày đó; Farmer bỏ một ngày hoạt động → khung ngày đó tự tắt; áp dụng mẫu tuần → khách yêu thích nhận thông báo có hàng lại.
3. **Admin chủ trì**: Admin đình chỉ Farmer → đơn mở tự từ chối, chỉ đơn đã duyệt / sẵn sàng được hoàn kho, khách nhận thông báo; Admin đổi lịch chợ → khung của Farmer tự tắt; *(v1.9)* Admin đóng chợ (nhập lý do, gõ `Confirm`) → đơn mở bị từ chối với lý do "chợ đóng" (không phải "đình chỉ"), hoàn kho đơn đã duyệt, khung giờ của chợ tắt, Farmer vẫn `APPROVED`, khách và Farmer nhận **một** thông báo `MARKET_CLOSED` kèm email.
4. **Farmer chủ trì, Customer phối hợp**: khách sửa đơn đã duyệt → đơn giữ nguyên, có yêu cầu thay đổi → Farmer chấp nhận (kho trừ / trả chênh lệch) hoặc giữ đơn cũ → khách nhận thông báo; yêu cầu không được xử lý tới giờ nhận thì tự hủy; quá giờ nhận khách không đến → Farmer bấm "Không đến", hàng trả về kho.
