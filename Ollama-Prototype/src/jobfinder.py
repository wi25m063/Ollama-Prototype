import os, csv, time
from pathlib import Path
from statistics import mean
from collections import Counter

from dotenv import load_dotenv
from schemas import CVFit, RankingResult
from llmutils import chat_json

SYSTEM_SCORE = """You are an HR screening assistant.

Return ONLY valid minified JSON (one single line, no markdown, no extra text).

Schema:
{"cv_id":"cv1","fit_score":0.0,"invite":"no","strengths":["..."],"gaps":["..."],"reason":"..."}

STRICT RULES:
- Output MUST be valid JSON and contain ALL fields from the schema
- Do NOT include newline characters or tabs in any string
- strengths MUST contain exactly 3 short bullet phrases
- gaps MUST contain exactly 3 short bullet phrases (never empty)
- reason MUST be 1 short sentence (no line breaks)
- fit_score MUST be a number between 0 and 1

INVITATION RULE:
- invite MUST be "yes" if fit_score >= 0.70, otherwise "no"

SCORING METHOD:
Compute fit_score as a weighted sum of the following criteria:

1) PHP + Framework experience (Laravel, Symfony, Doctrine) — weight 0.40
2) API design and system integration experience — weight 0.20
3) Database experience (SQL and/or NoSQL) — weight 0.15
4) Cloud, infrastructure, security, performance — weight 0.15
5) Product mindset, Agile methods, documentation, English — weight 0.10

Each criterion MUST be scored between 0.0 (no evidence) and 1.0 (strong evidence).
Multiply each score by its weight and sum up to get fit_score.

MUST-HAVE REQUIREMENTS:
1) Professional PHP experience with a framework (Laravel/Symfony/Doctrine)
2) API development or API consumption
3) Relational database experience

If ANY must-have requirement is missing:
- fit_score MUST NOT exceed 0.60
- the missing requirement MUST appear explicitly in gaps

If multiple must-haves are missing:
- fit_score SHOULD be <= 0.40

Be strict, realistic, and consistent across candidates.
"""

SYSTEM_RANK = """You are an HR screening assistant.

Return ONLY valid minified JSON (one single line, no markdown, no extra text).

Schema:
{
  "ranking":[
    {"cv_id":"cv1","fit_score":0.0,"invite":"no","strengths":["..."],"gaps":["..."],"reason":"..."}
  ],
  "recommendation":{"invite":["cv1"],"reject":["cv2"]},
  "notes":"..."
}

STRICT RULES:
- ranking MUST be sorted by fit_score in descending order
- EVERY ranking item MUST contain ALL fields: cv_id, fit_score, invite, strengths, gaps, reason
- strengths MUST contain exactly 3 items
- gaps MUST contain exactly 3 items
- reason MUST be a short single sentence
- notes MUST be short (max 2 sentences)
- Do NOT omit or rename any field

CONSISTENCY RULES:
- recommendation.invite MUST contain exactly the cv_id values with invite == "yes"
- recommendation.reject MUST contain all remaining cv_id values
- If a field value is uncertain, still provide a reasonable placeholder (e.g. "Limited information available")

The ranking must be fair, consistent, and strictly derived from the individual CV scores.
"""
def normalize_list_field(value, min_items=3):
    """
    Ensures the value is a list of strings.
    If a string is provided, wrap it into a list.
    Pads with 'Not specified' if too short.
    """
    if isinstance(value, str):
        value = [value]

    if not isinstance(value, list):
        return ["Not specified"] * min_items

    value = [str(v) for v in value if str(v).strip()]

    while len(value) < min_items:
        value.append("Not specified")

    return value[:min_items]


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")

def list_cvs(folder="data/cvs"):
    return sorted([p for p in Path(folder).glob("*.txt")])

def aggregate_cv_scores(results: list[CVFit]) -> CVFit:
    avg_score = mean(r.fit_score for r in results)
    invite_vote = Counter(r.invite for r in results).most_common(1)[0][0]
    strengths = []
    gaps = []
    for r in results:
        for s in r.strengths:
            if s not in strengths:
                strengths.append(s)
        for g in r.gaps:
            if g not in gaps:
                gaps.append(g)
    reason = results[0].reason  # keep first short reason
    return CVFit(
        cv_id=results[0].cv_id,
        fit_score=avg_score,
        invite=invite_vote,
        strengths=strengths[:4],
        gaps=gaps[:4],
        reason=reason,
    )

def append_metrics(row: dict, path="logs/metrics.csv"):
    Path("logs").mkdir(exist_ok=True)
    file_exists = Path(path).exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            w.writeheader()
        w.writerow(row)

def main():
    load_dotenv()
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    n_samples = int(os.getenv("N_SAMPLES", "5"))
    run_name = os.getenv("RUN_NAME", "v1")

    job = read_text("data/job.txt")

    aggregated = []
    for cv_path in list_cvs():
        cv_id = cv_path.stem  # cv1
        cv_text = read_text(str(cv_path))

        per_run = []
        for _ in range(n_samples):
            user = f"""JOB DESCRIPTION:
{job}

CANDIDATE CV ({cv_id}):
{cv_text}
"""
            data = chat_json(model, SYSTEM_SCORE, user)
            data["strengths"] = normalize_list_field(data.get("strengths"))
            data["gaps"] = normalize_list_field(data.get("gaps"))
            per_run.append(CVFit(**data))

        agg = aggregate_cv_scores(per_run)
        aggregated.append(agg)

        print("\n---", cv_id, "avg_score:", round(agg.fit_score, 3), "invite:", agg.invite)
        print("strengths:", agg.strengths)
        print("gaps:", agg.gaps)

    # final ranking prompt
    summary_block = "\n".join(
        [f"{c.cv_id}: fit_score={c.fit_score:.3f}, invite={c.invite}, strengths={c.strengths}, gaps={c.gaps}"
         for c in aggregated]
    )

    user_rank = f"""JOB DESCRIPTION:
{job}

AGGREGATED CV EVALUATIONS:
{summary_block}

Now produce the final JSON ranking and recommendation.
"""

    rank_data = chat_json(model, SYSTEM_RANK, user_rank)
    result = RankingResult(**rank_data)

    # save run
    Path("logs/runs").mkdir(parents=True, exist_ok=True)
    out_path = Path(f"logs/runs/{run_name}_{int(time.time())}.json")
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    # minimal metrics: top1 + invite count + stability proxies (simple)
    invites = len(result.recommendation.get("invite", []))
    metrics = {
        "run": run_name,
        "model": model,
        "n_samples": n_samples,
        "invites": invites,
        "top1": result.ranking[0].cv_id if result.ranking else "",
        "ts": int(time.time()),
    }
    append_metrics(metrics)

    print("\nFinal ranking saved to:", out_path)
    print("Metrics saved to logs/metrics.csv")

if __name__ == "__main__":
    main()
