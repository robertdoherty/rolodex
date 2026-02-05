# The Rolodex — Frontend Design Document

## Overview

A three-panel web interface for a personal CRM that manages interview intelligence. The UI displays a navigation sidebar, a detail view, and an AI agent chat panel — following Apple-inspired design principles (clean, minimal, high usability).

---

## 1. Tech Stack

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Framework | React 19 + TypeScript | Standard ecosystem, component model fits 3-panel layout |
| Styling | Tailwind CSS v4 | Utility-first, minimal Apple aesthetic without component library bloat |
| State | Zustand | 3 pieces of shared state — no Redux overhead needed |
| Data Fetching | TanStack Query v5 | Caching, stale-while-revalidate for infrequently-changing data |
| Build | Vite 6 | Fast HMR, zero-config |
| HTTP | Native `fetch` wrapper | No dependency needed |
| Icons | Lucide React | Clean line icons, Apple-adjacent |
| Backend API | FastAPI | Wraps existing `database.py` functions with HTTP endpoints |

---

## 2. Layout

```
|  Left Sidebar  |       Middle Panel (75%)       |  Right Sidebar (25%)  |
|    ~240px       |         detail view            |     agent chat        |
```

- **Left sidebar**: Fixed initial width (~240px, wide enough for names + metadata). Min 180px, max 400px.
- **Middle panel**: 75% of remaining space. Min 400px.
- **Right sidebar**: 25% of remaining space. Min 200px, max 500px.
- **All panels resizable** via draggable dividers between them (pointer event tracking on thin handles).
- Implemented with CSS Grid: `grid-template-columns: {leftPx}px 1px 1fr 1px {rightPx}px`

---

## 3. Component Architecture

```
App
├── PanelLayout                          # CSS Grid 3-panel container
│   ├── LeftSidebar                      # Person navigation
│   │   ├── SearchBar                    # Name search input
│   │   └── PersonList                   # Filtered, alphabetical list
│   │       └── PersonListItem[]         # Name, company, type badge, interaction count
│   │
│   ├── MiddlePanel                      # State machine: empty → person → interaction
│   │   ├── EmptyState                   # "Select a person" placeholder
│   │   ├── PersonDetailView             # Person info + interaction list
│   │   │   ├── PersonHeader             # Name, company, type badge, LinkedIn link
│   │   │   ├── PersonInfoGrid           # Industry, revenue, headcount (only non-empty fields)
│   │   │   ├── StateOfPlay              # AI rolling summary card
│   │   │   ├── LastDelta                # What changed last card
│   │   │   └── InteractionList          # Date-sorted interaction cards
│   │   │       └── InteractionCard[]    # Date, tag badges, takeaway preview
│   │   │
│   │   └── InteractionDetailView        # Full interaction (replaces person view)
│   │       ├── BackButton               # "← Back to {name}" in top-left
│   │       ├── InteractionHeader        # Date + tags
│   │       ├── TakeawaysList            # Bulleted key insights
│   │       └── TranscriptView           # Speaker-tagged transcript
│   │           └── Utterance[]          # Speaker name (bold) + text
│   │
│   └── RightSidebar                     # Agent chat (placeholder)
│       └── ChatPlaceholder              # "Agent coming soon"
│
├── ResizeHandle[]                       # Draggable dividers between panels
└── (shared)
    ├── TypeBadge                        # customer (blue) | investor (green) | competitor (amber)
    └── TagBadge                         # pricing | product | gtm | competitors | market pills
```

---

## 4. Navigation State Machine

Three shared state values in Zustand:
- `selectedPersonName: string | null`
- `selectedInteractionId: number | null`
- `searchQuery: string`

Middle panel renders based on state:

```
              selectPerson(name)
   EMPTY ─────────────────────────> PERSON_DETAIL
     ↑                                 ↓ ↑
     │        clearSelection()         │ │ goBackToPerson()
     ←─────────────────────────────────┘ │
                                         │
                   selectInteraction(id) ↓ │
                                  INTERACTION_DETAIL
```

| State | selectedPersonName | selectedInteractionId | Renders |
|-------|---|---|---|
| Empty | `null` | `null` | `EmptyState` |
| Person | `"John Doe"` | `null` | `PersonDetailView` |
| Interaction | `"John Doe"` | `5` | `InteractionDetailView` |

