# VoiceOps: Self-Improving Voice Incident Agent

VoiceOps is an autonomous AI agent that monitors real-time logs, detects incidents, generates a spoken summary, and prepares to take corrective action. It demonstrates multi-agent orchestration, real-time data ingestion, voice integration, and an extensible self-improvement loop.

This project is designed for hackathon environments where autonomy, real-time integration, and production-style architecture are required.

---

## What This Project Does

VoiceOps performs the following flow:

1. Pulls real-time logs from Datadog
2. Detects potential incident patterns
3. Triages and extracts a recurring error signature
4. Generates a spoken incident summary using ElevenLabs
5. Prepares the system for future automated patch generation and verification

The architecture is modular and built to evolve into:

* Log tracing agent
* Code patch generation agent
* Local patch application
* Verification agent
* Memory and evaluation loop (self-improvement)

---

## Project Architecture Overview

VoiceOps follows a structured agent-oriented architecture:

```
Log Source (Datadog)
        ↓
Triage Agent
        ↓
Voice Summary Generator (ElevenLabs)
        ↓
Future Modules:
   - Trace Agent
   - Fix Agent
   - Verification Agent
   - Evaluation Layer
   - Memory Store
```

The system is intentionally modular to support multi-agent orchestration.

---

## Folder Structure

```
voice-ops/
│
├── app/
│   └── streamlit_app.py
│
├── src/
│   ├── config.py
│   │
│   ├── agents/
│   │   └── triage_agent.py
│   │
│   ├── core/
│   │   └── models.py
│   │
│   └── integrations/
│       ├── datadog_client.py
│       └── elevenlabs_tts.py
│
├── data/
│   └── runs/
│
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

---

## Component Explanation

### 1. `app/streamlit_app.py`

The Streamlit interface for:

* Config validation
* Real-time log trigger
* Incident visualization
* Voice playback

This is currently the demo interface.

---

### 2. `src/config.py`

Loads environment variables and API credentials safely using dotenv.

---

### 3. `src/integrations/datadog_client.py`

Handles:

* Real-time log pull via Datadog API
* Incident creation from logs
* Simulator fallback if no logs exist

---

### 4. `src/agents/triage_agent.py`

Responsible for:

* Extracting recurring error signatures
* Creating structured summaries
* Producing fingerprints for future memory learning

---

### 5. `src/integrations/elevenlabs_tts.py`

Handles:

* Text-to-speech generation
* Voice file creation
* Automatic voice selection if needed

---

## Execution Instructions

### 1. Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file:

```
DD_API_KEY=your_datadog_api_key
DD_APP_KEY=your_datadog_app_key

ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_custom_voice_id
```

Important:
On ElevenLabs free plan, you must use a voice you created in your own account. Library voices cannot be used via API.

---

### 4. Run Application

```bash
python -m streamlit run app/streamlit_app.py
```

Open the local URL displayed in terminal.

---

## Current Capabilities

* Real-time log ingestion
* Deterministic triage engine
* Structured incident model
* Voice summary generation
* Modular multi-agent foundation

---

## Upcoming Extensions

VoiceOps is built to extend into:

* Trace agent: maps logs to source files
* Fix agent: generates patch diffs
* Local patch application
* Verification agent: runs tests
* Braintrust evaluation integration
* Memory store for self-improving behavior
* Full multi-agent orchestration loop

---

## Design Philosophy

* Real-time first
* Modular agents
* Production-oriented architecture
* Demo-safe fallback modes
* Extensible evaluation layer
* Human-in-the-loop optional confirmation

---

## Why This Project Matters

Most monitoring systems alert.
VoiceOps understands.
Then it speaks.
Soon it will fix.

This bridges observability, AI reasoning, and autonomous remediation.

---
