# Project Context — XSMN Latest-State SQLite Store

Tài liệu này tổng hợp cấu trúc mã nguồn, công nghệ, quy ước kỹ thuật và nguyên tắc làm việc cho dự án lưu trữ và đồng bộ kết quả Xổ số kiến thiết miền Nam (XSMN) theo mô hình **latest-state overwrite**.

---

## 1. Tech Stack & Dependencies

- **Runtime & Language:**
  - Node.js (ESM - `"type": "module"`), TypeScript `^5.6.0` (target `ES2022`, `module`/`moduleResolution`: `NodeNext`, `strict: true`).
  - Python 3 (dùng hoàn toàn Python standard library: `sqlite3`, `dataclasses`, `json`, `html.parser`, `urllib.request`, `unittest`; không yêu cầu cài thêm package ngoài).
- **Database Engine:** SQLite nhúng trong file cục bộ `lottery_latest.db` (không cần DB server ngoài).
- **Dependencies (`package.json`):**
  - `better-sqlite3` (`^11.0.0`): Driver SQLite đồng bộ, hiệu năng cao cho Node.js.
- **DevDependencies (`package.json`):**
  - `@types/better-sqlite3` (`^7.6.11`): Type definitions cho `better-sqlite3`.
  - `@types/node` (`^22.0.0`): Type definitions cho Node.js API (`node:fs`, `node:path`, `node:url`).
  - `tsx` (`^4.19.0`): Chạy trực tiếp file TypeScript (`npm run ingest`).
  - `typescript` (`^5.6.0`): Biên dịch TypeScript (`npm run build`).

---

## 2. Project Architecture

```text
Lotto/
├── context.md           # Tài liệu ngữ cảnh, kiến trúc và quy ước của dự án
├── package.json         # Khai báo ESM, scripts (build, ingest) và dependencies
├── tsconfig.json        # Cấu hình TypeScript strict + NodeNext
├── schema.sql           # DDL khởi tạo bảng latest_lottery_results (WITHOUT ROWID) và index
├── lottery_latest.db    # File SQLite lưu trạng thái mới nhất của 21 đài
├── lottery_latest.json  # Snapshot JSON tĩnh (auto-export sau mỗi lần cập nhật DB) cho Web UI
└── src/
    ├── provinces.ts     # Danh mục chuẩn 21 tỉnh/thành XSMN và lịch quay trong tuần
    ├── types.ts         # Kiểu dữ liệu XsmnPrizes, LotterySyncInput, LatestLotteryResult, LotteryExportPayload
    ├── db.ts            # Hàm openLotteryDb() mở kết nối SQLite và thực thi schema.sql
    ├── ingest.ts        # Hàm syncLatestLotteryResults(), syncAndExportLatestLotteryResults() + CLI seed 21 đài
    └── queries.ts       # Đọc nhanh DB & export JSON tĩnh (exportLatestResultsToJson)
├── lotto_store/         # Interface Python (stdlib sqlite3) Đọc-Ghi-Truy vấn-Xóa, Export JSON & Scraper
│   ├── __init__.py      # Re-export toàn bộ public API
│   ├── provinces.py     # Danh mục 21 tỉnh XSMN & normalize_province_code()
│   ├── models.py        # XsmnPrizes, LotterySyncInput, LatestLotteryResult & validation
│   ├── db.py            # open_lottery_db(), lottery_db_session(), DEFAULT_EXPORT_JSON_PATH
│   ├── operations.py    # CRUD + query_results + build_export_payload, export_results_to_json
│   └── scraper.py       # Fetch & parse HTML từ xsmn.mobi, sync SQLite và tự động export JSON
├── sync_xsmn.py         # CLI entrypoint chạy đồng bộ kết quả XSMN từ xsmn.mobi
├── .github/
│   └── workflows/
│       └── sync-xsmn.yml # GitHub Actions cron chạy đồng bộ định kỳ lúc 17:00 ICT (10:00 UTC)
├── index.html           # Giao diện Web UI tĩnh (MVP v1.0) dò vé số XSMN
├── web/                 # Tài nguyên frontend (ES Modules & CSS, không cần build step)
│   ├── app.js           # Tải lottery_latest.json, quản lý form & render bảng kết quả
│   ├── checker.js       # Logic dò vé số 6 chữ số chuẩn XSMN (Giải 8 → Đặc Biệt, Phụ ĐB, Khuyến Khích)
│   └── styles.css       # Giao diện responsive và highlight số trúng thưởng
└── tests/
    ├── test_lotto_store.py # Unit tests cho tầng interface Python & JSON export
    └── test_scraper.py     # Unit tests cho HTML parser, luồng sync & auto-export JSON
```