**Key rule**: `selectPerson()` always clears `selectedInteractionId` — clicking a different person while viewing an interaction returns to that new person's detail.

---

## 5. API Layer

New file: `backend/api.py` (FastAPI server wrapping existing `database.py` functions).

### `GET /api/persons`
Sidebar list. Lightweight — no state_of_play or backgrounds.
```json
{
  "persons": [
    { "name": "John Doe", "current_company": "Ford", "type": "customer", "interaction_count": 3 }
  ]
}
```
Backend: calls `list_persons()`, maps `len(person.interaction_ids)` to count.

### `GET /api/persons/{name}`
Full person detail with interaction summaries (no transcripts).
```json
{
  "name": "John Doe",
  "current_company": "Ford",
  "type": "customer",
  "background": "VP of Fleet Operations...",
  "linkedin_url": "https://linkedin.com/in/johndoe",
  "company_industry": "Automotive",
  "company_revenue": "$150B",
  "company_headcount": "177,000",
  "state_of_play": "John is currently focused on...",
  "last_delta": "In our latest conversation...",
  "interactions": [
    { "id": 1, "date": "2026-01-05T00:00:00", "tags": ["pricing", "product"], "takeaways": ["..."] }
  ]
}
```
Backend: calls `get_person(name)` + `get_interactions(name)`. Interactions sorted by date desc. Transcript field excluded.

### `GET /api/interactions/{id}`
Full interaction with transcript. Only fetched on interaction click.
```json
{
  "id": 1,
  "person_name": "John Doe",
  "date": "2026-01-05T00:00:00",
  "tags": ["pricing", "product"],
  "takeaways": ["Ford prioritizes...", "The company faces..."],
  "transcript": {
    "text": "Full transcript...",
    "utterances": [
      { "speaker": "John Doe", "text": "We currently have...", "start": 0, "end": 15000 }
    ]
  }
}
```
Backend: calls `get_interaction(id)`.

### `GET /api/tags`
Available tags with descriptions (from `TAG_DESCRIPTIONS` in `config.py`).

### CORS
FastAPI middleware allowing `localhost:5173` (Vite dev server). In production, Vite build served statically by FastAPI.

---

## 6. Search

Client-side filtering. The person list is small (personal CRM = tens to hundreds of contacts).

1. App mounts → TanStack Query fetches all persons → cached
2. User types → Zustand `searchQuery` updates
3. `PersonList` filters cached list: `name.toLowerCase().includes(query.toLowerCase())`
4. No debounce needed (in-memory array filter is instantaneous)

---

## 7. Styling — Apple-Inspired Design Tokens

