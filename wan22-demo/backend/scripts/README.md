# backend/scripts

在 `backend/` 目录下用 venv 执行：

```bash
cd backend
source .venv/bin/activate

python scripts/smoke_api.py
python scripts/verify_dialogue_test_case.py
python scripts/submit_dialogue_test_shot.py --shot 1
python scripts/test_splice.py

python scripts/concat_xfade.py --files a.mp4,b.mp4 --smart-splice
python scripts/analyze_splice.py --files a.mp4,b.mp4
python scripts/detect_duplicate_frames.py --input final.mp4 --json
python scripts/extract_last_frame.py --input a.mp4 --output last.jpg

python scripts/fix_ltx23_api.py --from-blueprint --mode t2v
python scripts/fix_ltx23_flf2v.py
```
