"""Main pipeline orchestrator for ingesting interview recordings."""

from datetime import datetime
from pathlib import Path

from database import (
    create_interaction,
    get_person,
    update_person_state,
)
from models import Interaction
from services.analysis import (
    analyze_interaction,
    diarize_transcript,
    generate_rolling_update,
    identify_subject_speaker,
)
from services.transcription import transcribe_video


def _get_person_or_raise(person_name: str):
    """Look up a person or raise ValueError."""
    person = get_person(person_name)
    if person is None:
        raise ValueError(
            f"Person '{person_name}' not found. Create them first with the 'person create' command."
        )
    return person


def _run_shared_pipeline(
    transcript: dict,
    subject_speaker: str,
    person_name: str,
    person,
    date: datetime,
    step_offset: int = 2,
) -> Interaction:
    """Shared pipeline steps: relabel speakers, analyze, update, store."""
    total = step_offset + 4

    # Relabel speakers: subject gets person_name, others get "Interviewer N"
    interviewer_count = 0
    speaker_map = {}
    for utterance in transcript.get("utterances", []):
        letter = utterance["speaker"]
        if letter not in speaker_map:
            if letter == subject_speaker:
                speaker_map[letter] = person_name
            else:
                interviewer_count += 1
                speaker_map[letter] = f"Interviewer {interviewer_count}"
        utterance["speaker"] = speaker_map[letter]

    n = step_offset + 1
    print(f"[{n}/{total}] Analyzing interaction (focusing on {person_name}'s statements)...")
    takeaways, tags = analyze_interaction(
        transcript,
        person.type,
        subject_name=person_name,
        subject_speaker=person_name,
    )

    n += 1
    print(f"[{n}/{total}] Generating rolling update...")
    delta, updated_state = generate_rolling_update(
        person.state_of_play,
        takeaways,
    )

    n += 1
    print(f"[{n}/{total}] Storing interaction...")
    interaction = create_interaction(
        person_name=person_name,
        date=date,
        transcript=transcript,
        takeaways=takeaways,
        tags=tags,
    )

    n += 1
    print(f"[{n}/{total}] Updating person state...")
    update_person_state(
        name=person_name,
        state_of_play=updated_state,
        last_delta=delta,
    )

    print(f"Done! Created interaction #{interaction.id}")
    return interaction


def ingest_recording(
    video_path: str | Path,
    person_name: str,
    date: datetime | None = None,
) -> Interaction:
    """Ingest a video/audio recording through the full pipeline.

    Args:
        video_path: Path to the video/audio file (mp4, m4a, etc.)
        person_name: Name of the person in the recording
        date: Date of the interaction (defaults to now)

    Returns:
        The created Interaction object
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"File not found: {video_path}")

    person = _get_person_or_raise(person_name)

    if date is None:
        date = datetime.now()

    print(f"[1/6] Extracting audio and transcribing...")
    transcript = transcribe_video(video_path)

    print(f"[2/6] Identifying subject speaker...")
    subject_speaker = identify_subject_speaker(transcript, person_name)

    return _run_shared_pipeline(transcript, subject_speaker, person_name, person, date)


def ingest_transcript(
    file_path: str | Path,
    person_name: str,
    date: datetime | None = None,
    context: str = "",
) -> Interaction:
    """Ingest a plain-text transcript through the pipeline.

    Args:
        file_path: Path to the .txt or .md transcript file
        person_name: Name of the person in the transcript
        date: Date of the interaction (defaults to now)
        context: Optional context about the conversation

    Returns:
        The created Interaction object
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    person = _get_person_or_raise(person_name)

    if date is None:
        date = datetime.now()

    print(f"[1/6] Reading transcript file...")
    raw_text = file_path.read_text(encoding="utf-8")

    if not raw_text.strip():
        raise ValueError(f"Transcript file is empty: {file_path}")

    print(f"[2/6] Diarizing transcript and identifying subject speaker...")
    transcript, subject_speaker = diarize_transcript(raw_text, person_name, context)

    return _run_shared_pipeline(transcript, subject_speaker, person_name, person, date)
