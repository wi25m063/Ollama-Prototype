import json
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
LOGS_DIR = ROOT / "logs"
RUNS_DIR = LOGS_DIR / "runs"
DATA_DIR = ROOT / "data"
CVS_DIR = DATA_DIR / "cvs"
JOB_FILE = DATA_DIR / "job.txt"
METRICS_FILE = LOGS_DIR / "metrics.csv"

st.set_page_config(page_title="Transparency Dashboard", layout="wide")

# ----------------------------
# Helpers
# ----------------------------
@st.cache_data
def load_metrics():
    if METRICS_FILE.exists():
        df = pd.read_csv(METRICS_FILE)
        # make sure ts is numeric (some csv writers create it as str)
        if "ts" in df.columns:
            df["ts"] = pd.to_numeric(df["ts"], errors="coerce")
        return df
    return pd.DataFrame(columns=["run", "model", "n_samples", "invites", "top1", "ts"])

@st.cache_data
def list_run_files():
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(RUNS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files

def load_run_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def safe_read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")

def ranking_to_df(run_json: dict) -> pd.DataFrame:
    ranking = run_json.get("ranking", [])
    if not ranking:
        return pd.DataFrame(columns=["cv_id", "fit_score", "invite", "reason"])
    df = pd.DataFrame(ranking)
    # keep a clean column order if present
    cols = [c for c in ["cv_id", "fit_score", "invite", "reason", "strengths", "gaps"] if c in df.columns]
    return df[cols]

# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.title("Transparency")
page = st.sidebar.radio(
    "Go to",
    ["Overview", "Run details", "Inputs (Job & CVs)"],
    index=0,
)

metrics = load_metrics()
run_files = list_run_files()

# ----------------------------
# Page: Overview
# ----------------------------
if page == "Overview":
    st.title("Overview")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total runs", len(run_files))
    c2.metric("Metrics rows", len(metrics))
    c3.metric("CV files", len(list(CVS_DIR.glob("*.txt"))) if CVS_DIR.exists() else 0)
    c4.metric("Has job.txt", "Yes" if JOB_FILE.exists() else "No")

    st.subheader("Run metrics (logs/metrics.csv)")
    if metrics.empty:
        st.info("No metrics yet. Run your script once to populate logs/metrics.csv.")
    else:
        st.dataframe(metrics.sort_values(by="ts", ascending=False), use_container_width=True)

        # quick visualization (no extra libs)
        if "invites" in metrics.columns and "run" in metrics.columns:
            st.subheader("Invites per run")
            chart_df = metrics[["run", "invites"]].copy()
            chart_df = chart_df.sort_values("run")
            st.bar_chart(chart_df.set_index("run"))

    st.subheader("Saved run outputs (logs/runs/*.json)")
    if not run_files:
        st.info("No run JSONs found in logs/runs yet.")
    else:
        st.write("Most recent runs:")
        for p in run_files[:10]:
            st.write(f"- {p.name}")

# ----------------------------
# Page: Run details
# ----------------------------
elif page == "Run details":
    st.title("Run details")

    if not run_files:
        st.warning("No run JSON files found in logs/runs.")
        st.stop()

    selected = st.selectbox(
        "Select a run JSON",
        options=run_files,
        format_func=lambda p: p.name,
    )

    run_json = load_run_json(selected)
    df = ranking_to_df(run_json)

    left, right = st.columns([2, 1])

    with left:
        st.subheader("Ranking output")
        if df.empty:
            st.info("This run JSON does not contain a ranking array.")
        else:
            # Show table without huge lists in-line
            display_df = df.copy()
            if "strengths" in display_df.columns:
                display_df["strengths"] = display_df["strengths"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
            if "gaps" in display_df.columns:
                display_df["gaps"] = display_df["gaps"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)

            st.dataframe(display_df, use_container_width=True)

            # chart fit scores
            if "fit_score" in df.columns:
                chart_df = df[["cv_id", "fit_score"]].set_index("cv_id")
                st.subheader("Fit score by CV")
                st.bar_chart(chart_df)

    with right:
        st.subheader("Recommendation & notes")
        st.json(run_json.get("recommendation", {}))
        notes = run_json.get("notes", "")
        if notes:
            st.write(notes)

        st.subheader("Raw run JSON")
        st.download_button(
            "Download JSON",
            data=json.dumps(run_json, indent=2).encode("utf-8"),
            file_name=selected.name,
            mime="application/json",
        )
        with st.expander("Show raw JSON"):
            st.json(run_json)

    # Drill into one CV
    st.divider()
    st.subheader("CV drill-down")

    if df.empty or "cv_id" not in df.columns:
        st.info("No CVs to drill into.")
        st.stop()

    cv_pick = st.selectbox("Select CV", options=df["cv_id"].tolist())
    row = df[df["cv_id"] == cv_pick].iloc[0].to_dict()

    a, b = st.columns(2)
    with a:
        st.markdown(f"### {cv_pick}")
        st.write(f"**fit_score:** {row.get('fit_score')}")
        st.write(f"**invite:** {row.get('invite')}")
        st.write(f"**reason:** {row.get('reason')}")
        st.write("**strengths:**")
        for s in (row.get("strengths") or []):
            st.write(f"- {s}")
        st.write("**gaps:**")
        for g in (row.get("gaps") or []):
            st.write(f"- {g}")

    with b:
        cv_path = CVS_DIR / f"{cv_pick.upper()}.txt"
        if not cv_path.exists():
            # fallback: try exact name
            cv_path = CVS_DIR / f"{cv_pick}.txt"
        st.markdown("### CV text used")
        cv_text = safe_read_text(cv_path)
        if not cv_text:
            st.info(f"Could not find CV file for {cv_pick} in data/cvs/")
        else:
            st.text_area("CV content", cv_text, height=350)

    st.markdown("### Job text used")
    st.text_area("Job content", safe_read_text(JOB_FILE), height=200)

# ----------------------------
# Page: Inputs
# ----------------------------
else:
    st.title("Inputs (Job & CVs)")

    st.subheader("Job description (data/job.txt)")
    job_txt = safe_read_text(JOB_FILE)
    if not job_txt:
        st.warning("data/job.txt not found (or empty).")
    st.text_area("Job", job_txt, height=280)

    st.subheader("CVs (data/cvs/*.txt)")
    cv_files = sorted(CVS_DIR.glob("*.txt")) if CVS_DIR.exists() else []
    if not cv_files:
        st.warning("No CV txt files found in data/cvs/")
        st.stop()

    cv_file = st.selectbox("Select CV file", cv_files, format_func=lambda p: p.name)
    st.text_area("CV", safe_read_text(cv_file), height=420)
