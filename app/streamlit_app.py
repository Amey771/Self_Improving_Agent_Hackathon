# app/streamlit_app.py
import streamlit as st
from pathlib import Path
import time
import difflib

from src.config import Settings
from src.integrations.datadog_client import DatadogClient
from src.agents.triage_agent import TriageAgent
from src.integrations.elevenlabs_tts import ElevenLabsTTS
from src.agents.trace_agent import TraceAgent
from src.agents.fix_agent import FixAgent
from src.integrations.braintrust_client import BraintrustClient
from src.core.verify_patch import verify_div0_guard_exists
from src.agents.llm_patch import LLMPatchAgent
from src.core.apply_llm_patch import apply_full_file_patch
from src.core.eval_metrics import compute_metrics
from src.integrations.braintrust_client import BraintrustClient
from src.core.verify_patch import verify_div0_guard_exists


# -----------------------------
# Page + Styling
# -----------------------------
st.set_page_config(page_title="VoiceOps", page_icon="🎙️", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; }
      .vo-card {
        border-radius: 18px;
        padding: 16px 18px;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
      }
      .vo-title {
        font-size: 44px;
        font-weight: 800;
        line-height: 1.05;
        margin-bottom: 0.4rem;
      }
      .vo-subtitle {
        font-size: 16px;
        opacity: 0.9;
      }
      .vo-badge {
        display: inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 700;
        background: linear-gradient(90deg, rgba(255,70,70,0.25), rgba(255,210,0,0.25), rgba(80,200,255,0.25));
        border: 1px solid rgba(255,255,255,0.12);
      }
      div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 10px 12px;
      }
      .stButton button {
        border-radius: 14px !important;
        font-weight: 700 !important;
      }
      .stButton button[kind="primary"]{
        background: linear-gradient(90deg, #ff3b3b, #ffd000, #41d1ff) !important;
        color: #000 !important;
        border: 0 !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="vo-card">
      <div class="vo-title">VoiceOps</div>
      <div class="vo-subtitle">
        Self-Improving Voice Incident Agent • <span class="vo-badge">Datadog + ElevenLabs + Braintrust</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")


# -----------------------------
# Sidebar navigation
# -----------------------------
st.sidebar.title("🚀 VoiceOps Control Center")
page = st.sidebar.radio(
    "Navigate",
    ["1) Monitor", "2) Trace", "3) Voice", "4) Patch", "5) Evaluate"],
    index=0,
)
st.sidebar.divider()

repo_path = st.sidebar.text_input("Repo path (local)", value=".")
demo_mode = st.sidebar.toggle("Demo Mode (always generate incident)", value=True)
service = st.sidebar.text_input("Service name", value="api")
minutes = st.sidebar.slider("Lookback window (minutes)", 1, 30, 5)

st.sidebar.divider()
st.sidebar.subheader("Config status")
st.sidebar.write(
    {
        "DD_API_KEY": bool(Settings.DD_API_KEY),
        "DD_APP_KEY": bool(Settings.DD_APP_KEY),
        "ELEVENLABS_API_KEY": bool(getattr(Settings, "ELEVENLABS_API_KEY", None)),
        "ELEVENLABS_VOICE_ID": bool(getattr(Settings, "ELEVENLABS_VOICE_ID", None)),
        "BRAINTRUST_API_KEY": bool(getattr(Settings, "BRAINTRUST_API_KEY", None)),
    }
)

# -----------------------------
# Session state
# -----------------------------
if "incident" not in st.session_state:
    st.session_state["incident"] = None
if "trace" not in st.session_state:
    st.session_state["trace"] = None
if "patch_result" not in st.session_state:
    st.session_state["patch_result"] = None
if "eval_result" not in st.session_state:
    st.session_state["eval_result"] = None
if "llm_patch_text" not in st.session_state:
    st.session_state["llm_patch_text"] = None
if "eval_metrics" not in st.session_state:
    st.session_state["eval_metrics"] = None


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def _count_guard_occurrences(file_text: str) -> int:
    # simple heuristic for your demo: counts common guard pattern occurrences
    # tweak if your FixAgent uses a different exact string
    return file_text.count("if installments == 0")


def _unified_diff(before: str, after: str, filename: str) -> str:
    diff = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="",
    )
    return "\n".join(diff)


def _safe_target_path(repo_root: str, suspected_file: str) -> Path:
    # suspected_file is usually "billing.py"
    return Path(repo_root).resolve() / suspected_file


# -----------------------------
# 1) Monitor: Fetch + Triage
# -----------------------------
if page == "1) Monitor":
    st.subheader("📡 Monitor: Fetch Incident (real-time logs)")

    colA, colB = st.columns([1, 2], gap="large")
    with colA:
        run_fetch = st.button("Fetch Incident", type="primary", use_container_width=True)

    if run_fetch:
        dd = DatadogClient()

        if demo_mode:
            incident = dd.simulate_incident(service)
        else:
            incident = dd.fetch_incident(service, minutes)

        triage = TriageAgent()
        incident = triage.enrich_incident(incident)

        st.session_state["incident"] = incident
        st.session_state["trace"] = None
        st.session_state["patch_result"] = None
        st.session_state["eval_result"] = None

    incident = st.session_state["incident"]
    if incident:
        st.success("Incident detected + triaged ✅")
        m1, m2, m3 = st.columns(3)
        m1.metric("Service", incident.service)
        m2.metric("Severity", str(incident.severity))
        m3.metric("Log fingerprints", str(len(getattr(incident, "log_fingerprints", []) or [])))
        st.json(incident.model_dump())
    else:
        st.info("Click **Fetch Incident** to begin.")


# -----------------------------
# 2) Trace
# -----------------------------
if page == "2) Trace":
    st.subheader("🧭 Trace: Locate the likely file/line")

    incident = st.session_state["incident"]
    if not incident:
        st.warning("No incident in session. Go to **1) Monitor** and fetch an incident first.")
    else:
        if st.button("Run Trace", type="primary"):
            trace_agent = TraceAgent()
            trace = trace_agent.trace(repo_path, incident)
            st.session_state["trace"] = trace

        trace = st.session_state["trace"]
        if trace:
            st.success("Trace complete ✅")
            c1, c2 = st.columns([1, 1])
            c1.metric("Suspected files", str(len(trace.suspected_files or [])))
            c2.metric("Snippets matched", str(len(trace.matched_snippets or [])))

            st.write("**Hypothesis:**", trace.hypothesis)
            st.write("**Suspected files:**", trace.suspected_files)

            if trace.matched_snippets:
                st.code("\n\n".join(trace.matched_snippets), language="python")
            else:
                st.info("No snippets matched. Make sure the repo path points to a folder that contains billing.py.")


# -----------------------------
# 3) Voice
# -----------------------------
if page == "3) Voice":
    st.subheader("🎙️ Voice: Readout for incident + hypothesis")

    incident = st.session_state["incident"]
    trace = st.session_state["trace"]

    if not incident or not trace:
        st.warning("Need both Incident and Trace. Run **1) Monitor** then **2) Trace**.")
    else:
        voice_text = (
            f"{incident.summary}. "
            f"Service is {incident.service}. Severity {incident.severity}. "
            f"Trace hypothesis: {trace.hypothesis}. "
            f"Say 'apply patch' to fix locally."
        )

        st.text_area("What the agent will speak", value=voice_text, height=140)

        if st.button("Generate Voice Summary", type="primary"):
            try:
                tts = ElevenLabsTTS()
                audio_path = tts.synthesize_to_file(voice_text)
                with open(audio_path, "rb") as f:
                    st.audio(f.read(), format="audio/mpeg")
                st.caption("Voice generated by ElevenLabs ✅")
            except Exception as e:
                st.error(f"Voice generation failed: {e}")


# -----------------------------
# 4) Patch
# -----------------------------
if page == "4) Patch":
    st.subheader("🛠️ Patch: Gemini-generated local fix (no git)")

    incident = st.session_state.get("incident")
    trace = st.session_state.get("trace")

    if not incident:
        st.warning("No incident found. Run **1) Monitor** first.")
    elif not trace or not trace.suspected_files:
        st.warning("No suspected file. Run **2) Trace** first.")
    else:
        suspected = trace.suspected_files[0]
        target_path = _safe_target_path(repo_path, suspected)

        st.write("**Target file:**", str(target_path))

        if not target_path.exists():
            st.error("Target file not found. Repo path should be a folder that contains the file.")
        else:
            before = _read_text(target_path)

            st.write("Preview (current file excerpt):")
            st.code("\n".join(before.splitlines()[:120]), language="python")

            col1, col2 = st.columns([1, 1])

            with col1:
                if st.button("Generate Patch with Gemini", type="primary"):
                    try:
                        agent = LLMPatchAgent()
                        patched_text = agent.suggest_patch(
                            file_name=target_path.name,
                            file_text=before,
                            incident_summary=incident.summary,
                            trace_hypothesis=trace.hypothesis,
                        )
                        st.session_state["llm_patch_text"] = patched_text
                        st.session_state["patch_result"] = None
                        st.session_state["eval_metrics"] = None
                        st.success("Gemini generated patch ✅")
                    except Exception as e:
                        st.error(f"Gemini patch generation failed: {e}")

            with col2:
                if st.button("Clear Patch Draft"):
                    st.session_state["llm_patch_text"] = None
                    st.session_state["patch_result"] = None
                    st.session_state["eval_metrics"] = None
                    st.info("Cleared patch draft.")

            patched_text = st.session_state.get("llm_patch_text")

            if patched_text:
                st.subheader("LLM Patch Preview (first 140 lines)")
                st.code("\n".join(patched_text.splitlines()[:140]), language="python")

                if st.button("Apply LLM Patch Locally", type="primary"):
                    try:
                        t0 = time.time()
                        apply_full_file_patch(str(target_path), patched_text)
                        t1 = time.time()

                        after = _read_text(target_path)
                        diff = _unified_diff(before, after, suspected)

                        m = compute_metrics(before, after)

                        st.session_state["patch_result"] = {
                            "message": "LLM patch applied locally ✅",
                            "target_file": suspected,
                            "target_path": str(target_path),
                            "time_sec": round(t1 - t0, 3),
                            "diff": diff[:8000],
                        }
                        st.session_state["eval_metrics"] = m

                        st.success("LLM patch applied locally ✅")
                    except Exception as e:
                        st.error(f"Apply patch failed: {e}")

            patch_result = st.session_state.get("patch_result")
            eval_metrics = st.session_state.get("eval_metrics")

            if patch_result:
                st.write("")
                st.subheader("Patch Result")

                a, b = st.columns(2)
                a.metric("Patch time (s)", str(patch_result["time_sec"]))
                b.metric("Patch applied", "Yes" if (eval_metrics and eval_metrics.get("patch_applied")) else "No")

                if eval_metrics:
                    c, d, e = st.columns(3)
                    c.metric("Guards before", str(eval_metrics.get("guard_count_before")))
                    d.metric("Guards after", str(eval_metrics.get("guard_count_after")))
                    e.metric("Duplicate guard", "⚠️" if eval_metrics.get("duplicate_guard") else "No")

                    if eval_metrics.get("duplicate_guard"):
                        st.warning("Duplicate guard detected. Ask Gemini for a minimal patch that does not duplicate checks.")

                st.write("Diff preview:")
                st.code(patch_result["diff"], language="diff")


# -----------------------------
# 5) Evaluate (Braintrust)
# -----------------------------
if page == "5) Evaluate":
    st.subheader("📊 Evaluate: Verify + score patch, then log to Braintrust")

    incident = st.session_state.get("incident")
    trace = st.session_state.get("trace")
    patch_result = st.session_state.get("patch_result")
    eval_metrics = st.session_state.get("eval_metrics")  # from LLM patch page

    if not trace or not trace.suspected_files:
        st.warning("Need Trace first.")
    elif not patch_result:
        st.warning("Apply a patch first in **4) Patch**.")
    else:
        suspected = trace.suspected_files[0]
        target_path = _safe_target_path(repo_path, suspected)

        if not target_path.exists():
            st.error("Target file not found.")
        else:
            file_text = _read_text(target_path)

            # Core verification
            ok = verify_div0_guard_exists(str(target_path))

            # File-level metrics (post-patch)
            guard_count = _count_guard_occurrences(file_text)
            duplicate_guard = guard_count > 1

            # Prefer eval_metrics computed from before/after (if available)
            guard_before = eval_metrics.get("guard_count_before") if eval_metrics else None
            guard_after = eval_metrics.get("guard_count_after") if eval_metrics else guard_count
            patch_applied = eval_metrics.get("patch_applied") if eval_metrics else True

            metrics = {
                "patch_verified": bool(ok),
                "patch_applied": bool(patch_applied),
                "guard_count_before": guard_before,
                "guard_count_after": int(guard_after) if guard_after is not None else int(guard_count),
                "duplicate_guard": bool(duplicate_guard),
                "target_file": suspected,
                "target_path": str(target_path),
                "service": (incident.service if incident else "unknown"),
                "severity": (str(incident.severity) if incident else "unknown"),
                "trace_hypothesis": (trace.hypothesis if trace else ""),
                "patch_time_sec": patch_result.get("time_sec"),
            }

            st.session_state["eval_result"] = metrics

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Verified", "✅" if metrics["patch_verified"] else "❌")
            m2.metric("Applied", "✅" if metrics["patch_applied"] else "❌")
            m3.metric("Guards after", str(metrics["guard_count_after"]))
            m4.metric("Duplicate guard", "⚠️" if metrics["duplicate_guard"] else "No")

            if metrics["duplicate_guard"]:
                st.warning("Duplicate guard detected. Ask Gemini for a minimal patch that avoids repeating checks.")

            st.write("Evaluation details:")
            st.json(metrics)

            # Scores for Braintrust
            scores = {
                "verified": 1.0 if metrics["patch_verified"] else 0.0,
                "patch_applied": 1.0 if metrics["patch_applied"] else 0.0,
                "no_duplicates": 1.0 if not metrics["duplicate_guard"] else 0.0,
            }

            # A clean, judge-friendly record
            bt_input = {
                "incident_summary": (incident.summary if incident else ""),
                "fingerprint": (incident.log_fingerprints[0] if incident and incident.log_fingerprints else ""),
                "service": metrics["service"],
                "severity": metrics["severity"],
                "target_file": metrics["target_file"],
            }

            bt_output = {
                "trace_hypothesis": metrics["trace_hypothesis"],
                "patch_verified": metrics["patch_verified"],
                "guard_count_after": metrics["guard_count_after"],
                "duplicate_guard": metrics["duplicate_guard"],
            }

            bt_metadata = {
                "target_path": metrics["target_path"],
                "patch_time_sec": metrics["patch_time_sec"],
                "diff_preview": (patch_result.get("diff") or "")[:2000],
                "repo_path": str(Path(repo_path).resolve()),
                "mode": "llm_patch",
                "model": str(getattr(Settings, "GEMINI_MODEL", "gemini")),
            }

            if st.button("Log Eval to Braintrust", type="primary"):
                try:
                    bt = BraintrustClient()
                    bt.log_eval(
                        input=bt_input,
                        output=bt_output,
                        scores=scores,
                        metadata=bt_metadata,
                    )
                    st.success("Logged to Braintrust ✅")
                except Exception as e:
                    st.error(f"Braintrust log failed: {e}")
                    st.info("Fix: ensure BraintrustClient implements log_eval(...) and initializes experiment correctly.")