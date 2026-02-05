# Customer Insights Agent Design

## Overview

An aggregation agent that allows freeform questions across all people and interactions. It translates natural language queries into structured searches, applies analytical lenses, and calibrates response depth to question complexity.

---

## Skill Folder Structure

The agent is a single skill. Everything lives in one folder:

```
skills/
  customer-insights/
    skill.md                  # Agent instructions, persona lenses, response calibration
    context/
      search-dimensions.md    # What the agent can filter/search on
      output-formats.md       # Format templates (2x2, empathy map, etc.)
      enums.md                # Valid values for tags, person types, industries
```

- `skill.md` is the entrypoint. It contains the agent's behavioral instructions and declares the tools it can use.
- `context/` holds reference material the agent reads as needed. These are not prompts — they're lookup tables and format templates.
- **Tools are CLI commands.** The agent invokes them via bash. No abstract Python functions — everything runs through `python main.py`.

---

## How the Agent Accesses Data

The agent has two access paths, each suited to different query types:

### 1. VFS (Virtual Filesystem) — for direct lookups

The existing VFS maps paths to database content. The agent uses `python main.py cat` and `python main.py ls` for simple factual lookups.

```
/                                   # ls: list all people
/John_Doe/                          # ls: person directory
/John_Doe/info                      # cat: name, company, type, interaction count
/John_Doe/background                # cat: static bio
/John_Doe/state                     # cat: AI-generated state of play
/John_Doe/delta                     # cat: what changed last meeting
/John_Doe/interactions/             # ls: all interaction dates
/John_Doe/interactions/2025-01-15/  # ls: transcript, takeaways, tags
```

**When to use:** "What company does Sarah work at?", "When did we last talk to John?", "Show me John's state of play."

### 2. CLI Search Commands — for filtered queries and aggregation

New CLI commands (extending `main.py`) handle multi-dimensional search and aggregation. The agent composes these commands based on the user's question.

```bash
# Search interactions with filters
python main.py search interactions --tag pricing --type customer --text "onboarding"
python main.py search interactions --tag competitors --company "Acme" --from 2025-01-01

# Search people with filters
python main.py search people --type investor --industry fintech
python main.py search people --text "concerned about pricing"

# Aggregation
python main.py aggregate tags                          # tag distribution across all interactions
python main.py aggregate tags --type customer          # scoped to customers only
python main.py aggregate segments --by industry        # breakdown by industry
python main.py aggregate segments --by type            # breakdown by person type

# Full-text search across transcripts + takeaways
python main.py search text "switching to competitor"
```

**When to use:** "What are customers saying about pricing?", "How many times was pricing discussed?", "What are the top pain points across enterprise customers?"

---

## Search Dimensions

The agent can filter and search across:

| Dimension | Source | CLI Flag | Search Type |
|-----------|--------|----------|-------------|
| Person Type | `Person.type` | `--type` | Enum filter (customer, investor, competitor) |
| Company Name | `Person.current_company` | `--company` | Text match |
| Company Revenue | `Person.company_revenue` | `--revenue` | Text field |
| Company Headcount | `Person.company_headcount` | `--headcount` | Text field |
| Industry | `Person.company_industry` | `--industry` | Text match |
| Tags | `Interaction.tags` | `--tag` | Multi-select (pricing, product, gtm, competitors, market) |
| Person Name | `Person.name` | `--person` | Text match |
| Date Range | `Interaction.date` | `--from` / `--to` | Date range |
| Takeaways | `Interaction.takeaways` | `--text` | Full-text search |
| Transcript | `Interaction.transcript` | `--text` | Full-text search |
| State of Play | `Person.state_of_play` | `--text` (people search) | Full-text search |
| Background | `Person.background` | `--text` (people search) | Full-text search |

---

## Persona Lenses

The agent applies different analytical frames based on the question. Auto-selects or user can specify.

### Product Investigator
- **Focus:** Pain points, feature requests, workarounds, unmet needs
- **Seeks:** Friction, "I wish..." statements, hacks customers use
- **Questions:** "What are the biggest pain points?", "What features do customers want?"
- **Output style:** Problem-solution pairings, opportunity sizing, prioritized lists

### Competitive Analyst
- **Focus:** Alternatives mentioned, switching triggers, market positioning
- **Seeks:** Who else they evaluated, why they chose/left, perceived gaps
- **Questions:** "What are customers saying about competitor X?", "Why do people switch?"
- **Output style:** Threat matrix, positioning gaps, competitive quotes