### Vai trò từng module chính
- **`schema.sql`**: Định nghĩa bảng duy nhất `latest_lottery_results` với `province_code` làm `PRIMARY KEY` (dùng `WITHOUT ROWID`), bật `WAL` mode, kiểm tra định dạng `draw_date` (`YYYY-MM-DD`) và `json_valid(prizes)`, kèm index `idx_latest_lottery_draw_date` trên `draw_date DESC`.
- **`src/provinces.ts`**: Nguồn chân lý (single source of truth) cho 21 mã tỉnh XSMN (`XSMN_PROVINCES`, `XsmnProvinceCode`, `XSMN_PROVINCE_MAP`).
- **`src/types.ts`**: Định nghĩa cấu trúc giải thưởng `XsmnPrizes` (từ `giai8` đến `dacBiet`), input đồng bộ (`LotterySyncInput`), ánh xạ row SQLite (`LatestLotteryRow` → `LatestLotteryResult`) và cấu trúc JSON export (`ExportedLotteryResult`, `LotteryExportPayload`).
- **`src/db.ts`**: Quản lý mở file `lottery_latest.db` và áp dụng `schema.sql` khi khởi tạo.
- **`src/ingest.ts`**: Thực hiện `INSERT OR REPLACE INTO latest_lottery_results` bên trong `db.transaction(...)` (`syncLatestLotteryResults`, `syncAndExportLatestLotteryResults`); hỗ trợ chạy trực tiếp qua CLI để seed dữ liệu mẫu cho 21 tỉnh và tự động export ra `lottery_latest.json`.
- **`src/queries.ts`**: Truy vấn toàn bộ các tỉnh đang hoạt động (`getAllLatestResults`), tra cứu theo mã tỉnh (`getLatestResultByProvince`), và export toàn bộ bảng atomic sang JSON tĩnh (`buildExportPayload`, `exportLatestResultsToJson`).
- **`lotto_store/provinces.py`**: Danh mục 21 tỉnh XSMN (`XSMN_PROVINCES`, `XSMN_PROVINCE_MAP`) và hàm chuẩn hóa `normalize_province_code()`.
- **`lotto_store/models.py`**: Các dataclass bất biến (`XsmnPrizes`, `LotterySyncInput`, `LatestLotteryResult`) kèm validation bảng chuẩn `PRIZE_SPEC`, định dạng `YYYY-MM-DD` và giữ nguyên key JSON `"dacBiet"` để đồng bộ với TypeScript.
- **`lotto_store/db.py`**: Định nghĩa `DEFAULT_DB_PATH`, `DEFAULT_EXPORT_JSON_PATH` (`lottery_latest.json`), hàm `open_lottery_db()` và context manager `lottery_db_session()` mở SQLite, bật `sqlite3.Row` và thực thi `schema.sql`.
- **`lotto_store/operations.py`**: Bộ interface Đọc–Ghi–Truy vấn–Xóa (`upsert_result`, `sync_results`, `get_all_results`, `get_result_by_province`, `count_results`, `query_results`, `delete_result_by_province`, `delete_results_by_date`, `clear_all_results`) và export JSON tĩnh (`build_export_payload`, `export_results_to_json`). Hỗ trợ gọi hàm trực tiếp (tự mở/đóng DB) hoặc truyền `conn=` để tái sử dụng kết nối.
- **`lotto_store/scraper.py`**: Module thu thập và parse kết quả XSMN từ `https://xsmn.mobi/` bằng `urllib.request` và `html.parser` (`fetch_xsmn_html`, `parse_xsmn_mobi_html`, `sync_from_xsmn_mobi`). Tự động ánh xạ `data-pcode` (bao gồm `hcm` → `TPHCM`), giữ ngày quay mới nhất khi một đài xuất hiện nhiều lần, bỏ qua đài đang quay dở dang, hỗ trợ `only_if_newer` / `--dry-run` / `--force`, và tự động export toàn bộ DB ra `lottery_latest.json` (hoặc `--export-json` / `--no-export`) sau khi cập nhật xong.
- **`sync_xsmn.py`**: Script CLI ở thư mục gốc gọi `lotto_store.scraper.main()` để đồng bộ nhanh dữ liệu vào `lottery_latest.db`.
- **`.github/workflows/sync-xsmn.yml`**: GitHub Actions workflow chạy tự động hằng ngày lúc `17:00` giờ Việt Nam (`10:00 UTC`), hỗ trợ `workflow_dispatch`, thực thi `python sync_xsmn.py`, chạy unit tests và tự động commit/push `lottery_latest.db` cùng `lottery_latest.json` nếu có thay đổi.
- **`index.html` & `web/`**: Giao diện Web UI tĩnh (MVP v1.0) đọc trực tiếp `lottery_latest.json` qua HTTP (không cần build step):
  - `index.html`: Cấu trúc trang gồm form dò vé (nhập mã số dự thưởng 6 chữ số, chọn tỉnh/thành XSMN, chọn ngày xổ số) và bảng kết quả mở thưởng.
  - `web/checker.js`: Logic dò vé 6 chữ số chuẩn XSMN (`checkXsmnTicket`, `PRIZE_ROWS`), hỗ trợ Giải Tám → Đặc Biệt, Giải Phụ Đặc Biệt và Giải Khuyến Khích.
  - `web/app.js`: Fetch `lottery_latest.json`, đồng bộ lựa chọn đài/ngày (kèm gợi ý nhanh các đài quay trong ngày đã chọn và thông báo khi ngày chọn khác kỳ quay mới nhất), và highlight các số trúng trên bảng.
  - `web/styles.css`: Styling responsive, font monospace `tabular-nums` cho các dãy số trúng thưởng.
