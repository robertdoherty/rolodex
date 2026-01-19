

# Product Design Spec: Person-Centric Interview Intelligence

## 1. System Vision

A "Stateful" AI layer that organizes information by **Individual Entities** (People) rather than **Files** (Transcripts). It tracks the "Delta" (change) in a person’s perspective across multiple interactions and aggregates these insights to identify market-wide trends.

---

## 2. Core Architecture: The "Stateful" Pipeline

### **Phase A: Ingestion**

* **Inputs:** `.mp4` file, `Name`, and `Type` (Customer/Investor/Competitor).
* **Backend:** Audio is extracted and sent to a **Diarization API** (Deepgram/AssemblyAI).
* **Output:** A JSON transcript with speaker timestamps: `Speaker_0: [00:12] Hello...`.

### **Phase B: The "Interaction" Processor**

For every new transcript, the system runs a single prompt to generate:

1. **Interaction Takeaways:** 3–5 bullet points of conversation key points. The prompt for summarization should be based on interviewee type (e.g., customer/investor/competitor)
2. **Thematic Tags:** Fixed tags (e.g., `#Pricing`, `#Strategy`) for cross-profile search. We should have a set list of ~10 to start which we can add more later on. Interactions can have multiple tags.

### **Phase C: The "Rolling" Update**

The AI takes the **New Takeaways** + the **Current `State of Play**` from the Person Object to:

1. **Identify the Delta:** What changed since the last time we spoke?
2. **Overwrite the State:** Refresh the `State of Play` with a new, unified summary.

(see below for state `State of Play` description)
---

## 3. Data Schema (The Backend Objects)

### **Object: Person**

| Field | Data Type | Description |
| --- | --- | --- |
| `name` | String | **Primary Key** for lookup. |
| `type` | Enum | Customer, Investor, or Competitor/Market. |
| `background` | Text | Static bio (e.g., "Ex-McKinsey, Founder of Motherboard"). |
| **`state_of_play`** | **Text (AI)** | **The "Current Truth."** A 200-word paragraph updated by AI. |
| **`last_delta`** | **Text (AI)** | What changed in the most recent meeting specifically. |
| `interactions` | List[IDs] | Chronological links to all transcripts. |

### **Object: Interaction**

| Field | Data Type | Description |
| --- | --- | --- |
| `date` | Timestamp | When the recording happened. |
| `transcript` | JSON | Speaker-tagged text. |
| `takeaways` | List[Str] | The "New News" extracted from this session. |
| `tags` | List[Enum] | Thematic tags for filtering. |

---

## 4. The Intelligence Prompts

### **Prompt 1: Interaction Analysis**

> **Role:** You are a Strategic Analyst.
> **Input:** [Transcript]
> **Task:** > 1. Extract 3-5 key takeaways.
> 2. Identify the top 3 themes from this list: [Pricing, Product, Competitors, Strategy].
> **Output:** JSON format.
(Have same prompt for all types (customer/investor/competitor) initially but have each be adjustable)

### **Prompt 2: The Rolling Update (The Delta)**

> **Input:** [Old State of Play] + [New Interaction Takeaways]
> **Task:** > 1. Compare these two. Identify any shifts in the person's viewpoint, tone, or priorities (**The Delta**).
> 2. Rewrite the **State of Play** to be a single, cohesive 200-word summary of where the person stands *today*.
> **Output:** `{ "delta": "...", "updated_state": "..." }`

---

## 5. Insight Engines (V1 Query Logic)

| Search Goal | Backend Logic |
| --- | --- |
| **"How has John changed?"** | Display `Person.last_delta`. |
| **"What are Investors saying?"** | Filter `Person.type == 'Investor'` → Aggregate their `state_of_play`. |
| **"Pricing Pain Points?"** | Filter `Interaction.tags` contains `#Pricing` → Aggregate their `takeaways`. |

---

## 6. Next Steps & Implementation

* **Step 1:** Build a Python script that takes your inputs and hits the Deepgram + Gemini APIs.
* **Step 2:** Store results in a local `data.json` or a simple SQLite database.
* **Step 3 (Streamlit):** Build a basic UI with a sidebar for "People" and a main window to show their "State of Play" and "Delta Timeline."

**Would you like me to write a basic Python script for Step 1 that handles the API calls and the rolling update logic?**