### Market Strategist
- **Focus:** Industry trends, timing signals, segment patterns
- **Seeks:** Macro factors, patterns across customer types, market shifts
- **Questions:** "How do enterprise vs SMB differ?", "What trends are emerging?"
- **Output style:** Segment comparisons, trend analysis, market maps

---

## Response Calibration

The agent matches output depth to question intent. Does not over-produce.

### Lookup (Direct Answer)
**Triggers:** Simple factual questions
**Tools:** VFS (`cat`, `ls`)
**Output:** 1 line, no preamble

Examples:
- "What company does Sarah work at?" → `cat /Sarah_Chen/info` → `Acme Corp`
- "When did we last talk to John?" → `ls /John_Doe/interactions/` → `January 15, 2025`
- "How many customers have we interviewed?" → `python main.py person list --type customer` → `23`

### Comparison (Brief Analysis)
**Triggers:** "How do X vs Y...", "What's the difference between...", comparison language
**Tools:** CLI search with different filters, then synthesize
**Output:** Bullets or small table, 3-7 points

Examples:
- "How do SMB vs enterprise view pricing?" → search interactions with `--tag pricing`, split by company size
- "What's different about investor vs customer concerns?" → search both types, compare takeaways

### Analysis (Full Report)
**Triggers:** "analyze", "report", "deep dive", "map out", "do an analysis"
**Tools:** Multiple CLI searches + aggregation, reads `context/output-formats.md` for template
**Output:** Structured format with visualization, headers, comprehensive coverage

Examples:
- "Do an analysis on competitive landscape in payments"
- "Create a report on onboarding pain points"
- "Map out the customer journey for enterprise buyers"

---

## Output Formats

For full analysis requests, the agent selects the most appropriate format:

| Format | Use Case | Triggered By |
|--------|----------|--------------|
| **2x2 Matrix** | Segment comparison on two dimensions | "compare X vs Y on A and B" |
| **Empathy Map** | Deep persona understanding (Think/Feel/Do/Say) | "what does customer X experience" |
| **Customer Journey** | Process/flow pain points | "journey", "onboarding", "process" |
| **Service Blueprint** | End-to-end experience mapping | "map the experience", "touchpoints" |
| **Frequency Table** | Topic prevalence, rankings | "top N", "how often", "most common" |
| **Quote Wall** | Evidence gathering, proof points | "show me quotes", "what did they say" |
| **Trend Line** | Change over time | "over time", "trending", "changing" |
| **Five Whys** | Root cause analysis | "why do they...", "root cause" |
| **Opportunity Scorecard** | Prioritization matrix | "prioritize", "rank opportunities" |

### Format Examples

**2x2 Matrix:**
```
                    High Urgency
                         │
    Quick Wins           │         Critical
    - Feature A          │         - Feature C
    - Feature B          │         - Feature D
                         │
    ─────────────────────┼─────────────────────
                         │
    Low Priority         │         Strategic
    - Feature E          │         - Feature F
                         │
                    Low Urgency

         Low Effort ◄────┴────► High Effort
```

**Empathy Map:**
```
┌─────────────────────────────────────────────┐
│                   THINKS                     │
│  "Is this really better than what I have?"  │
│  "Will my team actually adopt this?"        │
├──────────────────────┬──────────────────────┤
│        FEELS         │        SAYS          │
│  Overwhelmed by      │  "We need better     │
│  vendor options      │  reporting"          │
│  Skeptical of ROI    │  "Price is a factor" │
├──────────────────────┴──────────────────────┤
│                    DOES                      │
│  Evaluates 3-5 vendors, asks for references │
│  Runs pilot with small team first           │
└─────────────────────────────────────────────┘
```

**Frequency Table:**
```
Pain Point                  │ Mentions │ Severity
────────────────────────────┼──────────┼──────────
Slow onboarding             │    12    │ ████████░░
Pricing confusion           │     9    │ ██████░░░░
Missing integrations        │     7    │ █████░░░░░
Poor mobile experience      │     4    │ ███░░░░░░░
```

---

## CLI Commands to Build

These extend the existing `main.py` Click CLI. The agent invokes them via bash.

### search interactions

```bash
python main.py search interactions [OPTIONS]
```

