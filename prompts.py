"""LLM prompts for the Rolodex interview intelligence system."""

# Base analysis prompt - shared structure across person types
_BASE_ANALYSIS_PROMPT = """You are analyzing a transcript of a recorded conversation.

Your task is to extract key takeaways and assign relevant thematic tags.

## Available Tags
- PRICING: Pricing models, willingness to pay, cost concerns
- PRODUCT: Features, UX, functionality, bugs, requests
- GTM: Go-to-market strategy, sales, distribution, channels
- COMPETITORS: Competitive landscape, alternatives, switching
- MARKET: Industry trends, market size, timing, macro factors

## Instructions
1. Read the transcript carefully
2. Extract 3-7 key takeaways - specific, actionable insights from the conversation
3. Assign 1-3 relevant tags that best categorize the main themes discussed
4. Be specific and concrete - avoid vague generalizations

## Transcript
{transcript}

Extract the key takeaways and assign relevant tags."""

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
