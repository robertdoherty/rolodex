"""Audio transcription service with speaker diarization."""

import subprocess
import tempfile
from pathlib import Path

import assemblyai as aai

from config import AUDIO_FORMAT, AUDIO_SAMPLE_RATE
from local_secrets import ASSEMBLYAI_API_KEY


def extract_audio(video_path: str | Path) -> Path:
    """Extract audio from a video file using ffmpeg.

    Args:
        video_path: Path to the input video file (mp4, etc.)

    Returns:
        Path to the extracted audio file (wav)
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    audio_path = Path(tempfile.mktemp(suffix=f".{AUDIO_FORMAT}"))

    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(AUDIO_SAMPLE_RATE),
        "-ac", "1",
        "-y",
        str(audio_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    return audio_path


def transcribe_with_diarization(audio_path: str | Path) -> dict:
    """Transcribe audio with speaker diarization using AssemblyAI.

    Args:
        audio_path: Path to the audio file

    Returns:
        Dictionary with transcript data including speaker-tagged utterances:
        {
            "text": "Full transcript text",
            "utterances": [
                {"speaker": "A", "text": "...", "start": 0, "end": 1000},
                ...
            ]
        }
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    aai.settings.api_key = ASSEMBLYAI_API_KEY

    config = aai.TranscriptionConfig(
        speaker_labels=True,
    )

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(str(audio_path), config=config)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"Transcription failed: {transcript.error}")

    utterances = []
    if transcript.utterances:
        for utterance in transcript.utterances:
            utterances.append({
                "speaker": utterance.speaker,
                "text": utterance.text,
                "start": utterance.start,
                "end": utterance.end,
            })

    return {
        "text": transcript.text or "",
        "utterances": utterances,
    }


def transcribe_video(video_path: str | Path) -> dict:
    """Convenience function to extract audio and transcribe in one step.

    Args:
        video_path: Path to the input video file

    Returns:
        Dictionary with transcript data including speaker-tagged utterances
    """
    audio_path = extract_audio(video_path)
    try:
        return transcribe_with_diarization(audio_path)
    finally:
        audio_path.unlink(missing_ok=True)
