# Rà soát 14 góp ý của thầy cô — phần việc phía Admin

> **Ngày rà:** 2026-09-27 · **Nhánh:** `MA-admin-clean`
> **Cách đọc:** mỗi mục ghi rõ **trạng thái thật trong code**, **có phải việc của Admin không**, và **hướng sửa cụ thể**. Những chỗ tôi đã kiểm bằng cách đọc code đều dẫn file.

## Tổng kết một bảng

| # | Góp ý | Trạng thái | Việc của ai | Mức |
| :-: | :--- | :--- | :--- | :-- |
| 1 | Slider khoảng giá | Chưa có | Guest/Customer | — |
| 2 | Thiếu đơn vị "gram", bỏ đơn vị thừa | **Chưa có gram** | **Admin + cả nhóm** | Cao |
| 3 | Rà lại danh mục | Màn hình đã đủ, **nội dung cần duyệt** | **Admin** | Trung bình |
| 4 | Thêm sort + filter | **Xong phía admin**, guest chưa rà | Admin ✅ / Guest | Thấp |
| 5 | Icon phải khớp chữ | **Có lỗ hổng thật** | **Admin** | Trung bình |
| 6 | 1 chợ – 1 sạp | **Đã khoá hôm nay** | Admin ✅ | Xong |
| 7 | Giới hạn thao tác khi chợ đóng | **Một nửa** | **Admin + Customer** | Cao |
| 8 | Sửa sản phẩm lần 2 phải vào lại hàng đợi duyệt | **Chưa có hàng đợi duyệt nào cả** | **Admin** | **Cao nhất** |
| 9 | Race condition tồn kho | **Đã chống**, thiếu test chứng minh | Backend chung | Trung bình |
| 10 | Hết hàng → hỏi khách đặt lại | Chưa có | Farmer/Customer | — |
| 11 | Khách không đồng ý → huỷ đơn | Có sẵn đường huỷ | Farmer | Thấp |
| 12 | Chuông thông báo lấy hàng | **Đã có** | Xong | — |
| 13 | Lịch sử làm bằng chứng → khoá tự động | **Có bằng chứng, chưa tự động** | **Admin** | Cao |
| 14 | AI chatbot | **Đã có** | Xong | — |

**Bảy mục là việc của Admin: 2, 3, 5, 7, 8, 13** (và 6 đã xong). Mục 8 là lỗ hổng lớn nhất.

---

## Việc của Admin — chi tiết và hướng sửa

### Mục 8 — Không hề có bước duyệt sản phẩm ⚠️ Ưu tiên cao nhất

**Hiện trạng:** tôi đã tìm trong toàn bộ app `catalog` và **không có bất kỳ trường hay hàng đợi duyệt nào**. Sản phẩm nông dân đăng lên là **hiện ngay** cho khách. Admin chỉ có thể **Ẩn** hoặc **Gỡ bỏ** *sau khi* nó đã lên sàn.

Nghĩa là góp ý của thầy cô không chỉ đúng ở chỗ "sửa lần 2 phải duyệt lại" — mà **lần 1 cũng chưa từng được duyệt**.

**Hướng sửa:**

1. Thêm cột `Product.review_status` với bốn giá trị: `DRAFT` · `PENDING` · `APPROVED` · `REJECTED`, kèm `review_note` (lý do từ chối) và `reviewed_at` / `reviewed_by`.
2. Điều kiện hiển thị công khai thêm `review_status = APPROVED` (hiện là `is_archived=0 AND is_hidden_by_admin=0 AND farmer.status=APPROVED`).
3. **Sửa lần 2 quay lại hàng đợi**: chỉ khi đụng vào *trường trọng yếu* — tên, mô tả, ảnh, danh mục. Đổi giá hay đổi tồn kho **không** nên bắt duyệt lại, nếu không nông dân sẽ không dám cập nhật tồn kho và dữ liệu tồn kho thành vô dụng — đúng vấn đề ở mục 9 và 10.
4. Trong lúc chờ duyệt lại, **giữ nguyên bản đã duyệt trên sàn** chứ không ẩn đi; nếu ẩn thì mỗi lần sửa chính tả là sạp mất doanh thu.
5. Màn hình Admin: thêm tab **"Chờ duyệt"** vào trang Kiểm duyệt đang có, dùng lại y nguyên bộ lọc và cách sắp xếp hiện tại. Hai nút: Duyệt / Từ chối kèm lý do.
6. Thêm `AuditAction.PRODUCT_APPROVED` và `PRODUCT_REJECTED`, và thông báo cho sạp.

