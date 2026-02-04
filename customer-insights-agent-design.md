# Customer Insights Agent Design

## Overview

An aggregation agent that allows freeform questions across all people and interactions. It translates natural language queries into structured searches, applies analytical lenses, and calibrates response depth to question complexity.

---

## Search Dimensions

The agent can filter and search across:

| Dimension | Source | Search Type |
|-----------|--------|-------------|
| Person Type | `Person.type` | Enum filter (customer, investor, competitor) |
| Company Name | `Person.current_company` | Text match |
| Company Size | `Person.company_size` | Enum filter (startup, smb, enterprise) |
| Industry | `Person.industry` | Enum filter |
| Tags | `Interaction.tags` | Multi-select (pricing, product, gtm, competitors, market) |
| Person Name | `Person.name` | Text match |
| Date Range | `Interaction.date` | From/to dates |
| Takeaways | `Interaction.takeaways` | Full-text search |
| Transcript | `Interaction.transcript` | Full-text search |
| State of Play | `Person.state_of_play` | Full-text search |
| Background | `Person.background` | Full-text search |

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
**Output:** 1 line, no preamble

Examples:
- "What company does Sarah work at?" → `Acme Corp`
- "When did we last talk to John?" → `January 15, 2025`
- "How many customers have we interviewed?" → `23`

### Comparison (Brief Analysis)
**Triggers:** "How do X vs Y...", "What's the difference between...", comparison language
**Output:** Bullets or small table, 3-7 points

Examples:
- "How do SMB vs enterprise view pricing?"
- "What's different about investor vs customer concerns?"

### Analysis (Full Report)
**Triggers:** "analyze", "report", "deep dive", "map out", "do an analysis"
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

## Tools Required

### Search Functions

```python
def search_interactions(
    tags: list[Tag] = None,
    person_types: list[PersonType] = None,
    company_sizes: list[CompanySize] = None,
    industries: list[Industry] = None,
    companies: list[str] = None,
    text_query: str = None,  # full-text across transcripts + takeaways
    date_from: datetime = None,
    date_to: datetime = None,
) -> list[Interaction]

def search_persons(
    types: list[PersonType] = None,
    company_sizes: list[CompanySize] = None,
    industries: list[Industry] = None,
    companies: list[str] = None,
    text_query: str = None,  # full-text across state_of_play + background
) -> list[Person]
```

### Aggregation Functions

```python
def count_mentions(
    topic: str,
    scope: SearchScope = None,  # optional filter
) -> int

def extract_quotes(
    topic: str,
    scope: SearchScope = None,
    limit: int = 10,
) -> list[Quote]  # includes person, date, context

def get_tag_distribution(
    scope: SearchScope = None,
) -> dict[Tag, int]

def get_segment_breakdown(
    segment_by: str,  # "company_size", "industry", "person_type"
    scope: SearchScope = None,
) -> dict[str, int]
```

### Comparison Functions

```python
def compare_segments(
    segment_a: SearchScope,
    segment_b: SearchScope,
    on_topics: list[str] = None,
) -> SegmentComparison
```

---

## Conversation Context

The agent maintains context within a session for follow-up questions.

**Example flow:**
```
User: What are customers saying about pricing?
Agent: [searches #pricing tag, summarizes 12 interactions]

User: Which of those are from enterprise?
Agent: [filters previous results to company_size=enterprise]

User: Show me the strongest quotes
Agent: [extracts top quotes from filtered set]

User: How does that compare to SMB?
Agent: [runs comparison against SMB segment]
```

Context resets on new unrelated question or explicit reset.

---

## Data Model Additions

### New Enums (config.py)

```python
class CompanySize(str, Enum):
    STARTUP = "startup"       # <50 employees
    SMB = "smb"               # 50-500 employees
    ENTERPRISE = "enterprise" # 500+ employees

class Industry(str, Enum):
    FINTECH = "fintech"
    HEALTHCARE = "healthcare"
    SAAS = "saas"
    ECOMMERCE = "ecommerce"
    MANUFACTURING = "manufacturing"
    PROFESSIONAL_SERVICES = "professional_services"
    OTHER = "other"
```

### Person Model Updates

```python
@dataclass
class Person:
    name: str
    current_company: str
    type: PersonType
    company_size: CompanySize      # NEW
    industry: Industry             # NEW
    background: str = ""
    state_of_play: str = ""
    last_delta: str = ""
    interaction_ids: list[int] = field(default_factory=list)
```

### Database Schema Updates

```sql
ALTER TABLE persons ADD COLUMN company_size TEXT DEFAULT 'smb';
ALTER TABLE persons ADD COLUMN industry TEXT DEFAULT 'other';

-- Full-text search index (SQLite FTS5)
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

---

## Implementation Steps

1. **Add CompanySize and Industry enums** to `config.py`
2. **Update Person model** with new fields
3. **Migrate database schema** - add columns + FTS indexes
4. **Build search functions** - `search_interactions()`, `search_persons()`
5. **Build aggregation functions** - `count_mentions()`, `extract_quotes()`
6. **Create skill.md file** - agent instructions, tool definitions, response calibration rules
7. **Wire skill to backend** - connect tools to database functions
8. **Test with sample queries** across all response types

---

## Example Queries

| Query | Type | Persona | Format |
|-------|------|---------|--------|
| "What company does John work at?" | Lookup | - | Direct |
| "How many times was pricing discussed?" | Lookup | - | Direct |
| "What are the top pain points?" | Comparison | Product | Frequency Table |
| "How do enterprise vs SMB view integrations?" | Comparison | Product | 2x2 or Bullets |
| "What are investors worried about?" | Comparison | Market | Bullets |
| "Do an analysis on competitive threats" | Analysis | Competitive | Full Report |
| "Map the enterprise buyer journey" | Analysis | Product | Customer Journey |
| "Create an empathy map for our ideal customer" | Analysis | Product | Empathy Map |
