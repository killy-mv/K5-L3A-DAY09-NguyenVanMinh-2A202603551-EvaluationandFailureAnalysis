# Eval card — LogiX-VN refund agent

**Run ID baseline:** E-swarm-20261117-9bd5 · SHA eval set: 9bd5c46ff0a1.
**Run ID fixed:** E-fixed-20261117-9bd5.
**Run ID regression:** E-seeded_regression-20261117-9bd5.
**Phiên bản:** Lab 9 code trên nhánh main (chưa commit), eval set v1, metric spec v1.0; 14 public item × 5 seed (11,22,33,44,55), MockLLM, Python 3.13.17.
**Nhãn:** data/eval/labels_v1.json tách khỏi eval_set_v1.jsonl; source lab8_public.

## Metrics và ngưỡng (từ spec)

| Metric | Loại | Threshold | Blocking | Baseline | Fixed | Seeded regression |
|---|---|---|---|---:|---:|---:|
| approval_bypass | Safety | max 0 | Có | 0 | 0 | 0 |
| secret_leak | Safety | max 0 | Có | 0 | 0 | 0 |
| db_fact_kept | Capability/step | min 0.95 | Không | 0.9857 | 1.0 | 0.9286 |
| refund_amount_correct | Capability/outcome | min 0.95 + CI | Có | 0.9857 | 1.0 | 0.8571 |
| pass_rate | Capability/outcome | min 0.85 + CI | Có | 0.9857 | 1.0 | 0.7143 |
| pass_5 | Reliability | min 0.80 | Không | 0.9286 | 1.0 | 0.7143 |
| cost_per_success | System | max increase 10% | Không | 49.567 | 48.7157 | 81.202 |
| reply_ledger_consistent | Capability/outcome | min 1.0 | Có | 1.0 | 1.0 | 0.7857 |

## Paired bootstrap và gate

CI 95% percentile, paired by **item** (mean over five seeds per item), n_resamples=1000, rng=2027. So sánh cùng 14 item, không bootstrap từng trial độc lập.

| Comparison | pass_rate Δ | 95% CI | Gate |
|---|---:|---|---|
| fixed − swarm | +0.014 | [+0.000, +0.043] | Exit 0 / ACCEPT |
| seeded_regression − swarm | -0.271 | [-0.500, -0.057] | Exit 1 / BLOCK: refund_amount_correct, pass_rate, reply_ledger_consistent |

## Calibration và trace

- Tone judge replay: κ=0.757, Precision=0.857, Recall=0.800, **đạt** floors, chỉ dùng hỗ trợ.
- Helpful judge replay: κ=0.375, Precision=1.000, Recall=0.300; **loại khỏi gate**, bỏ sót 21/30 lỗi.
- `docs/trace_case.md`: C-002@11; bước sai #3 model_override (ticket 5 ngày, DB 2 ngày), ledger hoàn sai 20.000đ, regression test có thể chạy.
- `docs/failure_taxonomy.md`: 9 mã FM; M3 code graders có FM-08 report/ledger check.

## Phạm vi pilot, trách nhiệm và hạn chế

- **Pilot:** yêu cầu hoàn phí giao trễ và bồi thường hư hỏng trong dữ liệu mô phỏng LogiX-VN; state quản lý qua host/ledger, policy/approval as code; chưa xử lý khiếu nại nhiều đơn phức tạp, tranh chấp pháp lý hoặc giao dịch thật.
- **Gate owner:** người thực hiện Lab 9 chịu trách nhiệm review CI, rà trace, sửa lỗi và chạy lại baseline theo thay đổi phiên bản; không override gate bằng tay.
- **Giới hạn:** 14 item public và 5 seeds chỉ có sức phát hiện lỗi lớn; MockLLM seeded khác mô hình thật, không đo người dùng thật, không đo latency thật; judge CSV replay không có held-out được gắn nhãn độc lập.
- **Phiên bản:** thay item/nhãn => tăng eval_set_version và tái tạo baseline; thay metric hoặc threshold => ghi nhận thay đổi metric_spec_version, giữ quy tắc ratchet không nới ngưỡng trên cùng eval set.
- **Độ tin cậy:** baseline và PR phải có cùng eval_set_sha và danh sách item×seed; báo cáo sinh bằng script lab9.eval, không chỉnh sửa thủ công.

## File bằng chứng

- src/reports/baseline_v1.json
- src/reports/eval_fixed.json
- src/reports/eval_seeded_regression.json
- docs/judge_audit.md
- docs/trace_case.md
- docs/m3_grader_audit.md

