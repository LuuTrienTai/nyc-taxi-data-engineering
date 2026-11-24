# Đối chiếu thiết kế và triển khai

Các số trang dưới đây tính từ trang bìa của `MID-TERM SLIDES(1).pdf`.

| Slide | Sai lệch trong ZIP đầu vào | Bản cập nhật |
| --- | --- | --- |
| 4, 7–8 · Người dùng và nguồn | HTML chỉ có KPI, top zones và thời tiết cố định. | Website tương tác, lọc tháng, borough, pickup zone, giờ và thời tiết. Có nhóm ngày/giờ, đổi chỉ số, xếp hạng vùng, giá cước theo khoảng cách và ba nguồn như slide. |
| 5–6 · Chất lượng, hiệu năng và an toàn | Fact có index nhưng chưa partition. Kiểm tra tích hợp tham chiếu staging và DB hardcode. | Partition tháng, PK/FK, index, đối soát trước commit và đọc web qua role riêng. Replay Bronze và backup/restore PostgreSQL được ghi trong hướng dẫn. |
| 6, 11–12 · Safe loading | Slide dùng staging. Code dùng xóa/thay tháng và transaction. | Theo quyết định mới của nhóm, giữ direct COPY và transaction cho mỗi tháng. Fact, marts, Quarantine và audit được đối soát trước commit. |
| 7, 9 · Medallion | Silver đã chạy RAM nhưng demo thiếu dữ liệu minh họa. Audit chỉ lưu lý do và số dòng lỗi. | Pipeline explorer mở được mẫu Bronze và Silver của run. Quarantine có payload gốc theo dòng, lý do và phân trang. Great Expectations kiểm schema trước khi đọc batch. |
| 10 · Star schema | Thiếu `dim_date`, dùng `dim_weather_hour` và ba tên mart khác slide. | `dim_date`, `dim_weather`, `dim_zone` độc lập. Zone dùng hai vai trò qua hai FK. Trong web, người xem có thể chọn pickup hoặc drop-off để nhóm và lọc khu vực. Ba marts dùng đúng tên `agg_hourly_zone`, `agg_daily_trips`, `agg_zone_revenue`. |
| 11 · Trip identity | PK theo tháng và số dòng. Hai dòng có cùng nhận dạng vẫn được tải. | MD5 trên thuộc tính được chuẩn hóa. Bản ghi đầu theo thứ tự file được giữ, các ID lặp được đưa vào Quarantine, kể cả ở batch sau. |
| 13 · Airflow và dbt | DAG chỉ trigger tay. dbt có một view và hai test SQL. | DAG theo lịch tháng và có tham số backfill. Cùng SQL mô hình dbt được dùng để tạo marts trong transaction. `dbt build` dựng views kiểm thử trong schema `analytics` và chạy 7 test. |
| 7, 14 · Kênh phục vụ | Compose có cả dashboard và Metabase. | Website thay Metabase theo quyết định mới của nhóm. |

## Đối chiếu use case trên web

| Use case trong sơ đồ | Thành phần trên dashboard | Kết quả |
| --- | --- | --- |
| View Overview Dashboard | KPI chuyến, tổng phí, fare trung bình, khoảng cách trung bình, thời lượng trung bình | Đạt |
| Analyze Demand by Time | Chuyển biểu đồ sang Trips, nhóm theo ngày, giờ hoặc ngày thường/cuối tuần | Đạt |
| Analyze Revenue by Time | Chuyển metric sang Revenue, giữ các nhóm thời gian như trên | Đạt |
| Analyze Demand by Location | Chọn Pickup hoặc Drop-off, lọc borough/zone, xếp hạng theo số chuyến | Đạt |
| Analyze Revenue by Location | Chọn Pickup hoặc Drop-off, xếp hạng zone theo tổng phí | Đạt |
| Analyze Weather vs Demand | Biểu đồ trips/hour theo dải nhiệt độ, kèm số giờ và lượng mưa trung bình; lọc Dry/Rain-Snow | Đạt |
| Analyze Fare and Trip Metrics | KPI fare, distance, duration và các bảng zone với giá cước trung bình | Đạt |
| Analyze Fare vs Trip Distance | Bảng số chuyến và fare trung bình theo dải distance | Đạt |
| Filter Data | Tháng, khoảng ngày, borough, zone, role pickup/drop-off, giờ và thời tiết | Đạt |

Weather là dữ liệu giờ theo một điểm ở Manhattan. Dải nhiệt độ và mưa là phép so sánh mô tả, không suy ra quan hệ nhân quả. Dữ liệu được lọc theo quy tắc chất lượng của pipeline.

## Hợp đồng dữ liệu

