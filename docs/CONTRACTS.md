# NYC Taxi team integration contracts — draft v1

| Điểm bàn giao | Đầu ra |
|---|---|
| Ingestion | `data/bronze/taxi/yellow_tripdata_YYYY-MM.parquet`, `data/bronze/weather/weather_YYYY-MM.parquet`, `data/bronze/zones/taxi_zone_lookup.csv` |
| Validation | Tên file taxi/weather tương tự ở Silver, zone lookup dạng Parquet, dòng lỗi ở Quarantine |
| PostgreSQL | `staging.taxi_trips`, `staging.weather_hourly`, `staging.zones`; danh sách cột bắt buộc trong `TABLES` của `src/warehouse/load_staging.py` |
| dbt | Source `raw_staging` trỏ đến các bảng staging. Đầu ra `warehouse.fact_trip`, dimension và các Gold view trong `marts` |
| Analytics | Lọc `data_month` bằng ngày đầu tháng. Demand nhóm theo giờ New York. Join thời tiết dùng giờ UTC |
| Retry | `trip_id` theo file và vị trí dòng. Thay dữ liệu taxi/weather theo tháng và nạp lại lookup trong một transaction mặc định |
