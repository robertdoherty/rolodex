"""Main pipeline orchestrator for ingesting interview recordings."""

from datetime import datetime
from pathlib import Path

from database import (
    create_interaction,
    get_person,
    update_person_state,
)
from models import Interaction
from services.analysis import analyze_interaction, generate_rolling_update
from services.transcription import transcribe_video


def ingest_recording(
    video_path: str | Path,
    person_name: str,
    date: datetime | None = None,
) -> Interaction:
    """Ingest a recording through the full pipeline.

    Pipeline steps:
    1. Extract audio from video
    2. Transcribe with speaker diarization
    3. Analyze interaction (extract takeaways + tags)
    4. Generate rolling update (delta + state_of_play)
    5. Store interaction and update person

    Args:
        video_path: Path to the video file (mp4, etc.)
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
        raise FileNotFoundError(f"Video file not found: {video_path}")

    person = get_person(person_name)
    if person is None:
        raise ValueError(
            f"Person '{person_name}' not found. Create them first with the 'person create' command."
        )

    if date is None:
        date = datetime.now()

    print(f"[1/5] Extracting audio and transcribing...")
    transcript = transcribe_video(video_path)

    print(f"[2/5] Analyzing interaction...")
    takeaways, tags = analyze_interaction(transcript, person.type)

    print(f"[3/5] Generating rolling update...")
    delta, updated_state = generate_rolling_update(
        person.state_of_play,
        takeaways,
    )

    print(f"[4/5] Storing interaction...")
    interaction = create_interaction(
        person_name=person_name,
        date=date,
        transcript=transcript,
        takeaways=takeaways,
        tags=tags,
    )

    print(f"[5/5] Updating person state...")
    update_person_state(
        name=person_name,
        state_of_play=updated_state,
        last_delta=delta,
    )

    print(f"Done! Created interaction #{interaction.id}")
    return interaction