| Bảng | Grain / khóa | Nội dung |
| --- | --- | --- |
| `gold.fact_trip` | Tháng nguồn + `trip_id` | Một chuyến hợp lệ. Có `source_row` để truy vết và FK đến date, weather, pickup zone, drop-off zone. |
| `gold.dim_date` | `date_key` | Ngày, tháng, năm, thứ ISO, cờ cuối tuần. Tạo đủ ngày trong tháng nạp. |
| `gold.dim_zone` | `location_id` | Tên zone, borough và service zone, dùng hai lần khi nối fact. |
| `gold.dim_weather` | `hour_local` | Nhiệt độ, lượng mưa/tuyết quy đổi và số quan sát theo giờ địa phương. |
| `gold.agg_hourly_zone` | Tháng + giờ pickup + pickup zone | Số chuyến, tổng phí, tổng base fare, tổng khoảng cách. |
| `gold.agg_daily_trips` | Tháng + ngày pickup | Số chuyến, tổng phí, khoảng cách và thời lượng trung bình. |
| `gold.agg_zone_revenue` | Tháng + pickup zone | Số chuyến, tổng phí và base fare trung bình. |
| `quarantine.rejected_trip` | `run_id` + `source_row` | Một lý do chính và payload JSON của dòng nguồn. Số dòng bắt đầu từ 1. |
| `audit.pipeline_runs` | `run_id` | Trạng thái, thời điểm, số dòng, danh sách file Bronze kèm SHA-256 và tối đa 5 cặp mẫu. |

## Giải thích dimension Zone

`dim_zone` lưu thuộc tính ổn định của một taxi location: LocationID, tên zone, borough và service zone. `fact_trip` lưu hai khóa ngoại riêng là `pickup_location_id` và `dropoff_location_id`. Cả hai tham chiếu cùng một `dim_zone.location_id`, nhưng đại diện cho hai vai trò khác nhau trong chuyến đi. Đây là role-playing dimension trong star schema. Có thể alias cùng bảng thành `pickup_zone` và `dropoff_zone` trong query. Dữ liệu zone không cần nhân đôi.

Trong sơ đồ use case, người dùng có thể chọn vai trò Pickup hoặc Drop-off. Dashboard mặc định phân tích pickup, và người dùng đổi vai trò khi cần phân tích nơi kết thúc chuyến.

## Luồng xử lý và cách đọc số liệu

1. Ingest TLC Parquet, zone lookup CSV và Open-Meteo JSON. Parquet weather là bản chuyển định dạng để đọc, JSON là response gốc cho lần tải mới. Chế độ cache dùng file có sẵn, dấu vân tay trong audit cho biết chính xác run đã dùng file nào.
2. Great Expectations kiểm các cột bắt buộc của taxi. Silver xử lý từng batch 50.000 dòng trong RAM. Nó kiểm ngày giờ và tháng pickup, mã zone, khoảng cách, thời lượng, tốc độ, fare và total. Thiếu schema, zone key trùng hoặc thiếu coverage weather là lỗi của cả nguồn. Dòng taxi sai quy tắc vào Quarantine.
3. Trip ID là MD5 của pickup/drop-off timestamps, hai zone IDs, khoảng cách, base fare, total và tập thuộc tính nhận dạng tùy chọn như vendor, rate code, loại thanh toán và phụ phí. ID không phụ thuộc vào batch size hay thứ tự dòng. Đây là suy luận từ các cột có sẵn. Hai chuyến thực có bộ thuộc tính trùng hoàn toàn có thể bị gộp.
4. PostgreSQL COPY các dòng sạch vào partition theo tháng. Các FK kiểm toàn vẹn liên kết và ngăn mất chuyến khi nối dimensions. Tổng count và `total_amount` phải khớp giữa fact và từng mart. Nếu lỗi kỹ thuật, transaction rollback và audit ghi lỗi. Nếu mọi dòng bị loại, Quarantine được giữ và Gold đã commit vẫn phục vụ.
5. API dùng tài khoản đọc, transaction read-only và snapshot nhất quán trong mỗi request. Explorer hiển thị proof của một run. Gold browser đọc bảng đang phục vụ hiện tại, kể cả khi người dùng vừa xem một lần chạy lịch sử.

TLC dùng giờ địa phương New York. Open-Meteo tải giờ UTC đến hết ngày kế tiếp để bao trọn giờ New York của tháng. Giờ mùa thu bị lặp được gộp thành một khóa local bằng trung bình các quan sát. Fact gắn cờ `dst_ambiguous` với chuyến pickup trong giờ lặp. Ngày chuyển giờ mùa xuân có 23 local slots. So sánh weather tính cả giờ không có chuyến và tính giờ local lặp là một slot.

Weather là điểm tham chiếu ở Manhattan. Revenue trên web là tổng `total_amount` của các chuyến hợp lệ. Average base fare dùng `fare_amount`. Phân tích dựa trên các chuyến đạt bộ quy tắc chất lượng, bao gồm điều kiện fare và total dương. Các kết quả vì vậy có thể khác tổng báo cáo từ toàn bộ Bronze.
