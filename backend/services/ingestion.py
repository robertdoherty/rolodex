"""Main pipeline orchestrator for ingesting interview recordings."""

from datetime import datetime
from pathlib import Path

from database import (
    create_interaction,
    get_person,
    update_person_background,
    update_person_state,
)
from models import Interaction
from services.analysis import analyze_interaction, generate_background, generate_rolling_update, identify_subject_speaker
from services.transcription import transcribe_video


def ingest_recording(
    video_path: str | Path,
    person_name: str,
    date: datetime | None = None,
) -> Interaction:
    """Ingest a recording through the full pipeline.

    Pipeline steps:
    1. Extract audio and transcribe with speaker diarization
    2. Identify which speaker is the subject
    3. Analyze interaction (extract takeaways + tags from subject only)
    4. Generate rolling update (delta + state_of_play)
    5. Store interaction and update person

    Args:
        video_path: Path to the video/audio file (mp4, m4a, etc.)
        person_name: Name of the person in the recording
        date: Date of the interaction (defaults to now)

    Returns:
        The created Interaction object

    Raises:
        ValueError: If person doesn't exist in database
        FileNotFoundError: If video file doesn't exist
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"File not found: {video_path}")

    person = get_person(person_name)
    if person is None:
        raise ValueError(
            f"Person '{person_name}' not found. Create them first with the 'person create' command."
        )

    if date is None:
        date = datetime.now()

    print(f"[1/6] Extracting audio and transcribing...")
    transcript = transcribe_video(video_path)

    print(f"[2/6] Identifying subject speaker...")
    subject_speaker = identify_subject_speaker(transcript, person_name)

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

    print(f"[3/6] Analyzing interaction (focusing on {person_name}'s statements)...")
    takeaways, tags = analyze_interaction(
        transcript,
        person.type,
        subject_name=person_name,
        subject_speaker=person_name,
    )

    print(f"[4/6] Generating rolling update...")
    delta, updated_state = generate_rolling_update(
        person.state_of_play,
        takeaways,
    )

    print(f"[5/6] Storing interaction...")
    interaction = create_interaction(
        person_name=person_name,
        date=date,
        transcript=transcript,
        takeaways=takeaways,
        tags=tags,
    )

    print(f"[6/6] Updating person state...")
    update_person_state(
        name=person_name,
        state_of_play=updated_state,
        last_delta=delta,
    )

    # Auto-generate background on first interaction if blank
    if not person.background.strip() and not person.interaction_ids:
        print(f"    Generating background from first interaction...")
        background = generate_background(
            person_name=person_name,
            current_company=person.current_company,
            takeaways=takeaways,
        )
        update_person_background(person_name, background)
        print(f"    Background set: {background}")

    print(f"Done! Created interaction #{interaction.id}")
    return interaction
