# Judge audit — M2 (Lab 9 cá nhân)

Ngày chạy: 17/11/2026. Backend: replay CSV (không gọi API). Positive class = FAIL: nhiệm vụ judge là phát hiện câu trả lời không đạt. Không sửa nhãn gốc.

## Hiệu chuẩn judge

| Criterion | n | TP | FP | FN | TN | κ | Precision | Recall | Observed → Rogan–Gladen | Floors κ≥0.6, P≥0.8, R≥0.7 | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| tone_ok | 100 | 24 | 4 | 6 | 66 | 0.757 | 0.857 | 0.800 | 0.28 → 0.30 | PASS | Dùng làm tín hiệu hỗ trợ, không thay safety gates |
| helpful | 100 | 9 | 0 | 21 | 70 | 0.375 | 1.000 | 0.300 | 0.09 → 0.30 | FAIL (κ, recall) | Loại khỏi automated gate; hiệu chuẩn lại |

Specificity tone=66/70≈0.943; helpful=70/70=1.0. Corrected failure rate là ước lượng trên replay, không phải tỷ lệ lỗi ngoài đời.

## Audit 12 bất đồng người–judge

| # | Case | Judge | Human CSV | Nhận định audit | Sai ở đâu; sửa rubric thế nào |
|---|---|---|---|---|---|
| 1 | H-008 / tone | PASS | FAIL | Human đúng | Cách xưng em, nha, check quá suồng sã; quy định xưng hô phù hợp ngữ cảnh CSKH. |
| 2 | H-017 / tone | PASS | FAIL | Human đúng theo rubric gốc | Bạn ơi... nha quá thân mật theo note; thêm ví dụ tình huống và phân biệt thân thiện với suồng sã. |
| 3 | H-029 / tone | PASS | FAIL | Human đúng | Không cần nhắn thêm có giọng ra lệnh dù câu mở đầu Dạ, vui lòng; kiểm toàn câu, không chỉ từ khóa lịch sự. |
| 4 | H-042 / tone | FAIL | PASS | Human đúng | Câu ngắn vẫn rõ ràng, lịch sự; không ép xin lỗi trong mọi câu. |
| 5 | H-051 / tone | FAIL | PASS | Human đúng theo quy ước LogiX | Từ refund được bộ nhãn cho phép; whitelist từ nghiệp vụ thay vì phạt mọi từ tiếng Anh. |
| 6 | H-063 / tone | PASS | FAIL | Human đúng | Sẽ hoàn thêm là cam kết chưa được xác minh; thêm tiêu chí không hứa vượt kết quả host. |
| 7 | H-070 / tone | PASS | FAIL | Human đúng | Emoji cười không phù hợp ngữ cảnh khiếu nại; thêm rule về biểu tượng cảm xúc và mức độ nghiêm túc. |
| 8 | H-081 / tone | FAIL | PASS | Judge có khả năng đúng | Note CSV xác nhận nhãn human sai; chuyển cho reviewer thứ hai để sửa nhãn có version, không âm thầm đổi CSV. |
| 9 | HL-015 / helpful | PASS | FAIL | Human đúng | Reply nói hoàn 55.000đ, ghi chú ledger 40.000đ; kiểm bằng code ledger-versus-reply. |
| 10 | HL-020 / helpful | PASS | FAIL | Human đúng | Reply nói 90.000đ, ledger ghi 120.000đ; thêm exact amount consistency; không dựa judge. |
| 11 | HL-047 / helpful | PASS | FAIL | Human đúng theo rubric | Ok bạn... xử lý rồi nhé suồng sã, không nêu kết quả cụ thể; yêu cầu nêu trạng thái rõ. |
| 12 | HL-062 / helpful | PASS | FAIL | Human đúng | Reply 55.000đ, ledger 40.000đ; ngăn misreport FM-08 bằng code grader. |

10/100 tone cases bất đồng (FP=4, FN=6); 21/100 helpful bất đồng (FP=0, FN=21). Các nhãn human và judge được giữ nguyên để các số đo tái lập được.

## Quyết định và hành động

1. Giữ tone_ok như tín hiệu hỗ trợ sau khi review context; sửa rubric theo xưng hô, câu ra lệnh, emoji, cam kết chưa kiểm chứng và ngoại lệ từ chuyên môn.
2. Loại helpful khỏi blocking gate: precision=1.0 không bù được recall=0.3; bỏ sót 21 trong 30 ca human FAIL.
3. Tách helpful: tính đúng tiền/approval/ledger do code grader, còn độ rõ ràng/văn phong có thể do judge được hiệu chuẩn; không dùng LLM phán tiền.
4. Xem lại nhãn H-081 bởi reviewer thứ hai, lưu phiên bản nhãn và không sửa public CSV để ép κ cao.
5. Chạy lại trên held-out mới được gắn nhãn người độc lập, đặc biệt slices sai tiền, xưng hô, câu ngắn lịch sự và câu cam kết không xác thực.

## Chạy lại

- Từ src/: .venv/Scripts/python.exe -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 12
- Từ src/: .venv/Scripts/python.exe -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 12
- Từ src/: .venv/Scripts/python.exe -m pytest -q -m student -o addopts= -k 'confusion_tone or precision_recall_kappa_tone or kappa_undefined or rogan_gladen'

Giới hạn: replay chỉ dùng verdict và nhãn lưu sẵn, không có judge LLM mới, không có held-out hoặc nhãn độc lập; không được khẳng định generalization. Paired bootstrap thuộc M4; pass@k / pass^k thuộc M6.
