# VoiceOps: Self-Improving Voice Incident Agent

VoiceOps is an autonomous AI agent prototype that monitors logs, triages incidents, produces a voice summary, and now logs/evaluates runs with Braintrust.

---

## What This Project Does

Current pipeline:

1. Pull logs from Datadog (or simulate logs when keys are missing)
2. Triage and extract recurring error signatures
3. Trace likely source files/lines from incident logs
4. Generate ranked fix proposals from signatures + trace candidates
5. Produce a spoken incident summary with ElevenLabs
6. Log run data + quality signals to Braintrust
7. Run deterministic evals in Braintrust (triage/trace/fix)

---

## Project Architecture

```text
Datadog (or Simulator)
  -> Triage Agent
  -> Trace Agent
  -> Fix Agent
  -> Voice Summary (ElevenLabs)
  -> Braintrust Logging + Eval
```

Future modules remain:

- Patch application workflow
- Verification agent (test gates)
- Memory/self-improvement loop

---

## Folder Structure

```text
voice-ops/
|-- app/
|   `-- streamlit_app.py
|-- src/
|   |-- config.py
|   |-- agents/
|   |   |-- triage_agent.py
|   |   |-- trace_agent.py
|   |   `-- fix_agent.py
|   |-- core/
|   |   `-- models.py
|   `-- integrations/
|       |-- datadog_client.py
|       |-- elevenlabs_tts.py
|       `-- braintrust_client.py
|-- evals/
|   |-- eval_triage_agent.py
|   |-- eval_trace_agent.py
|   `-- eval_fix_agent.py
|-- data/
|   `-- runs/
|-- .env
|-- .env.example
|-- requirements.txt
`-- README.md
```

---

## Components

### `app/streamlit_app.py`
- Streamlit UI
- Fetch -> triage -> trace -> fix -> voice pipeline trigger
- Braintrust status display and run logging

### `src/config.py`
- Loads env vars from `.env`

### `src/integrations/datadog_client.py`
- Pulls Datadog logs from API
- Falls back to simulated incident when Datadog keys are missing

### `src/agents/triage_agent.py`
- Deterministic signature extraction from log messages
- Incident summary + fingerprint enrichment

### `src/agents/trace_agent.py`
- Extracts file/line hints from logs and fingerprints
- Resolves hints against local repo Python files
- Adds ranked trace candidates to the incident

### `src/agents/fix_agent.py`
- Produces deterministic patch strategies from signature + trace context
- Adds ranked fix proposals to the incident payload

### `src/integrations/elevenlabs_tts.py`
- Text-to-speech generation
- Voice auto-selection fallback if voice ID is not set

### `src/integrations/braintrust_client.py`
- Initializes Braintrust logger
- Logs each Streamlit incident run (input/output/metadata/scores)

### `evals/eval_triage_agent.py`
- Braintrust eval suite for deterministic triage behavior

### `evals/eval_trace_agent.py`
- Braintrust eval suite for trace agent file/line mapping quality

### `evals/eval_fix_agent.py`
- Braintrust eval suite for fix strategy selection quality

---

## Setup

### 1. Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```env
DD_API_KEY=your_datadog_api_key
DD_APP_KEY=your_datadog_app_key
DD_SITE=datadoghq.com

BRAINTRUST_API_KEY=your_braintrust_api_key
BRAINTRUST_PROJECT=voiceops
# Optional self-hosted Braintrust URL
# BRAINTRUST_API_URL=https://YOUR_BRAINTRUST_HOST

ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_custom_voice_id
```

---

## Run

### App

```bash
python -m streamlit run app/streamlit_app.py
```

### Braintrust Eval

```bash
braintrust eval evals/eval_triage_agent.py
braintrust eval evals/eval_trace_agent.py
braintrust eval evals/eval_fix_agent.py
```

---

## Current Capabilities

- Real-time (or simulated) log ingestion
- Deterministic triage engine
- First-pass trace engine (file/line candidate mapping)
- First-pass fix strategy generator (ranked patch proposals)
- Structured incident model
- Voice summary generation
- Braintrust run logging in app flow
- Braintrust triage/trace/fix eval suites

---

## Pending Work

- Local patch application workflow
- Verification agent: run tests and risk gates
- Memory store for self-improving behavior
- Full multi-agent orchestration loop