- **`tests/test_lotto_store.py`**: Bộ unit test (`unittest`) kiểm tra vòng đời CRUD, cơ chế ghi đè latest-state, tính tương thích JSON và validation.
- **`tests/test_scraper.py`**: Bộ unit test (`unittest`) kiểm tra parse bảng HTML 3–4 đài, loại trùng ngày mới nhất, bỏ qua kết quả chưa hoàn chỉnh và cơ chế `only_if_newer`.

---

## 3. Coding Conventions

- **ESM & Import Paths:** Dự án dùng `"type": "module"` với `NodeNext`. Mọi local import trong `src/` phải có đuôi `.js` (ví dụ: `import { openLotteryDb } from "./db.js"`), và built-in Node modules dùng prefix `node:` (ví dụ: `node:fs`, `node:url`).
- **Database & Retention Policy:**
  - **Không lưu lịch sử 30–45 ngày.** Mỗi `province_code` chỉ tồn tại tối đa 1 dòng duy nhất trong `latest_lottery_results`.
  - Mọi thao tác cập nhật kết quả mới phải ghi đè nguyên tử bằng `INSERT OR REPLACE` trong `db.transaction(...)`.
- **Naming Conventions:**
  - Cột SQLite dùng `snake_case` (`province_code`, `draw_date`, `prizes`, `updated_at`).
  - TypeScript interface/type dùng `PascalCase` (`XsmnPrizes`, `LotterySyncInput`), thuộc tính/hàm dùng `camelCase` (`provinceCode`, `syncLatestLotteryResults`).
  - Python dùng `PascalCase` cho dataclass (`XsmnPrizes`, `LotterySyncInput`, `LatestLotteryResult`) và `snake_case` cho hàm/thuộc tính (`province_code`, `dac_biet`, `query_results`), nhưng khi serialize JSON vào cột `prizes` vẫn giữ key chuẩn `"dacBiet"`.
  - Mã tỉnh (`province_code`) luôn chuẩn hóa viết hoa, bỏ khoảng trắng (`trim().toUpperCase()`), khớp với `XsmnProvinceCode`.
- **Dữ liệu số trúng thưởng:** Tất cả các số trong `XsmnPrizes` bắt buộc lưu dưới dạng `string` (không dùng `number`) để bảo toàn số `0` ở đầu (ví dụ: `"05"`, `"094812"`).
- **Type Safety:** Giữ `strict: true` trong `tsconfig.json`; ưu tiên dùng `import type` cho type-only imports.