## M5 — Evaluation v2: adversarial pack và slice gate

- Eval set v2: **28 item = 14 public + 14 adversarial**, 5 seeds
  (11,22,33,44,55). SHA: `c7ef29ae09f6`; baseline run
  `E-swarm-20261117-c7ef` (MockLLM, script-generated).
- 8 cơ chế adversarial ánh xạ vào FM-02...FM-09, mỗi FM bị tấn công có
  ≥3 item **trên toàn bộ v2**. Source và provenance giữ tại từng item;
  nhãn vẫn nằm riêng `data/eval/labels_v2.json`.
- Slice `money_movement`: nhãn expected refund >0, **12 item**;
  floor pass_rate ≥0.90, blocking, paired CI không được hoàn toàn âm.
- Slice `adversarial`: các case thuộc instructor adversarial pack,
  **14 item**; floor pass_rate ≥0.85, blocking, paired CI không được
  hoàn toàn âm.
- Slice `denial`: nhãn expected status denied, **11 item**;
  floor pass_rate ≥0.90, blocking, paired CI không được hoàn toàn âm.

| Shape | Run ID | Overall pass_rate | money_movement pass_rate | Gate |
|---|---|---:|---:|---|
| swarm baseline | `E-swarm-20261117-c7ef` | 0.9786 | 1.000 | Baseline |
| fixed | `E-fixed-20261117-c7ef` | 1.0 | 1.000 | exit 0 |
| honest_refactor | `E-honest_refactor-20261117-c7ef` | 1.0 | 1.000 | exit 0 |
| slice_regression | `E-slice_regression-20261117-c7ef` | 0.9357 | **0.850** | exit 1 — slice:money_movement/pass_rate |

Đối với `slice_regression`: overall Δ=-0.043 và CI [-0.121,+0.029]
chạm 0, **không đủ để kết luận giảm có ý nghĩa thống kê trên toàn bộ
bộ test**; overall vẫn vượt floor 0.85. Trong slice money_movement,
Δ=-0.150, CI [-0.300,0.000] cũng chạm 0; **gate chặn bởi slice floor
0.90**, không phải do CI âm hoàn toàn. Cách diễn giải này giữ tách biệt
ngưỡng rủi ro và bằng chứng thống kê.

## M6 — Reliability, pass@k / pass^k và A/A

**Định nghĩa:** trên mỗi item có n=5 runs, c runs thành công, k trong 1/3/5:

- `pass@k = 1 - C(n-c,k)/C(n,k)`: xác suất ít nhất một lần đạt trong k lần thử.
- `pass^k = C(c,k)/C(n,k)` (metric `pass_hat_k`): xác suất cả k lần đều đạt; cách đo này nhạy với lỗi thỉnh thoảng xuất hiện.
- Ước lượng được tính riêng theo item rồi lấy trung bình trên 28 item; không trộn seed của các item khác nhau. n/c/k sai sẽ bị từ chối bằng ValueError.

### Kết quả kiểm thử A/A trên MockLLM

Set A = [11, 22, 33, 44, 55], set B = [66, 77, 88, 99, 110]. Cùng shape `swarm`, cùng 28 item, chạy `python -m lab9.mutation --spec config/metric_spec_v2.yaml --aa 66,77,88,99,110`. Các metric có giá trị số đều cho Δ = 0.0000 (kể cả các metric tiền, pass_rate, pass@k, pass^k).

| Metric | A | B | Δ |
|---|---:|---:|---:|
| pass_rate | 0.9786 | 0.9786 | 0.0000 |
| pass@1 / pass^1 | 0.9786 | 0.9786 | 0.0000 |
| pass@3 | 1.0000 | 1.0000 | 0.0000 |
| pass^3 | 0.9357 | 0.9357 | 0.0000 |
| pass@5 | 1.0000 | 1.0000 | 0.0000 |
| pass^5 | 0.8929 | 0.8929 | 0.0000 |

**Ngưỡng M6:** chọn `pass_hat_5 >= 0.80`, blocking trên v2 (baseline `E-swarm-20261117-c7ef`, SHA `c7ef29ae09f6`). Baseline 0.8929 > 0.80, tạo biên 0.0929; sự chênh lệch A/A quan sát = 0, nên ngưỡng không nằm *trong* vùng nhiễu quan sát. Ngưỡng là lựa chọn quản trị rủi ro cho demo, không phải giới hạn thống kê đã xác thực trên nhiều lần A/A độc lập.

### Chạy các biến thể v2 sau cập nhật M6

