# Customer Insights Agent Design

## Overview

An aggregation agent that allows freeform questions across all people and interactions. It translates natural language queries into structured searches, applies analytical lenses, and calibrates response depth to question complexity.

---

## Skill Folder Structure

The agent is a single skill following the [Agent Skills](https://agentskills.io) open standard. Everything lives in one folder under `.claude/skills/`:

```
.claude/skills/
  customer-insights/
    SKILL.md                    # Agent instructions (entrypoint, <500 lines)
    references/
      search-dimensions.md      # What the agent can filter/search on
      output-formats.md         # Format templates (2x2, empathy map, etc.)
      enums.md                  # Valid values for tags, person types, industries
```

### Design Decisions

- **`SKILL.md`** is the required entrypoint. It contains the agent's behavioral instructions, persona lenses, and response calibration rules. Kept under 500 lines per the spec — detailed reference material lives in `references/`.
- **`references/`** holds lookup tables and format templates the agent reads on demand. These files are loaded only when the agent needs them (progressive disclosure), keeping the base context small.
- **Tools are CLI commands.** The agent invokes them via bash. No abstract Python functions — everything runs through `python main.py`.
- **Runs inline (not forked).** The agent needs conversation history for follow-up questions ("Which of those are from fintech?"), so `context: fork` is not used.

### SKILL.md Frontmatter

```yaml
---
name: customer-insights
description: >
  Answers freeform questions across all people and interactions in the Rolodex.
  Use when the user asks about customers, investors, competitors, trends, pain points,
  or wants analysis across interactions. Handles lookups, comparisons, and full reports.
allowed-tools: Bash(python main.py *) Read Grep
---
```

| Field | Value | Rationale |
|-------|-------|-----------|
| `name` | `customer-insights` | Matches directory name (required by spec) |
| `description` | (see above) | Includes keywords for auto-invocation: "customers", "investors", "pain points", "analysis", etc. |
| `allowed-tools` | `Bash(python main.py *)` `Read` `Grep` | CLI commands via bash, plus Read/Grep for transcript deep-dives |
| `disable-model-invocation` | omitted (default `false`) | Claude should auto-invoke this when the user asks analytical questions |
| `user-invocable` | omitted (default `true`) | User can also invoke directly via `/customer-insights` |
| `context` | omitted (inline) | Needs conversation history for follow-up refinements |

### Progressive Disclosure

The spec defines three loading levels. Here's how this skill maps to them:

| Level | What loads | When | Token cost |
|-------|-----------|------|------------|
| **Metadata** | `name` + `description` from frontmatter | Always (every session) | ~50 tokens |
| **Instructions** | Full `SKILL.md` body | When skill activates | <5000 tokens |
| **Resources** | `references/search-dimensions.md`, `references/output-formats.md`, `references/enums.md` | On demand during analysis | Variable |

The agent only reads `references/` files when it needs them — e.g., `output-formats.md` is loaded only for full analysis requests, not simple lookups.

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
- **Does NOT:** Search the web or speculate beyond what's in the Rolodex

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
Triggers: "analyze", "report", "deep dive", "map out", "research"

Workflow:
1. Plan 2-4 searches that cover the question from different angles
2. Run searches, collect results as JSON
3. For the strongest signals, read full transcripts via VFS for direct quotes
4. Read references/output-formats.md to select appropriate format
5. Synthesize into structured report with:
   - Key findings (ranked by frequency/strength of signal)
   - Supporting evidence (quotes attributed to specific people + dates)
   - Gaps: what the data doesn't cover, who you haven't asked about this

Examples:
- "Do an analysis on competitive landscape in payments"
- "Create a report on onboarding pain points"
- "Map out the customer journey for enterprise buyers"

## Data Coverage
Always state the evidence base: "Based on N interactions with M people..."
If fewer than 3 data points support a finding, flag it as thin evidence.
If an entire segment is missing (e.g., no healthcare customers), say so.
---

## Output Formats

Three formats. Pick the one that fits the question.

### 1. Evidence Wall

The workhorse. Most questions boil down to "what are people saying about X?" — this answers that directly. Forces the agent to go into transcripts, pull real quotes, and attribute them.

**Use for:** "What are customers saying about X?", "Show me feedback on Y", "What pain points came up?"

```
## Pricing Concerns (7 mentions across 5 people)

**"We can't justify the cost without seeing ROI in 90 days"**
— Sarah Chen (Acme Corp, Enterprise), Jan 15 2026

**"Competitors are offering bundled pricing that makes comparison impossible"**
— John Doe (Ford, Enterprise), Jan 5 2026

**"For our size, per-seat doesn't make sense"**
— Maria Lopez (TechStart, SMB), Dec 12 2025
```

### 2. Frequency Table

When you need to see patterns and prioritize — what's coming up most, what's loudest. The "People" column is critical because 14 mentions from 2 people is very different from 14 mentions across 8 people.

**Use for:** "What are the top pain points?", "Rank the most common themes", "How often did X come up?"

```
Theme                       │ People │ Mentions │ Strength
────────────────────────────┼────────┼──────────┼──────────
Slow onboarding             │  8/12  │    14    │ ████████░░
Pricing confusion           │  5/12  │     9    │ ██████░░░░
Missing integrations        │  4/12  │     7    │ █████░░░░░
Poor mobile experience      │  2/12  │     4    │ ███░░░░░░░
```

### 3. Segment Comparison

When comparing two groups — customer types, company sizes, industries, time periods. Forces a structured contrast with evidence from both sides.

**Use for:** "How do X vs Y think about Z?", "What's different between segments?", "Has sentiment changed over time?"

```
                    │ Enterprise              │ SMB
────────────────────┼─────────────────────────┼───────────────────────
Absolute cost       │ Secondary concern       │ Primary blocker
Willingness to pay  │ High if proven          │ Low, price-sensitive
Comparison behavior │ Formal RFP, 3-5 vendors │ Quick Google search
Key quote           │ "Show me the business   │ "We just need it to
                    │  case" — Sarah Chen,    │  work" — Maria Lopez,
                    │  Acme                   │  TechStart
Data coverage       │ 8 interactions          │ 4 interactions
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

The agent runs inline (not forked), so it maintains conversation context naturally within a session for follow-up questions.

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

No custom context management needed — Claude Code handles this natively.

---

## Implementation Steps

1. **Write `SKILL.md`** — frontmatter (name, description, allowed-tools) + agent instructions, persona lenses, response calibration rules. Keep under 500 lines. This is the spec the agent follows.
2. **Write `references/` files** — `search-dimensions.md`, `output-formats.md`, `enums.md` as reference material the SKILL.md points to.
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
| "Map the enterprise buyer journey" | Analysis | CLI + VFS | Search + read `references/output-formats.md` → journey map |
| "Create an empathy map for our ideal customer" | Analysis | CLI + VFS | Search + aggregate → empathy map format |