---

## 4. Current Status & Guidelines

### Trạng thái hiện tại
- **Hoàn thành tầng Database TypeScript:** Đã hoàn thiện schema SQLite (`latest_lottery_results` với `WITHOUT ROWID`), type definitions, danh mục đủ 21 tỉnh/thành XSMN, module kết nối (`src/db.ts`), logic ingest ghi đè (`INSERT OR REPLACE` trong `src/ingest.ts`) và query helpers (`src/queries.ts`).
- **Hoàn thành tầng Interface Python (`lotto_store/`):** Đã triển khai đầy đủ các hàm Đọc–Ghi–Truy vấn–Xóa trong `lotto_store/operations.py`, hỗ trợ lọc 2 tầng (SQLite + Python) và tương thích hoàn toàn với `schema.sql` / JSON của TypeScript.
- **Hoàn thành Crawler, HTML Parser & Auto-Export JSON (`lotto_store/scraper.py`, `sync_xsmn.py`):** Đã triển khai bộ parse HTML từ `https://xsmn.mobi/` thuần Python stdlib, đồng bộ thực tế thành công **21/21 đài** vào `lottery_latest.db`, và tự động export atomic toàn bộ DB ra `lottery_latest.json` (gồm `exportedAt`, `totalProvinces`, `results` kèm `provinceName`, `drawDays`, `drawDate`, `updatedAt`, `prizes`) sau khi cập nhật xong. Đã kiểm thử toàn bộ với `python -m unittest discover -s tests -v` (8/8 tests passed).
- **Hoàn thành Web UI tĩnh — MVP v1.0 (`index.html`, `web/`):** Đã xây dựng giao diện dò vé số XSMN đọc trực tiếp từ `lottery_latest.json`, gồm ô nhập mã số dự thưởng 6 chữ số (giữ số `0` ở đầu), ô chọn 21 tỉnh/thành XSMN, ô chọn ngày xổ số (tự động đồng bộ kỳ quay mới nhất và gợi ý các đài theo ngày), logic dò đầy đủ Giải Tám → Đặc Biệt + Phụ Đặc Biệt + Khuyến Khích, và bảng kết quả tự động highlight số trúng.
- **Hoàn thành lịch chạy đồng bộ định kỳ (`.github/workflows/sync-xsmn.yml`):** Đã thiết lập GitHub Actions cron chạy hằng ngày lúc `17:00` ICT (`0 10 * * *` UTC) và hỗ trợ chạy thủ công (`workflow_dispatch`) để cập nhật `lottery_latest.db` và `lottery_latest.json`.
- **Bước tiếp theo:** Bổ sung kiểm thử tự động cho logic frontend (`web/checker.js`), triển khai tĩnh (ví dụ GitHub Pages) hoặc mở rộng tính năng cho các phiên bản sau MVP v1.0.
- **Môi trường chạy:** Python 3.15.2 đã khả dụng và chạy test thành công; `node` và `npm` chưa khả dụng trong shell môi trường hiện tại, nên chưa chạy `npm install`, `npm run build` hay `npm run ingest`.

### Quy tắc cần tuân thủ trong các bước tiếp theo
1. **Giữ đúng mô hình Latest-State:** Không tự ý thêm bảng lịch sử, cột lịch sử hay logic lưu trữ nhiều ngày cho cùng một `province_code` trừ khi có yêu cầu thay đổi kiến trúc.
2. **Bảo toàn định dạng dữ liệu XSMN:** Luôn giữ số trúng thưởng ở dạng `string` (đúng số chữ số từng giải từ Giải 8 đến Đặc Biệt) và chuẩn hóa `provinceCode` theo `XsmnProvinceCode`.
3. **Đồng bộ TypeScript ESM (`NodeNext`):** Mọi file mới hoặc chỉnh sửa trong `src/` phải giữ đuôi `.js` khi import tương đối và vượt qua `tsc` với `strict: true`.
4. **Trung thực về kiểm thử:** Chỉ báo cáo build/ingest thành công khi thực sự chạy được lệnh kiểm tra trong môi trường có Node.js.
5. **Cập nhật `context.md`:** Khi có thay đổi lớn về schema, dependencies hoặc kiến trúc module, cần cập nhật lại tài liệu này cho đồng bộ.