**Điểm cần cả nhóm chốt:** quy định "trường trọng yếu" gồm những gì. Đây là ranh giới giữa *kiểm duyệt có tác dụng* và *làm phiền nông dân đến mức họ bỏ cập nhật*.

**Khối lượng:** 1 migration, ~6 file backend, 2 file frontend.

---

### Mục 2 — Thiếu đơn vị "gram"

**Hiện trạng** ([catalog/models.py:11](../../backend/catalog/models.py#L11)):

```python
class Unit(models.TextChoices):
    KG = "KG", "Kilogram"
    BUNCH = "BUNCH", "Bunch"
    PIECE = "PIECE", "Piece"
    PACK = "PACK", "Pack"
```

Không có gram. Bốn đơn vị này **không phải danh mục admin quản lý được** — chúng là enum trong code, nên muốn đổi phải sửa code + migration, không bấm nút trên web được.

**Hướng sửa:**

- Thêm `GRAM = "GRAM", "Gram"`.
- Về "bỏ bớt đơn vị không dùng": tôi **không tự ý bỏ** được. `BUNCH` (bó) và `PACK` (vỉ/khay) là đơn vị rất thật ở chợ Việt Nam; `PIECE` (quả/củ) cũng vậy. Cần nhóm xác nhận cái nào thừa **dựa trên dữ liệu thật**, vì xoá một giá trị enum đang có sản phẩm dùng sẽ làm hỏng những dòng đó.
- Đề xuất bộ tối thiểu cho bối cảnh Việt Nam: **KG · GRAM · BUNCH (bó) · PIECE (quả/củ) · PACK (vỉ/khay)** — tức chỉ thêm, không bớt, trừ khi có số liệu chứng minh cái nào không ai dùng.
- Câu hỏi thiết kế đi kèm: nếu bán theo gram thì giá niêm yết theo gram hay theo kg rồi quy đổi? Nên **lưu một đơn vị, hiển thị theo đơn vị đó**, đừng quy đổi ngầm — quy đổi ngầm là chỗ sinh lỗi làm tròn tiền.

---

### Mục 3 — Rà lại danh mục

**Hiện trạng:** màn hình `/admin/categories` đã đủ chức năng — thêm, sửa, xoá (chặn nếu còn sản phẩm), bật/tắt, kéo thả đổi thứ tự. **Công cụ không thiếu; nội dung mới là thứ cần rà.**

Dữ liệu mẫu hiện có 20 danh mục (rau lá, củ quả, bầu bí, rau thơm, ớt, nấm, trái cây nhiệt đới, có múi, dâu, dưa, gạo & ngũ cốc, đậu, trứng, sữa, mật ong, đồ khô, bánh, đồ muối chua, gia vị, cây giống).

**Hướng sửa:** đây là **quyết định nghiệp vụ, không phải việc code**. Đề nghị nhóm chốt danh sách chính thức rồi tôi cập nhật `seed_demo` cho khớp. Hai điểm nên cân nhắc:
- 20 danh mục là **nhiều** cho một bộ lọc thả xuống. Dưới 12 dễ dùng hơn.
- "Cây giống" có thật sự thuộc *nông sản tươi* không, hay nên bỏ.

---

### Mục 5 — Icon phải khớp chữ ⚠️ Có lỗ hổng thật

**Hiện trạng** ([categoryIcon.js:26](../../frontend/src/utils/categoryIcon.js#L26)) — comment trong chính file đã thú nhận:

> *"anything missing here silently becomes a leaf on the shopper's home page. 'pepper' and 'basket' have no lucide icon of that name, hence the deliberate stand-ins."*

Tức là: admin gõ tên icon không có trong bảng → **im lặng thành cái lá**, không báo gì. Trang chủ khách thấy một rổ lá cho mọi thứ.

**Hướng sửa:**

1. `IconPicker` đã có sẵn lưới chọn icon — **bắt buộc chọn từ lưới**, bỏ hẳn khả năng lưu một tên icon tuỳ ý. Ràng buộc ở serializer: `icon` phải thuộc danh sách đã biết, sai thì báo lỗi 400 thay vì âm thầm thay bằng lá.
2. Trên trang Categories, hiện icon **ngay cạnh tên** ở mỗi dòng (đang có rồi) để admin tự thấy nếu lệch.
3. Rà một lượt 20 danh mục hiện tại: icon nào đang là lá do không khớp thì gán lại.

---

### Mục 7 — Giới hạn thao tác khi chợ đóng

**Hiện trạng — một nửa đã có:**

✅ Đóng chợ đã: huỷ mọi đơn đang mở, tắt khung giờ nhận hàng, đình chỉ các sạp tại chợ đó (vừa làm hôm nay), gửi thông báo.
✅ Chợ đóng biến mất khỏi danh sách công khai (`is_active` được lọc ở [markets/selectors.py:93](../../backend/markets/selectors.py#L93)).

❌ **Còn thiếu — "lịch nghỉ" khác với "đóng cửa":** bảng `MarketClosure` (nghỉ lễ, nghỉ sửa chữa) **chỉ đang được hiển thị**, tôi không tìm thấy chỗ nào chặn đặt hàng rơi vào ngày nghỉ. Nghĩa là chợ vẫn mở nhưng nghỉ ngày 2/9, khách vẫn đặt được lịch lấy hàng đúng ngày 2/9.

**Hướng sửa:**
- Khi tạo đơn, chặn `pickup_date` rơi vào khoảng `MarketClosure` của chợ đó hoặc `FarmerClosure` của sạp đó → **điểm này nằm ở nhánh Customer**, tôi chỉ báo chứ không sửa được một mình.
- Phía Admin bổ sung: khi thêm một lịch nghỉ **có đơn đã đặt rơi vào đó**, hiện cảnh báo *"N đơn đang rơi vào khoảng này"* trước khi lưu — giống hộp thoại xem trước thiệt hại đang dùng cho đình chỉ sạp và đóng chợ. Đây là việc Admin làm được ngay.

---

### Mục 13 — Lịch sử làm bằng chứng → khoá tự động

**Hiện trạng — bằng chứng đã đủ, quyết định vẫn thủ công:**

✅ Có cờ **"khách có nguy cơ"**: hệ thống đếm số lần không đến nhận trong 30 ngày gần nhất, quá ngưỡng thì cờ tự bật. Ngưỡng và cửa sổ đọc từ biến môi trường.
✅ Có nhật ký hệ thống (ai làm gì) và lịch sử thay đổi từng bản ghi (trước → sau).
✅ Khoá tài khoản bắt buộc nhập lý do và hiện trước số đơn sẽ bị huỷ.

❌ Admin **phải tự nhìn cờ rồi tự bấm khoá**.

**Hướng sửa — đề nghị làm hai bước, đừng nhảy thẳng sang tự động:**

**Bước 1 (nên làm ngay): hiện bằng chứng ngay tại chỗ bấm.** Hộp thoại khoá tài khoản hiện liệt kê luôn các lần vi phạm — ngày nào, đơn số mấy, ở chợ nào. Admin bấm khoá là đã đọc bằng chứng, và lý do khoá tự điền sẵn thay vì gõ tay. Ít rủi ro, làm được ngay bằng dữ liệu đang có.

**Bước 2 (cần nhóm chốt): tự động khoá.** Một lệnh chạy theo lịch, khoá tài khoản vượt ngưỡng, ghi bằng chứng vào nhật ký.

⚠️ **Tôi khuyến nghị cân nhắc kỹ bước 2.** Khoá tự động sẽ **huỷ đơn của người khác** — mỗi lần khoá là các sạp mất đơn đang chờ. Một khách bị trùng dữ liệu hoặc một sạp đánh dấu "không đến" nhầm là đủ để một tài khoản thật bị khoá mà không ai xem lại. Đề xuất an toàn hơn: lệnh tự động **đẩy vào hàng đợi theo dõi** (đã có sẵn) kèm bằng chứng, admin bấm một nút để chốt. Vẫn tự động phần phát hiện, giữ con người ở phần quyết định.

---

## Những mục KHÔNG phải việc của Admin (báo để nhóm phân công)

**Mục 9 — Race condition tồn kho: đã chống, nhưng chưa chứng minh.**
[catalog/services/stock.py:11](../../backend/catalog/services/stock.py#L11) khoá sản phẩm bằng `select_for_update` và **sắp xếp theo id** trước khi khoá, nên hai đơn tranh nhau sẽ xếp hàng chứ không bán vượt, và không deadlock. Thiếu **một test chứng minh** bằng hai transaction song song. Đề nghị viết test đó — thầy cô hỏi thì có cái để chỉ.

**Mục 10, 11 — Hết hàng thì hỏi khách đặt lại.** Luồng này chưa có. Nằm ở nhánh Farmer + Customer. Ghi chú thiết kế: nên đi qua cơ chế "yêu cầu đổi đơn" (`pending_change`) đã có sẵn trong bảng `orders`, đừng dựng cơ chế thứ hai.

**Mục 1, 4 (phần guest) — Slider giá, sort/filter trang khách.** Phía admin đã có đủ bộ lọc và sắp xếp cho **toàn bộ** bảng, làm ở máy chủ, tìm kiếm có debounce. Trang khách cần rà riêng.

**Mục 12 — Chuông thông báo: đã có.** Thông báo trong app qua WebSocket, có fallback hỏi lại mỗi 30 giây, kèm loại `ORDER_READY`.

**Mục 14 — AI chatbot: đã có.** Widget hỏi đáp về chợ, nông sản, đường đi; nút bấm nay kéo thả được khắp màn hình.

---

## Đề nghị thứ tự làm

| Thứ tự | Việc | Vì sao trước |
| :-: | :--- | :--- |
| 1 | **Mục 8** — hàng đợi duyệt sản phẩm | Lỗ hổng lớn nhất: hiện sản phẩm lên sàn không qua ai duyệt |
| 2 | **Mục 2** — thêm gram | Nhỏ, rõ, nhưng phải chốt bộ đơn vị trước khi có dữ liệu thật |
| 3 | **Mục 5** — khoá icon vào danh sách đã biết | Nhỏ, và đang âm thầm sai trên trang khách |
| 4 | **Mục 13 bước 1** — hiện bằng chứng khi khoá | Dùng dữ liệu đã có, không rủi ro |
| 5 | **Mục 7** — cảnh báo khi thêm lịch nghỉ đè lên đơn | Cần nhánh Customer làm phần chặn đặt hàng |
| 6 | **Mục 9** — test chứng minh chống tranh tồn kho | Để trả lời được khi bị hỏi |
| 7 | **Mục 3** — chốt danh sách danh mục | Quyết định nghiệp vụ, không phải code |

**Ba câu cần nhóm chốt trước khi tôi code:**
1. Sửa **trường nào** của sản phẩm thì phải duyệt lại? (mục 8)
2. Bộ đơn vị tính chính thức gồm những gì? (mục 2)
3. Khoá tài khoản **tự động thật**, hay tự động **đẩy vào hàng đợi** để admin chốt? (mục 13)
