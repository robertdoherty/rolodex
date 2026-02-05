"""LLM prompts for the Rolodex interview intelligence system."""

# Speaker identification prompt - identifies who each speaker is
SPEAKER_IDENTIFICATION_PROMPT = """You are analyzing a transcript to identify who each speaker is.

The transcript contains speakers labeled A, B, C, etc. Your task is to identify:
1. Which speaker is the SUBJECT being interviewed (the person we want to learn about)
2. Which speakers are the INTERVIEWERS (the people asking questions)

Look for clues like:
- Introductions ("I'm [name] from [company]")
- Who asks questions vs who answers them
- References to their role/company/background
- The subject typically shares expertise, experiences, and opinions about their work

## Subject Name (the person being interviewed)
{subject_name}

## Transcript
{transcript}

Identify which speaker letter (A, B, C, etc.) is the subject being interviewed."""

# Base analysis prompt - shared structure across person types
_BASE_ANALYSIS_PROMPT = """You are analyzing a transcript of a recorded conversation.

Your task is to extract key takeaways and assign relevant thematic tags.

IMPORTANT: The SUBJECT of this interview is {subject_name} (Speaker {subject_speaker}).
Only extract insights, opinions, and information shared BY the subject.
Ignore statements made by the interviewers - we only care about what the subject said.

## Available Tags
- PRICING: Pricing models, willingness to pay, cost concerns
- PRODUCT: Features, UX, functionality, bugs, requests
- GTM: Go-to-market strategy, sales, distribution, channels
- COMPETITORS: Competitive landscape, alternatives, switching
- MARKET: Industry trends, market size, timing, macro factors

## Instructions
1. Read the transcript carefully
2. Extract 3-7 key takeaways from what {subject_name} (Speaker {subject_speaker}) said
3. Assign 1-3 relevant tags that best categorize the main themes discussed
4. Be specific and concrete - avoid vague generalizations
5. Focus ONLY on the subject's statements, not the interviewers' questions or comments

## Transcript
{transcript}

Extract the key takeaways from {subject_name}'s statements and assign relevant tags."""

CUSTOMER_ANALYSIS_PROMPT = _BASE_ANALYSIS_PROMPT
INVESTOR_ANALYSIS_PROMPT = _BASE_ANALYSIS_PROMPT
COMPETITOR_ANALYSIS_PROMPT = _BASE_ANALYSIS_PROMPT

ROLLING_UPDATE_PROMPT = """You are updating a person's profile based on a new interaction.

## Current State of Play
{old_state}

## New Takeaways from Recent Interaction
{new_takeaways}

## Instructions
1. Analyze what has changed or been learned from this new interaction
2. Generate a "delta" - a concise summary (1-2 sentences) of what's new or changed
3. Generate an updated "state_of_play" - a comprehensive summary (~200 words) that:
   - Incorporates the new information
   - Maintains relevant context from the previous state
   - Reflects the current truth about this person/relationship
   - Is written in present tense

Be specific and actionable. Focus on insights that matter for the relationship."""

TRANSCRIPT_DIARIZATION_PROMPT = """You are analyzing a raw transcript of a conversation. \
The transcript has NO speaker labels - it is plain text with numbered lines. Your job is to:

1. DIARIZE the transcript by assigning speaker labels to line ranges. \
Label speakers as "A", "B", "C", etc.
2. IDENTIFY which speaker is the SUBJECT (the person we want to learn about, \
not the interviewer(s)).

## Subject Name
{subject_name}

## Additional Context
{context}

## Numbered Transcript
{numbered_text}

## Instructions
- Read through the entire transcript carefully
- Identify speaker changes based on conversational cues (questions vs answers, \
topic shifts, turn-taking patterns, references to roles/names)
- Assign consistent speaker letters (A, B, C, etc.) to each speaker throughout
- Return speaker turns as line ranges (start_line, end_line) that cover the \
entire transcript with no gaps and no overlaps
- Determine which speaker letter corresponds to the subject ({subject_name})
- The subject is typically the person sharing information, experiences, and opinions, \
while interviewers ask questions
- Use the additional context (if provided) to help identify speakers and roles
- Do NOT reproduce the transcript text - only return line numbers"""
