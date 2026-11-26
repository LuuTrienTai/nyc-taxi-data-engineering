# NYC Taxi Analytics Platform

Pipeline batch theo tháng cho NYC Yellow Taxi, Taxi Zone Lookup và Open-Meteo. Chạy bằng Docker Compose trên Mac hoặc Windows. Website truy vấn PostgreSQL qua API đọc. Dashboard so sánh pickup/drop-off, lọc khoảng ngày, nhóm weekday/weekend và phân tích demand theo nhiệt độ, lượng mưa, fare, distance, duration.

- **Bronze** lưu các file nguồn và dấu vân tay SHA-256.
- **Silver** đọc Parquet theo batch, chuẩn hóa, kiểm tra, nối khóa zone/date/weather và tạo mã chuyến. Website hiển thị mẫu trước và sau xử lý.
- **Quarantine** lưu bản ghi bị loại, số dòng nguồn và lý do.
- **Gold** có `fact_trip` phân vùng theo tháng, `dim_date`, `dim_zone`, `dim_weather` và ba marts đúng tên trên slide.
- **Airflow** chạy theo lịch tháng hoặc chạy bù một tháng được chọn. **dbt** cung cấp SQL mô hình mart và kiểm thử warehouse.

## Chạy dữ liệu thật

Mở Docker Desktop, giải nén ZIP và mở Terminal trong thư mục có `compose.yaml`. Nếu cổng web 8501 đã được dùng, đổi `WEB_PORT` trong `.env`. PostgreSQL chỉ truy cập qua mạng Docker nội bộ.

```bash
cp .env.example .env
docker compose up -d --build dashboard
docker compose run --rm runner python -m src.pipeline --month 2025-01
docker compose run --rm runner python -m src.verify --month 2025-01
```

Mở [NYC Taxi Analytics](http://localhost:8501), chọn **2025-01**. Chạy thêm `2025-02` và `2025-03` bằng cùng lệnh pipeline để đạt phạm vi ba tháng theo slide. Khởi động Airflow là tùy chọn cho đường chạy CLI.

## Chạy demo offline

Xem [hướng dẫn demo](docs/DEMO_VI.md) để tạo dữ liệu giả lập trong Compose project riêng. Lần đầu Docker vẫn cần tải image và Python dependencies. Sau khi build xong, fixture chạy với Bronze nội bộ, không gọi TLC hoặc Open-Meteo.

## Kiểm thử và tài liệu

```bash
docker compose run --rm runner python -m pytest -q
docker compose run --rm runner dbt build --project-dir dbt --profiles-dir dbt
```

- [Demo, Airflow, backup và chuyển từ bản cũ](docs/DEMO_VI.md)
- [Đối chiếu từng slide và thiết kế dữ liệu](docs/ARCHITECTURE.md)
- [Kết quả kiểm thử và cách tái lập](docs/VALIDATION.md)

Dừng dịch vụ bằng `docker compose down`. Lệnh này giữ volumes. Nếu đã bật Airflow, dùng cặp file Compose và profile như lúc khởi động, thêm `down`. Giữ project mới `nyc-taxi-platform` tách biệt với volume Gold của phiên bản cũ.
