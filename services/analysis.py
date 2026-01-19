"""LLM-based transcript analysis service."""

from enum import Enum
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from config import (
    MODEL_MAX_TOKENS,
    MODEL_NAME,
    MODEL_TEMPERATURE,
    PersonType,
    Tag,
)
from local_secrets import GEMINI_API_KEY
from prompts import (
    COMPETITOR_ANALYSIS_PROMPT,
    CUSTOMER_ANALYSIS_PROMPT,
    INVESTOR_ANALYSIS_PROMPT,
    ROLLING_UPDATE_PROMPT,
)


class TagEnum(str, Enum):
    """Tag enum for structured output."""
    PRICING = "pricing"
    PRODUCT = "product"
    GTM = "gtm"
    COMPETITORS = "competitors"
    MARKET = "market"


class InteractionAnalysisSchema(BaseModel):
    """Schema for interaction analysis output."""
    takeaways: list[str] = Field(
        description="3-7 key takeaways from the conversation - specific, actionable insights"
    )
    tags: list[Literal["pricing", "product", "gtm", "competitors", "market"]] = Field(
        description="1-3 relevant thematic tags"
    )


class RollingUpdateSchema(BaseModel):
    """Schema for rolling update output."""
    delta: str = Field(
        description="1-2 sentence summary of what's new or changed"
    )
    updated_state: str = Field(
        description="Comprehensive ~200 word summary of current truth about this person"
    )


def _get_llm() -> ChatGoogleGenerativeAI:
    """Get configured LLM instance."""
    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=MODEL_TEMPERATURE,
        max_output_tokens=MODEL_MAX_TOKENS,
        google_api_key=GEMINI_API_KEY,
    )


def _format_transcript(transcript: dict) -> str:
    """Format transcript dict into readable text."""
    if not transcript.get("utterances"):
        return transcript.get("text", "")

    lines = []
    for utterance in transcript["utterances"]:
        speaker = utterance.get("speaker", "Unknown")
        text = utterance.get("text", "")
        lines.append(f"Speaker {speaker}: {text}")

    return "\n".join(lines)


def _get_prompt_for_type(person_type: PersonType) -> str:
    """Get the appropriate analysis prompt for a person type."""
    prompts = {
        PersonType.CUSTOMER: CUSTOMER_ANALYSIS_PROMPT,
        PersonType.INVESTOR: INVESTOR_ANALYSIS_PROMPT,
        PersonType.COMPETITOR: COMPETITOR_ANALYSIS_PROMPT,
    }
    return prompts.get(person_type, CUSTOMER_ANALYSIS_PROMPT)


def analyze_interaction(
    transcript: dict,
    person_type: PersonType,
) -> tuple[list[str], list[Tag]]:
    """Analyze a transcript to extract takeaways and tags.

    Args:
        transcript: Dictionary with transcript data
        person_type: Type of person being interviewed

    Returns:
        Tuple of (takeaways list, tags list)
    """
    llm = _get_llm()
    structured_llm = llm.with_structured_output(InteractionAnalysisSchema)

    prompt_template = _get_prompt_for_type(person_type)
    formatted_transcript = _format_transcript(transcript)

    prompt = ChatPromptTemplate.from_messages([
        ("human", prompt_template),
    ])

    chain = prompt | structured_llm
    result = chain.invoke({"transcript": formatted_transcript})

    tags = [Tag(t) for t in result.tags]

    return result.takeaways, tags


def generate_rolling_update(
    old_state: str,
    new_takeaways: list[str],
) -> tuple[str, str]:
    """Generate a rolling update based on new interaction.

    Args:
        old_state: Previous state_of_play text
        new_takeaways: List of takeaways from the new interaction

    Returns:
        Tuple of (delta, updated_state)
    """
    llm = _get_llm()
    structured_llm = llm.with_structured_output(RollingUpdateSchema)

    prompt = ChatPromptTemplate.from_messages([
        ("human", ROLLING_UPDATE_PROMPT),
    ])

    takeaways_text = "\n".join(f"- {t}" for t in new_takeaways)

    chain = prompt | structured_llm
    result = chain.invoke({
        "old_state": old_state or "No previous state - this is the first interaction.",
        "new_takeaways": takeaways_text,
    })

    return result.delta, result.updated_state