| Flag | Type | Description |
|------|------|-------------|
| `--tag` | Multi | Filter by tag (pricing, product, gtm, competitors, market) |
| `--type` | Choice | Filter by person type (customer, investor, competitor) |
| `--company` | Text | Filter by company name (substring match) |
| `--industry` | Text | Filter by company industry (substring match) |
| `--person` | Text | Filter by person name |
| `--text` | Text | Full-text search across takeaways + transcripts |
| `--from` | Date | Start date (YYYY-MM-DD) |
| `--to` | Date | End date (YYYY-MM-DD) |
| `--format` | Choice | Output as `table` (default) or `json` |

Output: For each matching interaction, prints person name, date, tags, and takeaways. With `--format json`, outputs structured JSON the agent can process further.

### search people

```bash
python main.py search people [OPTIONS]
```

| Flag | Type | Description |
|------|------|-------------|
| `--type` | Choice | Filter by person type |
| `--company` | Text | Filter by company name |
| `--industry` | Text | Filter by company industry |
| `--text` | Text | Full-text search across state_of_play + background |
| `--format` | Choice | Output as `table` (default) or `json` |

### search text

```bash
python main.py search text QUERY [OPTIONS]
```

Full-text search across all transcripts and takeaways. Returns matching excerpts with person name, date, and surrounding context.

### aggregate tags

```bash
python main.py aggregate tags [OPTIONS]
```

Shows tag frequency distribution. Accepts same filter flags as `search interactions` to scope the count.

### aggregate segments

```bash
python main.py aggregate segments --by FIELD [OPTIONS]
```

Groups people or interactions by a field (`type`, `industry`, `company`) and shows counts.

---

## Database Changes

### Full-text search indexes (SQLite FTS5)

```sql
CREATE VIRTUAL TABLE interactions_fts USING fts5(
    takeaways,
    transcript,
    content='interactions',
    content_rowid='id'
);

CREATE VIRTUAL TABLE persons_fts USING fts5(
    state_of_play,
    background,
    content='persons',
    content_rowid='rowid'
);
```

These power the `--text` flag on search commands.

---

## Conversation Context

The agent maintains context within a session for follow-up questions.

**Example flow:**
```
User: What are customers saying about pricing?
Agent: [runs: search interactions --tag pricing --type customer --format json]
Agent: [summarizes 12 interactions]

User: Which of those are from fintech?
Agent: [runs: search interactions --tag pricing --type customer --industry fintech --format json]
Agent: [filters to 4 interactions]

User: Show me the strongest quotes
Agent: [reads transcripts via VFS for those 4 people]
Agent: [extracts top quotes]

User: How does that compare to healthcare?
Agent: [runs: search interactions --tag pricing --type customer --industry healthcare --format json]
Agent: [compares the two sets]
```

Context resets on new unrelated question or explicit reset.

---

## Implementation Steps

1. **Write `skill.md`** — agent instructions, tool declarations (CLI commands + VFS), persona lenses, response calibration rules. This is the spec the agent follows.
2. **Write `context/` files** — `search-dimensions.md`, `output-formats.md`, `enums.md` as reference material the skill.md points to.
3. **Add FTS5 indexes** to database schema (`database.py` init_db migration).
4. **Build `search interactions` CLI command** — multi-filter search with `--format json` output.
5. **Build `search people` CLI command** — person search with text matching.
6. **Build `search text` CLI command** — full-text search across transcripts + takeaways.
7. **Build `aggregate` CLI commands** — tag distribution and segment breakdown.
8. **Test with sample queries** across all response types (lookup via VFS, comparison via search, analysis via search + aggregation).

---

## Example Queries

| Query | Type | Data Path | Agent Action |
|-------|------|-----------|-------------|
| "What company does John work at?" | Lookup | VFS | `cat /John_Doe/info` |
| "What's John's state of play?" | Lookup | VFS | `cat /John_Doe/state` |
| "How many customers have we talked to?" | Lookup | CLI | `person list --type customer` |
| "How many times was pricing discussed?" | Lookup | CLI | `aggregate tags` → read pricing count |
| "What are the top pain points?" | Comparison | CLI | `search interactions --tag product --format json` → frequency table |
| "How do fintech vs healthcare view pricing?" | Comparison | CLI | Two `search interactions` calls, compare |
| "What are investors worried about?" | Comparison | CLI | `search interactions --type investor --format json` → bullets |
| "Do an analysis on competitive threats" | Analysis | CLI + VFS | Multiple searches + transcript reads → full report |
| "Map the enterprise buyer journey" | Analysis | CLI + VFS | Search + read `context/output-formats.md` → journey map |
| "Create an empathy map for our ideal customer" | Analysis | CLI + VFS | Search + aggregate → empathy map format |
