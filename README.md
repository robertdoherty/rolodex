# Rolodex

An AI-powered Interview Intelligence System that transforms raw interview recordings into actionable insights organized by individual people.

## Overview

Rolodex is a person-centric knowledge management tool for tracking how customers, investors, and competitors think over time. Instead of managing transcripts by file, it maintains rolling AI-generated summaries ("State of Play") for each person and tracks what's changed since the last interaction ("Last Delta").

**Use Case**: Business stakeholders (founders, researchers) who conduct frequent interviews and need to identify patterns, extract market intelligence, and understand evolving perspectives across multiple conversations.

## Architecture

```
rolodex/
├── main.py                 # CLI entry point (Click-based)
├── config.py               # Configuration and enums
├── models.py               # Data classes (Person, Interaction)
├── database.py             # SQLite storage layer
├── prompts.py              # LLM prompt templates
├── local_secrets.py        # API keys (gitignored)
├── services/
│   ├── ingestion.py        # Main pipeline orchestrator
│   ├── transcription.py    # Audio extraction & transcription
│   └── analysis.py         # LLM-based analysis
└── data/
    └── rolodex.db          # SQLite database
```

## Data Model

### Person
The core entity representing an individual contact:
- **name**: Primary identifier
- **current_company**: Organization affiliation
- **type**: `customer` | `investor` | `competitor`
- **background**: Context about the person
- **state_of_play**: AI-generated ~200-word rolling summary
- **last_delta**: What changed in the most recent meeting

### Interaction
A single recorded conversation:
- **person_name**: Links to Person
- **date**: When the interaction occurred
- **transcript**: Speaker-tagged utterances
- **takeaways**: 3-7 key insights extracted by LLM
- **tags**: 1-3 thematic tags (pricing, product, gtm, competitors, market)

## Pipeline Flow

The ingestion pipeline processes recordings in 5 steps:

```
Video File
    │
    ▼
┌─────────────────────────────────────┐
│ 1. Extract Audio & Transcribe       │
│    (ffmpeg + AssemblyAI diarization)│
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 2. Analyze Interaction              │
│    (LLM extracts takeaways + tags)  │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 3. Generate Rolling Update          │
│    (LLM compares old state + new)   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 4. Store Interaction                │
│    (Save to SQLite)                 │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 5. Update Person State              │
│    (state_of_play + last_delta)     │
└─────────────────────────────────────┘
```

## Installation

### Prerequisites
- Python 3.10+
- ffmpeg (for audio extraction)
- AssemblyAI API key
- Google Gemini API key

### Setup

1. Clone the repository:
```bash
git clone <repo-url>
cd rolodex
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure API keys in `local_secrets.py`:
```python
ASSEMBLYAI_API_KEY = "your-assemblyai-key"
GEMINI_API_KEY = "your-gemini-key"
```

## Usage

### Person Management

```bash
# Create a new person
python main.py person create "Jane Doe" --company "Acme Inc" --type customer --background "VP of Engineering, 10 years in SaaS"

# List all people
python main.py person list
python main.py person list --type investor

# Show person details and state
python main.py person show "Jane Doe"
```

### Recording Ingestion

```bash
# Process a recording for a person
python main.py ingest path/to/video.mp4 --person "Jane Doe" --date 2024-01-15
```

### Search & Discovery

```bash
# Find interactions by tag
python main.py search tag pricing
python main.py search tag competitors

# Show all interactions with a person
python main.py search person "Jane Doe"

# List available tags
python main.py tags
```

## Key Modules

| Module | Responsibility |
|--------|----------------|
| `main.py` | CLI interface with Click commands |
| `config.py` | Constants, enums (PersonType, Tag), API settings |
| `models.py` | Dataclass definitions (Person, Interaction) |
| `database.py` | SQLite CRUD operations |
| `prompts.py` | LLM prompt templates |
| `services/transcription.py` | Audio extraction, speaker diarization |
| `services/analysis.py` | LLM-powered analysis (Gemini) |
| `services/ingestion.py` | Pipeline orchestration |

## Configuration

Key settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `MODEL_NAME` | gemini-1.5-flash | LLM model for analysis |
| `MODEL_TEMPERATURE` | 0.3 | Low temperature for factual output |
| `MODEL_MAX_TOKENS` | 4096 | Max response length |
| `DATABASE_PATH` | data/rolodex.db | SQLite database location |
| `AUDIO_FORMAT` | wav | Extracted audio format |
| `AUDIO_SAMPLE_RATE` | 16000 | Audio sample rate |

## Tags

Interactions are automatically tagged with 1-3 of the following:

| Tag | Description |
|-----|-------------|
| `pricing` | Pricing discussions, willingness to pay |
| `product` | Feature requests, product feedback |
| `gtm` | Go-to-market, sales, distribution |
| `competitors` | Competitive landscape mentions |
| `market` | Market trends, industry dynamics |

## Dependencies

```
assemblyai>=0.23.0        # Audio transcription with speaker diarization
langchain>=0.2.0          # LLM framework
langchain-google-genai>=1.0.0  # Google Gemini integration
click>=8.1.0              # CLI framework
pydantic>=2.0.0           # Data validation
```

## Design Patterns

- **Stateful AI**: Person profiles maintain AI-generated state that evolves with each interaction
- **Structured LLM Output**: Pydantic schemas with LangChain's `with_structured_output()` for reliable JSON
- **Service Layer**: Business logic separated into services (transcription, analysis, ingestion)
- **Command Pattern**: Click groups organize CLI commands hierarchically
- **Type Safety**: Enums (PersonType, Tag) and dataclasses throughout
