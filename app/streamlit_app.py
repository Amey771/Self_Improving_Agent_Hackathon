from pathlib import Path

import streamlit as st

from src.agents.fix_agent import FixAgent
from src.agents.ai_fix_orchestrator import AIMultiAgentFixOrchestrator
from src.agents.remediation_agent import RemediationAgent
from src.agents.trace_agent import TraceAgent
from src.agents.triage_agent import TriageAgent
from src.config import Settings
from src.core.models import Incident
from src.integrations.braintrust_client import BraintrustClient
from src.integrations.datadog_client import DatadogClient
from src.integrations.elevenlabs_tts import ElevenLabsTTS


def inject_ui_theme():
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
            :root {
                --bg-a: #f3f7ff;
                --bg-b: #dff7f0;
                --ink: #102a43;
                --muted: #486581;
                --accent: #0f766e;
                --panel: rgba(255, 255, 255, 0.72);
            }
            html, body, [class*="css"] {
                font-family: 'IBM Plex Sans', sans-serif;
            }
            .stApp {
                background:
                    radial-gradient(900px 450px at 8% 2%, #deecff 0%, transparent 60%),
                    radial-gradient(900px 450px at 95% 0%, #d4f7ee 0%, transparent 58%),
                    linear-gradient(135deg, var(--bg-a), var(--bg-b));
            }
            .hero {
                border-radius: 18px;
                padding: 1.2rem 1.3rem;
                background: linear-gradient(130deg, rgba(15,118,110,0.92), rgba(30,64,175,0.9));
                color: white;
                box-shadow: 0 16px 40px rgba(16, 42, 67, 0.22);
                margin-bottom: 0.8rem;
            }
            .hero h2 {
                font-family: 'Space Grotesk', sans-serif;
                margin: 0;
                font-size: 1.4rem;
                letter-spacing: 0.2px;
            }
            .hero p {
                margin: 0.35rem 0 0;
                color: rgba(255,255,255,0.92);
            }
            .status-chip {
                display: inline-block;
                padding: 0.25rem 0.55rem;
                border-radius: 999px;
                font-size: 0.75rem;
                margin-right: 0.45rem;
                margin-bottom: 0.35rem;
                background: rgba(255,255,255,0.78);
                color: var(--ink);
                border: 1px solid rgba(15,118,110,0.24);
            }
            .panel-caption {
                color: var(--muted);
                font-size: 0.88rem;
                margin-bottom: 0.35rem;
            }
            .stDataFrame, .stTable {
                background: var(--panel);
                border-radius: 12px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_chip(label: str, is_enabled: bool) -> str:
    state = "ON" if is_enabled else "OFF"
    return f"<span class='status-chip'><b>{label}</b>: {state}</span>"


def build_voice_script(incident: Incident) -> str:
    signature = incident.log_fingerprints[0] if incident.log_fingerprints else "unknown signal"
    top_trace = incident.trace_candidates[0].file_path if incident.trace_candidates else "unknown location"
    top_fix = incident.fix_proposals[0].title if incident.fix_proposals else "needs manual investigation"
    return (
        "VoiceOps incident update. "
        f"{incident.summary}. "
        f"Primary signature is {signature}. "
        f"Likely source file is {top_trace}. "
        f"Suggested first fix is {top_fix}. "
        f"Current severity is {incident.severity}. "
        "Ready to proceed with patch generation if approved."
    )


def ensure_session_state():
    if "incident_data" not in st.session_state:
        st.session_state["incident_data"] = None
    if "pipeline_context" not in st.session_state:
        st.session_state["pipeline_context"] = {}
    if "voice_state" not in st.session_state:
        st.session_state["voice_state"] = {}
    if "remediation_state" not in st.session_state:
        st.session_state["remediation_state"] = None
    if "repo_validation" not in st.session_state:
        st.session_state["repo_validation"] = None
    if "ai_loop_result" not in st.session_state:
        st.session_state["ai_loop_result"] = None


def render_repo_validation(repo_validation: dict | None):
    if not repo_validation:
        return

    if repo_validation.get("ok"):
        st.success("Repository validation passed after patch application.")
    else:
        st.error("Repository validation failed. Use rollback if needed.")

    with st.expander("Validation Command Output", expanded=False):
        st.write({
            "command": repo_validation.get("command"),
            "returncode": repo_validation.get("returncode"),
            "ok": repo_validation.get("ok"),
        })
        if repo_validation.get("stdout_tail"):
            st.code(repo_validation.get("stdout_tail"), language="text")
        if repo_validation.get("stderr_tail"):
            st.code(repo_validation.get("stderr_tail"), language="text")


st.set_page_config(page_title="VoiceOps", page_icon="VO", layout="wide")
inject_ui_theme()
ensure_session_state()
braintrust = BraintrustClient()
braintrust_status = braintrust.status()

st.markdown(
    """
    <div class='hero'>
        <h2>VoiceOps Command Deck</h2>
        <p>Real-time incident triage with trace, fix planning, remediation controls, and voice briefing.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Run Controls")
    service = st.text_input("Service name", value="api")
    minutes = st.slider("Lookback window (minutes)", 1, 30, 5)

    st.divider()
    st.subheader("Voice Tuning")
    default_model = (
        Settings.ELEVENLABS_MODEL_ID
        if Settings.ELEVENLABS_MODEL_ID in ElevenLabsTTS.MODEL_OPTIONS
        else ElevenLabsTTS.MODEL_OPTIONS[0]
    )
    voice_model = st.selectbox("Model", options=ElevenLabsTTS.MODEL_OPTIONS, index=ElevenLabsTTS.MODEL_OPTIONS.index(default_model))
    stability = st.slider("Stability", 0.0, 1.0, float(Settings.ELEVENLABS_STABILITY), 0.05)
    similarity_boost = st.slider("Similarity Boost", 0.0, 1.0, float(Settings.ELEVENLABS_SIMILARITY_BOOST), 0.05)
    style = st.slider("Style", 0.0, 1.0, float(Settings.ELEVENLABS_STYLE), 0.05)
    speaker_boost = st.toggle("Speaker Boost", value=bool(Settings.ELEVENLABS_USE_SPEAKER_BOOST))
    show_raw_json = st.toggle("Show Raw Incident JSON", value=False)

    st.divider()
    st.subheader("Remediation")
    validation_command = st.text_input("Validation command", value=Settings.REMEDIATION_VALIDATION_CMD)
    ai_max_attempts = st.slider("AI max attempts", 1, 6, int(Settings.AI_MAX_FIX_ATTEMPTS))
    use_ai_loop = st.toggle("Enable AI Auto-Fix Loop", value=True)

voice_profile = {
    "model_id": voice_model,
    "stability": stability,
    "similarity_boost": similarity_boost,
    "style": style,
    "use_speaker_boost": speaker_boost,
}

st.markdown(
    status_chip("Datadog Keys", bool(Settings.DD_API_KEY and Settings.DD_APP_KEY))
    + status_chip("Braintrust", bool(braintrust_status.get("enabled")))
    + status_chip("ElevenLabs Key", bool(Settings.ELEVENLABS_API_KEY))
    + status_chip("Voice ID", bool(Settings.ELEVENLABS_VOICE_ID)),
    unsafe_allow_html=True,
)
st.caption(f"Braintrust status: {braintrust_status.get('reason')}")

metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
metric_col_1.metric("Service", service)
metric_col_2.metric("Lookback", f"{minutes} min")
metric_col_3.metric("Voice Model", voice_model)
metric_col_4.metric("Speaker Boost", "On" if speaker_boost else "Off")

run_pipeline = st.button("Run Incident Pipeline", type="primary", use_container_width=True)

if run_pipeline:
    with st.spinner("Fetching logs, triaging, tracing, and preparing fix proposals..."):
        dd = DatadogClient()
        incident = dd.fetch_incident(service, minutes)
        incident = TriageAgent().enrich_incident(incident)
        incident = TraceAgent().enrich_incident(incident)
        incident = FixAgent().enrich_incident(incident)

    st.session_state["incident_data"] = incident.model_dump()
    st.session_state["pipeline_context"] = {
        "service": service,
        "minutes": minutes,
        "source": dd.last_source,
        "voice_profile": voice_profile,
    }
    st.session_state["voice_state"] = {}
    st.session_state["remediation_state"] = None
    st.session_state["repo_validation"] = None
    st.session_state["ai_loop_result"] = None

    braintrust.log_incident_run(
        incident,
        service=service,
        minutes=minutes,
        source=dd.last_source,
        voice_generated=False,
        voice_profile=voice_profile,
    )

incident_data = st.session_state.get("incident_data")
if not incident_data:
    st.info("Run the pipeline to generate an incident, then use Remediation and Voice actions.")
    st.stop()

incident = Incident.model_validate(incident_data)
pipeline_context = st.session_state.get("pipeline_context", {})

st.success("Pipeline ready: incident + triage + trace + fix generated.")
summary_col_1, summary_col_2, summary_col_3 = st.columns(3)
summary_col_1.metric("Incident ID", incident.id)
summary_col_2.metric("Severity", incident.severity.upper())
summary_col_3.metric("Log Source", pipeline_context.get("source", "unknown"))
st.markdown(f"**Summary:** {incident.summary}")

tabs = st.tabs(["Overview", "Trace", "Fix", "Remediation", "Voice"])

with tabs[0]:
    st.markdown("<div class='panel-caption'>Incident snapshot</div>", unsafe_allow_html=True)
    if show_raw_json:
        st.json(incident.model_dump())
    else:
        st.write(
            {
                "service": incident.service,
                "severity": incident.severity,
                "summary": incident.summary,
                "fingerprints": incident.log_fingerprints,
                "sample_log_count": len(incident.sample_logs),
            }
        )

with tabs[1]:
    st.markdown("<div class='panel-caption'>Ranked trace candidates</div>", unsafe_allow_html=True)
    if incident.trace_candidates:
        st.table([candidate.model_dump() for candidate in incident.trace_candidates])
    else:
        st.info("No trace candidates found.")

with tabs[2]:
    st.markdown("<div class='panel-caption'>Ranked fix proposals</div>", unsafe_allow_html=True)
    if incident.fix_proposals:
        st.table([proposal.model_dump() for proposal in incident.fix_proposals])
    else:
        st.info("No fix proposals generated.")

with tabs[3]:
    st.markdown("<div class='panel-caption'>Patch preview, validate, apply, rollback</div>", unsafe_allow_html=True)
    remediator = RemediationAgent()

    if not incident.fix_proposals:
        st.info("No fix proposals available for remediation.")
    else:
        proposal_options = list(range(len(incident.fix_proposals)))
        selected_idx = st.selectbox(
            "Select fix proposal",
            options=proposal_options,
            format_func=lambda i: f"{i + 1}. {incident.fix_proposals[i].title} ({incident.fix_proposals[i].strategy})",
            key="remediation_selected_proposal",
        )

        current_state = st.session_state.get("remediation_state")
        can_validate = bool(current_state)
        can_apply = bool(current_state and current_state.get("validation_passed") and not current_state.get("applied"))
        can_rollback = bool(current_state and current_state.get("applied") and current_state.get("backup_path"))

        btn_col_1, btn_col_2, btn_col_3, btn_col_4, btn_col_5 = st.columns(5)
        generate_clicked = btn_col_1.button("Generate Patch Preview", use_container_width=True)
        validate_clicked = btn_col_2.button("Validate Syntax", disabled=not can_validate, use_container_width=True)
        apply_clicked = btn_col_3.button("Apply + Validate Repo", disabled=not can_apply, use_container_width=True)
        rollback_clicked = btn_col_4.button("Rollback", disabled=not can_rollback, use_container_width=True)
        run_ai_loop_clicked = btn_col_5.button("Run AI Auto-Fix", disabled=not use_ai_loop, use_container_width=True)

        if generate_clicked:
            state = remediator.generate_patch_preview(incident, selected_idx)
            st.session_state["remediation_state"] = state
            st.session_state["repo_validation"] = None
            braintrust.log_remediation_event(incident, action="generate", remediation_state=state)

        if validate_clicked:
            state = remediator.validate_patch_syntax(st.session_state["remediation_state"])
            st.session_state["remediation_state"] = state
            braintrust.log_remediation_event(incident, action="validate_syntax", remediation_state=state)

        if apply_clicked:
            state = remediator.apply_patch(st.session_state["remediation_state"])
            repo_validation = remediator.run_repo_validation(validation_command)
            st.session_state["remediation_state"] = state
            st.session_state["repo_validation"] = repo_validation
            braintrust.log_remediation_event(
                incident,
                action="apply",
                remediation_state=state,
                repo_validation=repo_validation,
            )

        if rollback_clicked:
            state = remediator.rollback_patch(st.session_state["remediation_state"])
            st.session_state["remediation_state"] = state
            st.session_state["repo_validation"] = None
            braintrust.log_remediation_event(incident, action="rollback", remediation_state=state)

        if run_ai_loop_clicked:
            orchestrator = AIMultiAgentFixOrchestrator(repo_root=".", max_attempts=ai_max_attempts)
            result = orchestrator.run(incident, validation_command=validation_command)
            st.session_state["ai_loop_result"] = result
            remediation_state = result.get("remediation_state")
            repo_validation = result.get("repo_validation")
            if remediation_state:
                st.session_state["remediation_state"] = remediation_state
            if repo_validation:
                st.session_state["repo_validation"] = repo_validation

            for attempt in result.get("history", []):
                braintrust.log_remediation_event(
                    incident,
                    action=f"ai_loop_attempt_{attempt.get('attempt')}",
                    remediation_state={
                        "status": "ai_attempt",
                        "target_file": attempt.get("selected_file"),
                        "target_line": attempt.get("selected_line"),
                        "validation_passed": bool(attempt.get("repo_validation_ok")),
                        "applied": bool(attempt.get("repo_validation_ok")),
                    },
                    repo_validation={"ok": bool(attempt.get("repo_validation_ok")), "command": "ai_loop"},
                )

            if result.get("success"):
                st.success(f"AI loop fixed issue in {result.get('attempts')} attempt(s).")
            else:
                st.warning(f"AI loop did not fully fix issue after {result.get('attempts')} attempt(s).")

        current_state = st.session_state.get("remediation_state")
        if current_state:
            display_state = {
                key: value
                for key, value in current_state.items()
                if key not in {"_original_content", "_patched_content", "diff"}
            }
            st.write(display_state)
            if current_state.get("diff"):
                st.code(current_state["diff"], language="diff")

        render_repo_validation(st.session_state.get("repo_validation"))

        ai_loop_result = st.session_state.get("ai_loop_result")
        if ai_loop_result:
            st.markdown("<div class='panel-caption'>AI Auto-Fix Loop Result</div>", unsafe_allow_html=True)
            st.write(
                {
                    "success": ai_loop_result.get("success"),
                    "attempts": ai_loop_result.get("attempts"),
                    "max_attempts": ai_loop_result.get("max_attempts"),
                    "selected_file": ai_loop_result.get("selected_file"),
                    "selected_line": ai_loop_result.get("selected_line"),
                    "llm_enabled": ai_loop_result.get("llm_enabled"),
                    "llm_provider": ai_loop_result.get("llm_provider"),
                    "llm_model": ai_loop_result.get("llm_model"),
                }
            )
            history = ai_loop_result.get("history", [])
            if history:
                st.table(history)

with tabs[4]:
    voice_text = build_voice_script(incident)
    st.markdown("<div class='panel-caption'>Narration script</div>", unsafe_allow_html=True)
    st.code(voice_text, language="text")

    generate_voice_clicked = st.button("Generate Voice Briefing", key="generate_voice_briefing")
    if generate_voice_clicked:
        voice_generated = False
        voice_error = None
        audio_path = None
        try:
            tts = ElevenLabsTTS()
            audio_path = tts.synthesize_to_file(
                voice_text,
                model_id=voice_model,
                stability=stability,
                similarity_boost=similarity_boost,
                style=style,
                use_speaker_boost=speaker_boost,
            )
            voice_generated = True
            st.success("Voice summary generated with tuned ElevenLabs settings.")
        except Exception as exc:
            voice_error = str(exc)
            st.error(f"Voice generation failed: {voice_error}")

        st.session_state["voice_state"] = {
            "generated": voice_generated,
            "audio_path": audio_path,
            "error": voice_error,
        }

        braintrust.log_incident_run(
            incident,
            service=pipeline_context.get("service", service),
            minutes=int(pipeline_context.get("minutes", minutes)),
            source=pipeline_context.get("source", "unknown"),
            voice_generated=voice_generated,
            voice_profile=pipeline_context.get("voice_profile", voice_profile),
        )

    voice_state = st.session_state.get("voice_state", {})
    audio_path = voice_state.get("audio_path")
    if audio_path and Path(audio_path).exists():
        with open(audio_path, "rb") as f:
            st.audio(f.read(), format="audio/mpeg")
    elif voice_state.get("error"):
        st.warning(voice_state.get("error"))

    st.write({"voice_profile": pipeline_context.get("voice_profile", voice_profile)})
