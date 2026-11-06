# M3 từng bước

M3 nhận **Silver Parquet** từ M2, đưa vào PostgreSQL rồi biến thành bảng có thể phân tích. M4 dùng kết quả để kiểm KPI và làm Metabase.

| Bước | Input | Việc M3 làm | Output |
|---|---|---|---|
| 1. Nạp dữ liệu | Silver taxi, weather, zones | `load_staging.py` dùng `COPY`, thay taxi/weather theo `data_month` và cập nhật zone lookup trong cùng transaction | `staging.taxi_trips`, `staging.weather_hourly`, `staging.zones` |
| 2. Khai báo nguồn | Ba bảng staging | `sources.yml` khai báo source dbt `raw_staging`. Các view `stg_*` chọn cột để dùng ở bước sau | Các view staging của dbt |
| 3. Dựng dimension | Zones, weather và ngày pickup | Chuẩn bị danh mục zone, thời tiết theo giờ UTC và lịch ngày pickup | `dim_zone`, `dim_weather_hourly`, `dim_date` |
| 4. Dựng fact | Một dòng taxi từ staging | `LEFT JOIN` zone hai lần cho pickup/dropoff và weather theo giờ UTC. Khóa duy nhất là `(data_month, trip_id)` | `warehouse.fact_trip`, mỗi dòng là một chuyến |
| 5. Dựng Gold | `fact_trip` | Gom số chuyến và doanh thu theo ngày, giờ và pickup zone, có cột `data_month` để lọc | `marts.agg_daily_demand`, `agg_hourly_demand`, `agg_zone_demand` |
| 6. Kiểm chứng | Staging, fact và Gold | dbt kiểm khóa, thời gian chuyến, số dòng trước/sau join. M4 đối soát số chuyến và doanh thu theo từng nhóm | Log kiểm tra và KPI tháng |

Ví dụ, một dòng Silver có pickup zone `132`. Sau khi nạp staging và chạy dbt, dòng fact giữ ID `132`, có tên zone nếu lookup khớp, và có nhiệt độ nếu giờ UTC khớp. Nếu zone hoặc weather thiếu, `LEFT JOIN` vẫn giữ chuyến đó. Dòng này được tính một lần trong tổng số chuyến của đúng ngày, giờ và zone.

```bash
python -m src.warehouse.load_staging --month "$MONTH"
dbt debug --project-dir dbt --profiles-dir dbt
dbt parse --project-dir dbt --profiles-dir dbt
dbt build --project-dir dbt --profiles-dir dbt
python -m src.processing.validate_marts --month "$MONTH"
```

`COPY` chỉ đưa dữ liệu vào staging. `dbt build` tạo fact/dim và Gold, rồi chạy test. `validate_marts` kiểm tháng đã chọn có dữ liệu và KPI khớp. Fact được dựng lại toàn bộ từ staging mỗi lần chạy build.

Xem [trình tự chạy đầy đủ](WEEK2_CHECKPOINT.md) để chuẩn bị môi trường, chạy M2 trước M3 và bàn giao M4.
