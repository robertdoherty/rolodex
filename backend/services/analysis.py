"""LLM-based transcript analysis service."""

from enum import Enum
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from config import (
    ANALYSIS_MAX_TOKENS,
    DIARIZATION_MAX_TOKENS,
    MODEL_NAME,
    MODEL_TEMPERATURE,
    ROLLING_UPDATE_MAX_TOKENS,
    SPEAKER_ID_MAX_TOKENS,
    PersonType,
    Tag,
)
from local_secrets import GEMINI_API_KEY
from prompts import (
    COMPETITOR_ANALYSIS_PROMPT,
    CUSTOMER_ANALYSIS_PROMPT,
    INVESTOR_ANALYSIS_PROMPT,
    ROLLING_UPDATE_PROMPT,
    SPEAKER_IDENTIFICATION_PROMPT,
    TRANSCRIPT_DIARIZATION_PROMPT,
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


class SpeakerIdentificationSchema(BaseModel):
    """Schema for speaker identification output."""
    subject_speaker: str = Field(
        description="The speaker letter (A, B, C, etc.) that is the subject being interviewed"
    )
    reasoning: str = Field(
        description="Brief explanation of how you identified the subject"
    )


class SpeakerSegment(BaseModel):
    """A contiguous block of lines belonging to one speaker."""
    speaker: str = Field(description="Speaker letter (A, B, C, etc.)")
    start_line: int = Field(description="First line number of this speaker's turn (1-indexed)")
    end_line: int = Field(description="Last line number of this speaker's turn (1-indexed)")


class TranscriptDiarizationSchema(BaseModel):
    """Schema for combined diarization + subject identification output."""
    segments: list[SpeakerSegment] = Field(
        description="Speaker turns as line ranges covering the entire transcript, in order"
    )
    subject_speaker: str = Field(
        description="The speaker letter (A, B, C, etc.) that is the subject"
    )
    reasoning: str = Field(
        description="Brief explanation of how speakers were identified and which is the subject"
    )


def _get_llm(max_tokens: int) -> ChatGoogleGenerativeAI:
    """Get configured LLM instance."""
    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=MODEL_TEMPERATURE,
        max_output_tokens=max_tokens,
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
        lines.append(f"{speaker}: {text}")

    return "\n".join(lines)


def _get_prompt_for_type(person_type: PersonType) -> str:
    """Get the appropriate analysis prompt for a person type."""
    prompts = {
        PersonType.CUSTOMER: CUSTOMER_ANALYSIS_PROMPT,
        PersonType.INVESTOR: INVESTOR_ANALYSIS_PROMPT,
        PersonType.COMPETITOR: COMPETITOR_ANALYSIS_PROMPT,
    }
    return prompts.get(person_type, CUSTOMER_ANALYSIS_PROMPT)


def identify_subject_speaker(
    transcript: dict,
    subject_name: str,
) -> str:
    """Identify which speaker is the subject being interviewed.

    Args:
        transcript: Dictionary with transcript data
        subject_name: Name of the person being interviewed

    Returns:
        Speaker letter (A, B, C, etc.) of the subject
    """
    llm = _get_llm(SPEAKER_ID_MAX_TOKENS)
    structured_llm = llm.with_structured_output(SpeakerIdentificationSchema)

    formatted_transcript = _format_transcript(transcript)

    prompt = ChatPromptTemplate.from_messages([
        ("human", SPEAKER_IDENTIFICATION_PROMPT),
    ])

    chain = prompt | structured_llm
    result = chain.invoke({
        "subject_name": subject_name,
        "transcript": formatted_transcript,
    })

    print(f"    Identified {subject_name} as Speaker {result.subject_speaker}")
    print(f"    Reasoning: {result.reasoning}")

    return result.subject_speaker


def diarize_transcript(
    raw_text: str,
    subject_name: str,
    context: str = "",
) -> tuple[dict, str]:
    """Diarize a raw transcript and identify the subject speaker in a single LLM call.

    Numbers the lines, asks the LLM for speaker line-ranges (compact output),
    then reconstructs full utterances from the original text.

    Args:
        raw_text: The raw transcript text (no speaker labels)
        subject_name: Name of the person being discussed/interviewed
        context: Optional context about the conversation

    Returns:
        Tuple of (transcript_dict, subject_speaker_letter)
    """
    lines = raw_text.splitlines()
    numbered_text = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))

    llm = _get_llm(DIARIZATION_MAX_TOKENS)
    structured_llm = llm.with_structured_output(TranscriptDiarizationSchema)

    prompt = ChatPromptTemplate.from_messages([
        ("human", TRANSCRIPT_DIARIZATION_PROMPT),
    ])

    chain = prompt | structured_llm
    result = chain.invoke({
        "subject_name": subject_name,
        "numbered_text": numbered_text,
        "context": context or "No additional context provided.",
    })

    print(f"    Identified {subject_name} as Speaker {result.subject_speaker}")
    print(f"    Reasoning: {result.reasoning}")
    print(f"    Diarized into {len(result.segments)} segments")

    # Reconstruct utterances from line ranges
    utterances = []
    for seg in result.segments:
        start = max(seg.start_line - 1, 0)  # convert to 0-indexed
        end = min(seg.end_line, len(lines))
        text = "\n".join(lines[start:end]).strip()
        if text:
            utterances.append({"speaker": seg.speaker, "text": text})

    transcript = {
        "text": raw_text,
        "utterances": utterances,
    }

    return transcript, result.subject_speaker


def analyze_interaction(
    transcript: dict,
    person_type: PersonType,
    subject_name: str,
    subject_speaker: str,
) -> tuple[list[str], list[Tag]]:
    """Analyze a transcript to extract takeaways and tags.

    Args:
        transcript: Dictionary with transcript data
        person_type: Type of person being interviewed
        subject_name: Name of the subject being interviewed
        subject_speaker: Speaker letter (A, B, C) of the subject

    Returns:
        Tuple of (takeaways list, tags list)
    """
    llm = _get_llm(ANALYSIS_MAX_TOKENS)
    structured_llm = llm.with_structured_output(InteractionAnalysisSchema)

    prompt_template = _get_prompt_for_type(person_type)
    formatted_transcript = _format_transcript(transcript)

    prompt = ChatPromptTemplate.from_messages([
        ("human", prompt_template),
    ])

    chain = prompt | structured_llm
    result = chain.invoke({
        "transcript": formatted_transcript,
        "subject_name": subject_name,
        "subject_speaker": subject_speaker,
    })

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
    llm = _get_llm(ROLLING_UPDATE_MAX_TOKENS)
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
