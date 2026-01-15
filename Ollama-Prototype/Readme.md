# Transparent LLM-Assisted CV Screening with Local Models (Ollama Prototype)

**Author:** <Your Name>  
**Affiliation:** <Course / University>  
**Repository:** https://github.com/YOUR_ORG/YOUR_REPO  
**Date:** 2026-01-15  

## Abstract
We present a lightweight prototype for LLM-assisted CV screening that emphasizes **structured outputs**, **repeatable runs**, and **transparent logging**. Given a job description and a folder of plain-text CVs, the system (i) scores each CV against explicit must-have criteria using an Ollama-hosted LLM, (ii) reduces variance by sampling multiple times per CV and aggregating scores, and (iii) produces a final ranked shortlist with explanations. A Streamlit dashboard visualizes run history and per-candidate rationales. In a small demonstration (5 synthetic CVs, one PHP Engineer role), the system consistently identified the only web-development-oriented CV as the top candidate and produced internally consistent invite/reject lists.

## 1. Task
The task is **initial screening**: rank candidates for a job opening and decide who should be invited to interview. The prototype targets:
- **Structured decisions:** enforce JSON schemas for downstream use.
- **Consistency:** reduce single-sample LLM randomness via repeated scoring.
- **Auditability:** log full rankings, reasons, and simple run metrics.

## 2. System Overview
### 2.1 Inputs
- `data/job.txt`: job description (plain text)
- `data/cvs/*.txt`: one CV per file (plain text)
- Environment variables:
  - `OLLAMA_HOST` (default `http://localhost:11434`)
  - `OLLAMA_MODEL` (default `llama3.2`)
  - `N_SAMPLES` (default `5`)
  - `RUN_NAME` (default `v1`)

### 2.2 Pipeline
1. **Per-CV scoring (n samples):** the LLM returns JSON with fields:
   `cv_id`, `fit_score` ∈ [0,1], `invite` ∈ {yes,no}, `strengths` (3 items), `gaps` (3 items), and `reason`.
2. **Aggregation:** average `fit_score`, majority vote for `invite`, and deduplicate `strengths/gaps`.
3. **Final ranking:** a second LLM call produces a globally sorted ranking and a `recommendation` object:
   `invite = [cv_id where invite=="yes"]`, `reject = all others`.
4. **Logging:** writes:
   - `logs/runs/<run>_<timestamp>.json` (full results)
   - `logs/metrics.csv` (run summary: model, n_samples, invite count, top1)

### 2.3 Transparency Dashboard
`app.py` provides a Streamlit UI to browse past runs, inspect the job text, compare candidates, and view metrics over time.

## 3. Demonstration Setup
**Job:** “PHP Engineer” (IXOPAY posting excerpt in `data/job.txt`).  
**Candidates:** 5 synthetic CVs (`CV1.txt` … `CV5.txt`).  
**Run artifacts:** `logs/runs/v1_1768298705.json`, `logs/metrics.csv`.

The run metadata recorded:
- Model: `deepseek-v3.1:671b-cloud`
- Samples per CV: 5
- Invites: 1
- Top-ranked CV: `cv5`

## 4. Results
### 4.1 Ranking Outcome
| Rank | CV | Fit score | Invite | Short reason |
|---:|---|---:|:---:|---|
| 1 | cv5 | 0.408 | yes | Strong web development background with payment integration exposure, but lacks specific PHP framework experience. |
| 2 | cv1 | 0.270 | no | Front-end and API experience present, but missing core PHP framework and database skills. |
| 3 | cv2 | 0.066 | no | Strong financial background but lacks technical PHP and API development experience. |
| 4 | cv4 | 0.032 | no | Excellent soft skills but completely lacks required PHP and technical infrastructure experience. |
| 5 | cv3 | 0.000 | no | Management-focused profile with no relevant PHP engineering experience. |

The system invited **only `cv5`**. All other CVs were rejected due to missing must-have requirements (notably PHP + frameworks).

### 4.2 Example Explanation (Top Candidate)
- **Strengths (cv5):** Six years of professional web development experience, Familiarity with e-commerce and payment integrations, Demonstrated project management and collaboration skills
- **Gaps (cv5):** No explicit mention of PHP framework experience required, Limited evidence of API design and system integration, No direct cloud or performance optimization experience

## 5. Discussion
The demonstration shows the end-to-end plumbing working:
- The JSON schema constraints were satisfied (all required fields present).
- The final ranking was sorted by score and the recommendation lists were consistent with per-item invites.
- Logging enables post-hoc inspection and run-to-run comparisons.

## 6. Limitations
- **No ground-truth labels:** this prototype demonstrates mechanics, not validated hiring accuracy.
- **LLM bias and hallucination risk:** explanations can be persuasive even when incorrect; human review is required.
- **Input quality:** plain-text CV parsing is simplistic; real CVs may require robust extraction.
- **Cost/performance tradeoffs:** multi-sample scoring improves stability but increases latency.

## 7. Ethical & Practical Notes
This tool should support—never replace—human decision-making. Recommended safeguards:
- Keep explicit must-have criteria and enforce them strictly.
- Provide candidates a way to contest obvious extraction errors.
- Log versions of prompts/models and apply consistent evaluation policies.

## 8. Conclusion
We built a small, reproducible CV-screening prototype that uses local/remote Ollama models to produce structured, auditable rankings and a transparency dashboard. Next steps include adding test suites, bias checks, and evaluation against labeled screening datasets.

## How to run
```bash
python -m venv .venv 
source .venv/bin/activate
pip install -r requirements.txt

# ensure Ollama is running and the model is available
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="deepseek-v3.1:671b-cloud"
export N_SAMPLES="5"
export RUN_NAME="v1"

python src/jobfinder.py
streamlit run app.py
```
