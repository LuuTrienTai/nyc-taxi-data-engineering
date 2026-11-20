# Báo cáo Kiểm thử & Xác thực (M4 Validation Report)

**Người thực hiện:** M4 - Hùng
**Ngày cập nhật:** Tháng 11/2026
**Môi trường:** Docker Compose (PostgreSQL 16, Python 3.11)
**Kiến trúc:** Bronze (Disk) → Silver (Transient RAM) → Gold (PostgreSQL)

---

## 1. Tổng quan Kiến trúc & Trạng thái Hệ thống
Dự án đã được tái cấu trúc (refactor) toàn diện sang mô hình Data Warehouse chuẩn mực. Lớp Staging và Silver lưu trữ vật lý đã được loại bỏ hoàn toàn. 
*   **Bronze Layer:** Lưu trữ dữ liệu gốc (Parquet/JSON/CSV) trên ổ cứng.
*   **Silver Layer:** Dữ liệu được làm sạch và xử lý logic hoàn toàn trong RAM (Pandas DataFrame) theo từng batch 50,000 dòng. Không ghi file hay tạo bảng vật lý.
*   **Gold Layer:** Chứa dữ liệu phân tích cuối cùng trong schema `gold`, bao gồm: `gold.fact_trip`, `gold.dim_zone`, `gold.dim_weather_hour`, và 3 bảng aggregate (`agg_daily_demand`, `agg_zone_demand`, `agg_hourly_weather`).

---

## 2. Kết quả Chạy Pipeline (M2 & M3)
Pipeline được kích hoạt thông qua Docker runner để đảm bảo tính nhất quán của môi trường.

**Lệnh chạy:**
    docker compose run --rm runner python -m src.pipeline --month 2025-01

**Kết quả thực tế:**
*   Dữ liệu được tải và xử lý thành công.
*   Lớp Gold đã ghi nhận **3,251,618** dòng chuyến xe hợp lệ cho tháng 01/2025.
*   Các chuyến xe không hợp lệ (lỗi tọa độ, thời gian, giá cước âm) đã được đưa vào bảng `audit.rejections` với lý do cụ thể.

---

## 3. Kết quả Kiểm thử Độc lập (M4 Verification)
Script `src/verify.py` được viết bởi M4 để kiểm chứng độc lập tính toàn vẹn của dữ liệu đầu ra (không phụ thuộc vào M3). Script kiểm tra 3 điều kiện:
1. Bảng `gold.fact_trip` phải tồn tại và có dữ liệu.
2. Không được tồn tại bất kỳ bảng Staging/Silver nào trong DB.
3. Tổng doanh thu từ Fact phải khớp tuyệt đối với bảng Aggregate.

**Lệnh chạy:**
    docker compose run --rm runner python -m src.verify --month 2025-01

**Kết quả thực tế:**
    === Starting M4 Independent Verification for 2025-01 ===
    [PASS] gold.fact_trip exists with 3,251,618 rows for 2025-01.
    [PASS] No Silver or staging tables found in Postgres.
    [PASS] Fact and Mart revenue reconciled: $88,071,527.78

    === All M4 Verification Checks Passed! ===

---

## 4. Đối chiếu Chỉ số Dashboard với SQL Trực tiếp
Để đảm bảo Dashboard hiển thị đúng số liệu, M4 đã đối chiếu trực tiếp các KPI trên Dashboard với kết quả truy vấn SQL từ Database.

| KPI trên Dashboard | Câu lệnh SQL đối chiếu | Kết quả SQL thực tế | Trạng thái |
| :--- | :--- | :--- | :--- |
| **Valid Trips** | `SELECT COUNT(*) FROM gold.fact_trip WHERE data_month = '2025-01-01';` | `3,251,618` | KHỚP |
| **Total Revenue** | `SELECT SUM(total_amount) FROM gold.fact_trip WHERE data_month = '2025-01-01';` | `$88,071,527.78` | KHỚP |
| **Top Zones** | `SELECT pickup_location_id, COUNT(*) FROM gold.fact_trip GROUP BY 1 ORDER BY 2 DESC LIMIT 1;` | `Zone 132 (JFK)` | KHỚP |
| **Daily Demand** | `SELECT pickup_datetime::date, COUNT(*) FROM gold.fact_trip GROUP BY 1;` | `Biểu đồ line chart` | KHỚP |

---

## 5. Kiểm tra Tài khoản Metabase Reader (Read-only)
Theo yêu cầu của PDF, tài khoản `metabase_reader` phải đọc được dữ liệu Gold nhưng không được phép sửa đổi.

**Lệnh kiểm tra quyền Đọc (SELECT):**
    SELECT COUNT(*) FROM gold.fact_trip;
    -- Kết quả: Trả về 3,251,618 (Thành công)

**Lệnh kiểm tra quyền Ghi/Xóa (DELETE) - Dự kiến sẽ bị từ chối:**
    DELETE FROM gold.fact_trip;
    -- Kết quả: ERROR: permission denied for table fact_trip (Thành công - Đã chặn đúng)

---

## 6. Kiểm tra Xử lý Lỗi (Edge Cases)
*   **Tháng không có dữ liệu:** Khi chọn tháng không tồn tại trên Dashboard, giao diện hiển thị "No data for this month" và không giữ lại số liệu của tháng trước đó.
*   **Re-run (Idempotency):** Chạy lại pipeline cho cùng một tháng sẽ xóa dữ liệu cũ của tháng đó trong transaction và ghi đè bằng dữ liệu mới. Số lượng dòng và doanh thu không bị nhân đôi (đã được kiểm chứng qua `audit.pipeline_runs`).

---
*Báo cáo được tổng hợp bởi M4 dựa trên kết quả chạy thực tế tại local (Docker Compose).*