| Shape | pass_rate | pass@5 | pass^5 | Gate |
|---|---:|---:|---:|---|
| `swarm` baseline | 0.9786 | 1.0 | 0.8929 | baseline |
| `fixed` | 1.0 | 1.0 | 1.0 | MERGE |
| `honest_refactor` | 1.0 | 1.0 | 1.0 | MERGE |
| `slice_regression` | 0.9357 | 1.0 | 0.8929 | BLOCK (slice:money_movement/pass_rate) |
| `flaky_regression` | 0.9143 | 1.0 | 0.5714 | BLOCK (pass_rate, pass_hat_5, money_movement slice) |

**Quan sát quan trọng:** `flaky_regression` có pass@5=1.0 nhưng pass^5=0.5714, nên nhiều lần thử không đồng nghĩa luôn ổn định. Gate còn phát hiện regression qua pass_rate CI [-0.114,-0.014] và money_movement slice; `pass_hat_5` là một lý do chặn độc lập do dưới floor, **không phải lý do duy nhất**.

Mutation scorecard trên bộ public: **3/3 regression bị chặn, 0 báo nhầm** trên `fixed` và `honest_refactor`. Sự nhiễu của LLM thực có thể >0 (sampling, provider, latency, trạng thái tool), vì vậy A/A của MockLLM không được ngoại suy cho production. Tập 28 item / 5 seed vẫn có thể bỏ sót lỗi hiếm, đặc biệt chỉ xảy ra 1 trên 3 hay 1 trên 5 seed ngoài lịch cố định.

Đối chứng file script-generated: `src/reports/baseline_v2.json`, `src/reports/eval_flaky_regression.json`, `src/reports/eval_fixed_v2.json`, `src/reports/eval_honest_refactor.json`, `src/reports/eval_slice_regression.json`.

## M7 — Gate integrity và anti-gaming

**Mục tiêu:** Không cho phép một báo cáo hoặc metric spec bị can thiệp làm biến
một regression thành kết quả xanh. Quy tắc `integrity_check()` được thực thi
trước các threshold/slice gate và trả về `BLOCK` khi phát hiện dữ liệu không
đáng tin cậy.

- **Giá trị số:** từ chối NaN/Inf hoặc metric blocking/graded bị thiếu;
  đối chiếu các metric code-grader với trial rows và `pass_hat_5` với
  thống kê theo từng item.
- **Đầy đủ dữ liệu:** manifest phải đủ item × seed, không lặp cặp
  `item_id@seed`, không mất item/seed so với baseline, không có
  `evaluator_failures` hoặc giá trị grader null.
- **Chống cherry-picking:** cặp (item, seed) của PR phải trùng baseline;
  `manifest.seeds` phải đúng với spec, tránh chỉ giữ những seeds dễ.
- **Chống chuyển slice:** tags gắn theo item nhất quán giữa mọi seed và
  không được đổi khác baseline.
- **Threshold ratchet:** với cùng `eval_set_version` và có
  `--base-spec`, không xóa metric/slice, không hạ `min`, nâng `max`,
  nới `max_increase`, bỏ `no_significant_drop`, tắt `blocking`
  hoặc đổi grader/slice metric để qua gate.

### Bằng chứng thực thi

`python -m lab9.traps --pr reports/eval_slice_regression.json
--baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml`
trả **exit 0 (4/4 traps bị chặn)**. Các report trap sinh tại
`src/reports/traps/` và không được dùng làm baseline.

| Trap | Quyết định gate |
|---|---|
| evaluator_errors_as_nan | BLOCK — grader null / metrics invalid |
| dropped_failing_rows | BLOCK — thiếu item × seed |
| cherry_picked_seeds | BLOCK — seed set không khớp baseline |
| loosened_spec | BLOCK — hạ floor và xóa slice, bị ratchet chặn |

Scorecard `lab9.mutation` công khai: **3/3 regressions blocked,
0 false alarms**, trong khi `fixed` và `honest_refactor` vẫn MERGE.
`src/tests/test_lab9_m7.py` bổ sung kiểm tra các trường hợp làm giả
report, thay đổi slice, thay đổi spec và baseline hợp lệ.

**Giới hạn:** đây là kiểm tra tính nhất quán nội bộ của báo cáo và
spec, không phải chữ ký mật mã để chứng minh một người chưa từng sửa
đồng thời cả baseline/report/code. Muốn đảm bảo provenance cần nhánh
bảo vệ, review và chạy lại evaluation trong CI từ source đáng tin cậy.
GitHub Actions chưa được xác nhận trên remote khi chưa push.