### Typography
System font stack: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif`

| Element | Size | Weight |
|---------|------|--------|
| Sidebar person name | 13px | medium (500) |
| Sidebar company | 11px | normal (400) |
| Detail header name | 24px | semibold (600) |
| Section labels | 11px uppercase | semibold (600) |
| Body text | 14px | normal (400) |
| Badge text | 11px | medium (500) |

### Colors
Neutral palette, minimal accents:
- **Surfaces**: white (#FFF), gray-50 (#F9FAFB sidebar), gray-100 (#F3F4F6 hover/inputs)
- **Text**: gray-900 (primary), gray-500 (secondary), gray-400 (muted)
- **Borders**: gray-200 (standard), gray-100 (subtle)
- **Type badges**: customer=blue, investor=green, competitor=amber (light bg + darker text)
- **Tag badges**: pricing=red-muted, product=blue-muted, gtm=green-muted, competitors=amber-muted, market=purple-muted
- **Selected sidebar item**: `bg-blue-50 text-blue-700`

### Spacing
4px grid. Sidebar padding: 12px/8px. Panel padding: 24px. Card padding: 16px. Badge padding: 8px/2px.

### Borders & Shadows
- Cards: `rounded-lg` (8px). Badges: `rounded-full`. Inputs/buttons: `rounded-md` (6px).
- Almost no shadows. 1px solid borders for panel dividers. Optional `shadow-sm` on card hover.

---

## 8. File Structure

```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── .env                                # VITE_API_URL=http://localhost:8000
└── src/
    ├── main.tsx                        # Entry point, QueryClientProvider
    ├── App.tsx                         # Renders PanelLayout
    ├── index.css                       # Tailwind directives
    ├── api/
    │   ├── client.ts                   # fetch wrapper with base URL
    │   ├── endpoints.ts                # api.getPersons(), getPerson(), getInteraction()
    │   └── queryKeys.ts               # TanStack Query key constants
    ├── store/
    │   └── appStore.ts                 # Zustand: selectedPerson, selectedInteraction, searchQuery
    ├── types/
    │   └── index.ts                    # TS interfaces mirroring API shapes
    ├── components/
    │   ├── layout/
    │   │   ├── PanelLayout.tsx
    │   │   └── ResizeHandle.tsx
    │   ├── sidebar/
    │   │   ├── LeftSidebar.tsx
    │   │   ├── SearchBar.tsx
    │   │   ├── PersonList.tsx
    │   │   └── PersonListItem.tsx
    │   ├── detail/
    │   │   ├── MiddlePanel.tsx         # State machine router
    │   │   ├── EmptyState.tsx
    │   │   ├── PersonDetailView.tsx
    │   │   ├── PersonHeader.tsx
    │   │   ├── PersonInfoGrid.tsx
    │   │   ├── StateOfPlay.tsx
    │   │   ├── LastDelta.tsx
    │   │   ├── InteractionList.tsx
    │   │   └── InteractionCard.tsx
    │   ├── interaction/
    │   │   ├── InteractionDetailView.tsx
    │   │   ├── BackButton.tsx
    │   │   ├── InteractionHeader.tsx
    │   │   ├── TakeawaysList.tsx
    │   │   ├── TranscriptView.tsx
    │   │   └── Utterance.tsx
    │   ├── chat/
    │   │   └── ChatPlaceholder.tsx
    │   └── shared/
    │       ├── TypeBadge.tsx
    │       └── TagBadge.tsx
    └── hooks/
        ├── usePersons.ts              # TanStack Query hook for person list
        ├── usePerson.ts               # TanStack Query hook for person detail
        └── useInteraction.ts          # TanStack Query hook for interaction detail
```

Backend addition (single new file, no existing code modified):
```
backend/
├── api.py                             # NEW: FastAPI server
└── (all existing files unchanged)
```
New deps in `requirements.txt`: `fastapi`, `uvicorn`

---

## 9. Implementation Sequence

| Phase | Steps | What's built |
|-------|-------|--------------|
| **1. Scaffold** | Init Vite+React+TS, install deps, configure Tailwind tokens | Empty project builds |
| **2. API Server** | Create `backend/api.py` with 4 endpoints + CORS | `uvicorn backend.api:app` serves data |
| **3. Layout** | `PanelLayout` with CSS Grid + `ResizeHandle` drag | Three resizable panels |
| **4. Sidebar** | `LeftSidebar`, `PersonList`, `PersonListItem`, `SearchBar` | Clickable person list with search |
| **5. Person Detail** | `MiddlePanel` state machine, `PersonDetailView` + all sub-components | Full person info display |
| **6. Interactions** | `InteractionList`, `InteractionCard`, click-to-select | Interaction previews in person view |
| **7. Interaction Detail** | `InteractionDetailView`, `BackButton`, `TranscriptView`, `Utterance` | Full transcript with back navigation |
| **8. Polish** | `ChatPlaceholder`, loading skeletons, error states, final styling | Complete MVP |

---

## 10. Key Files to Modify/Create

**Backend (existing, reference only — API wraps these):**
- `backend/database.py` — CRUD functions the API endpoints call
- `backend/models.py` — Person/Interaction dataclasses defining the data shape
- `backend/config.py` — PersonType, Tag enums, TAG_DESCRIPTIONS

**Backend (new):**
- `backend/api.py` — FastAPI server (new file)

**Frontend (all new):**
- Everything in `frontend/src/` as described in file structure above

---

## 11. Verification Plan

1. **API**: Start FastAPI with `uvicorn backend.api:app --reload`, hit each endpoint with curl against existing SQLite data
2. **Frontend**: `npm run dev`, verify sidebar loads persons from API, search filters correctly
3. **Navigation flow**: Click person → detail appears → click interaction → transcript appears → back button returns to person → click different person → resets correctly
4. **Resize**: Drag panel dividers, verify min/max constraints hold
5. **Empty states**: Verify empty middle panel on load, graceful handling of persons with no interactions
