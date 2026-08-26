# instest — MCQ quiz generator from recorded lectures

Record a lecture → clean transcript → multiple-choice questions → Moodle GIFT import. Two Gemini calls (native-audio transcription, then question generation), stdlib-only Python, driven from a Colab notebook.

- **Run it**: open [`notebook/run_qcm.ipynb`](notebook/run_qcm.ipynb) in Google Colab and follow [`notebook/Colab tutorial.md`](notebook/Colab%20tutorial.md).
- **Parameters**: 3-layer YAML cascade — `resources/system.yaml` (global) → `course.yaml` → session yaml (lowest wins). See the tutorial's section D for the complete annotated reference.
- **Code**: `scripts/run_qcm.py` (CLI) + `scripts/lib/` (config cascade, Gemini REST client with audio-compression preflight, GIFT renderer with escaping, cost log).

Requires a Gemini API key (Colab secret `GEMINI_API_KEY`). No other dependency beyond Python stdlib + PyYAML + ffmpeg (both preinstalled in Colab).
