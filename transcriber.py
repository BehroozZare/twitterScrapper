#!/usr/bin/env python3
"""
CLI tool for extracting audio and transcribing Farsi speech from video files.

Two-phase workflow:
    Phase 1: Extract audio from videos
        python transcriber.py extract-audio data/
    
    Phase 2: Transcribe audio to subtitles
        python transcriber.py transcribe data/
"""

import argparse
import json
import sys
from pathlib import Path

from src.transcriber import AudioExtractor, OpenAITranscriber, Transcription


# =============================================================================
# Utility Functions
# =============================================================================

def get_prefix_from_filename(filename: str, suffix: str) -> str | None:
    """Extract the prefix (date_id) from a filename with given suffix."""
    if filename.endswith(suffix):
        return filename[:-len(suffix)]
    return None


def find_video_files(path: Path) -> list[Path]:
    """Find all video files in a path (file or directory)."""
    video_extensions = {".mp4", ".mkv", ".webm", ".mov", ".avi"}
    
    if path.is_file():
        if path.suffix.lower() in video_extensions:
            return [path]
        else:
            print(f"Warning: {path} is not a recognized video file")
            return []
    
    if path.is_dir():
        videos = []
        for ext in video_extensions:
            videos.extend(path.glob(f"*{ext}"))
        return sorted(videos)
    
    return []


def find_audio_files(path: Path) -> list[Path]:
    """Find all audio files in a path (file or directory)."""
    audio_extensions = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
    
    if path.is_file():
        if path.suffix.lower() in audio_extensions:
            return [path]
        else:
            print(f"Warning: {path} is not a recognized audio file")
            return []
    
    if path.is_dir():
        # Look for *_voice.wav files specifically
        voice_files = list(path.glob("*_voice.wav"))
        if voice_files:
            return sorted(voice_files)
        
        # Fall back to all audio files
        audio_files = []
        for ext in audio_extensions:
            audio_files.extend(path.glob(f"*{ext}"))
        return sorted(audio_files)
    
    return []


def find_corresponding_json(file_path: Path, file_suffix: str) -> Path | None:
    """
    Find the JSON file corresponding to a video or audio file.
    
    Naming: 2024_01_15_1234567890_video.mp4 or 2024_01_15_1234567890_voice.wav
    JSON:   2024_01_15_1234567890_twitt.json or 2024_01_15_1234567890_thread_twitt.json
    """
    filename = file_path.stem
    prefix = get_prefix_from_filename(filename, file_suffix)
    
    if prefix:
        # Try single tweet first
        json_path = file_path.parent / f"{prefix}_twitt.json"
        if json_path.exists():
            return json_path
        
        # Try thread
        thread_json_path = file_path.parent / f"{prefix}_thread_twitt.json"
        if thread_json_path.exists():
            return thread_json_path
    
    return None


def update_json_with_transcript(json_path: Path, transcription: Transcription) -> None:
    """Update a JSON file with transcription data."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    data["transcript"] = transcription.to_dict()
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =============================================================================
# Phase 1: Extract Audio
# =============================================================================

def extract_audio_from_videos(
    input_path: Path,
    output_dir: Path | None = None,
    skip_existing: bool = True,
    clean_audio: bool = False,
    trim_silence: bool = False,
) -> None:
    """
    Extract audio from video files and save as voice files.
    
    Args:
        input_path: Path to a video file or directory containing videos
        output_dir: Directory to save audio files (default: same as video)
        skip_existing: Skip videos that already have extracted audio
        clean_audio: Apply denoise + normalization filters during extraction
        trim_silence: Trim leading/trailing silence (conservative thresholds)
    """
    # Find video files
    video_files = find_video_files(input_path)
    
    if not video_files:
        print(f"No video files found in {input_path}")
        return
    
    print(f"Found {len(video_files)} video file(s)")
    
    # Initialize audio extractor
    audio_extractor = AudioExtractor()
    
    # Process each video
    successful = 0
    skipped = 0
    failed = 0
    
    for i, video_path in enumerate(video_files, 1):
        print(f"\n[{i}/{len(video_files)}] Processing: {video_path.name}")
        
        # Determine output path
        video_name = video_path.stem
        if video_name.endswith("_video"):
            prefix = video_name[:-6]  # Remove "_video" suffix
            voice_name = f"{prefix}_voice.wav"
        else:
            voice_name = f"{video_name}_voice.wav"
        
        out_dir = output_dir if output_dir else video_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        voice_path = out_dir / voice_name
        
        # Check if already extracted
        if skip_existing and voice_path.exists():
            print(f"  Skipping (voice file exists)")
            skipped += 1
            continue
        
        try:
            # Extract audio
            print(f"  Extracting audio...")
            audio_extractor.extract_audio(
                str(video_path),
                str(voice_path),
                clean_audio=clean_audio,
                trim_silence=trim_silence,
            )
            print(f"  Saved: {voice_name}")
            successful += 1
            
        except Exception as e:
            print(f"  Error: {e}")
            failed += 1
    
    # Summary
    print(f"\n{'='*50}")
    print(f"Audio extraction complete!")
    print(f"  Successful: {successful}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")


# =============================================================================
# Phase 2: Transcribe Audio
# =============================================================================

def save_subtitle(
    audio_path: Path,
    transcription: Transcription,
    output_dir: Path,
) -> Path:
    """Save transcription to a subtitle JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subtitle filename from audio filename
    # voice: 2024_01_15_1234567890_voice.wav -> subtitle: 2024_01_15_1234567890_subtitle.json
    audio_name = audio_path.stem
    if audio_name.endswith("_voice"):
        prefix = audio_name[:-6]  # Remove "_voice" suffix
        subtitle_name = f"{prefix}_subtitle.json"
    else:
        subtitle_name = f"{audio_name}_subtitle.json"
    
    output_path = output_dir / subtitle_name
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transcription.to_dict(), ensure_ascii=False, indent=2, fp=f)
    
    return output_path


def transcribe_audio_files(
    input_path: Path,
    update_json: bool = False,
    output_dir: Path | None = None,
    skip_existing: bool = True,
    model: str | None = None,
    prompt: str | None = None,
    temperature: float | None = None,
    clean_audio: bool = True,
    trim_silence: bool = True,
) -> None:
    """
    Transcribe audio files to subtitles using OpenAI Whisper API.
    
    Args:
        input_path: Path to an audio file or directory containing audio files
        update_json: Whether to update corresponding JSON files with transcripts
        output_dir: Directory to save subtitle files (default: same as audio)
        skip_existing: Skip audio files that already have subtitles
        model: OpenAI transcription model override
        prompt: Optional transcription prompt (hints)
        temperature: Optional decoding temperature
        clean_audio: Apply FFmpeg cleanup before upload (denoise + normalize)
        trim_silence: Trim leading/trailing silence before upload
    """
    # Find audio files
    audio_files = find_audio_files(input_path)
    
    if not audio_files:
        print(f"No audio files found in {input_path}")
        print("Hint: Run 'extract-audio' first to extract audio from videos")
        return
    
    print(f"Found {len(audio_files)} audio file(s)")
    
    # Initialize transcriber
    print("\nInitializing OpenAI Whisper transcriber...")
    transcriber = OpenAITranscriber(
        model=model,
        prompt=prompt,
        temperature=temperature,
        clean_audio=clean_audio,
        trim_silence=trim_silence,
    )
    
    # Process each audio file
    successful = 0
    skipped = 0
    failed = 0
    
    for i, audio_path in enumerate(audio_files, 1):
        print(f"\n[{i}/{len(audio_files)}] Processing: {audio_path.name}")
        
        # Check if already transcribed
        if skip_existing:
            if update_json:
                json_path = find_corresponding_json(audio_path, "_voice")
                if json_path:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "transcript" in data:
                        print(f"  Skipping (already transcribed)")
                        skipped += 1
                        continue
            else:
                # Check for subtitle file
                audio_name = audio_path.stem
                if audio_name.endswith("_voice"):
                    prefix = audio_name[:-6]
                    subtitle_name = f"{prefix}_subtitle.json"
                else:
                    subtitle_name = f"{audio_name}_subtitle.json"
                
                check_dir = output_dir if output_dir else audio_path.parent
                subtitle_path = check_dir / subtitle_name
                if subtitle_path.exists():
                    print(f"  Skipping (subtitle exists)")
                    skipped += 1
                    continue
        
        try:
            # Transcribe audio
            print(f"  Transcribing...")
            transcription = transcriber.transcribe(
                str(audio_path),
                return_timestamps=True,
            )
            
            # Show preview
            preview = transcription.text[:100] + "..." if len(transcription.text) > 100 else transcription.text
            print(f"  Result: {preview}")
            
            # Save results
            if update_json:
                json_path = find_corresponding_json(audio_path, "_voice")
                if json_path:
                    update_json_with_transcript(json_path, transcription)
                    print(f"  Updated: {json_path.name}")
                else:
                    print(f"  Warning: No corresponding JSON found for {audio_path.name}")
                    # Fall back to saving subtitle file
                    out_dir = output_dir if output_dir else audio_path.parent
                    save_path = save_subtitle(audio_path, transcription, out_dir)
                    print(f"  Saved subtitle: {save_path.name}")
            else:
                out_dir = output_dir if output_dir else audio_path.parent
                save_path = save_subtitle(audio_path, transcription, out_dir)
                print(f"  Saved: {save_path.name}")
            
            successful += 1
            
        except Exception as e:
            print(f"  Error: {e}")
            failed += 1
    
    # Summary
    print(f"\n{'='*50}")
    print(f"Transcription complete!")
    print(f"  Successful: {successful}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Extract audio and transcribe Farsi speech from video files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Two-phase workflow:

  Phase 1 - Extract audio from videos:
    python transcriber.py extract-audio data/
    python transcriber.py extract-audio data/2024_01_15_123_video.mp4

  Phase 2 - Transcribe audio to subtitles (using OpenAI Whisper API):
    python transcriber.py transcribe data/
    python transcriber.py transcribe data/ --update-json

Output files:
  Video:    2024_01_15_1234567890_video.mp4
  Audio:    2024_01_15_1234567890_voice.wav
  Subtitle: 2024_01_15_1234567890_subtitle.json

Required environment variable:
  OPENAI_API_KEY - Your OpenAI API key for Whisper transcription

Optional environment variables:
  OPENAI_TRANSCRIBE_MODEL - Override transcription model (default: gpt-4o-mini-transcribe; fallback to whisper-1)
  OPENAI_TRANSCRIBE_PROMPT - Optional hint/prompt for better Persian transcription
  OPENAI_TRANSCRIBE_TEMPERATURE - Optional decoding temperature (e.g. 0 or 0.2)
  TRANSCRIBE_CLEAN_AUDIO - 1/true to enable FFmpeg cleanup (default: true)
  TRANSCRIBE_TRIM_SILENCE - 1/true to trim leading/trailing silence (default: true)
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # =========================
    # extract-audio subcommand
    # =========================
    extract_parser = subparsers.add_parser(
        "extract-audio",
        help="Extract audio from video files",
        description="Extract audio from video files and save as voice files (WAV format)",
    )
    
    extract_parser.add_argument(
        "input",
        type=Path,
        help="Video file or directory containing video files",
    )
    
    extract_parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output directory for audio files (default: same as video)",
    )
    
    extract_parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Re-extract audio even if voice file exists",
    )
    
    extract_parser.add_argument(
        "--clean-audio",
        action="store_true",
        help="Apply denoise + normalization filters during extraction",
    )
    
    extract_parser.add_argument(
        "--trim-silence",
        action="store_true",
        help="Trim leading/trailing silence during extraction (conservative thresholds)",
    )
    
    # =========================
    # transcribe subcommand
    # =========================
    transcribe_parser = subparsers.add_parser(
        "transcribe",
        help="Transcribe audio files to subtitles",
        description="Transcribe Farsi audio files to subtitle JSON files",
    )
    
    transcribe_parser.add_argument(
        "input",
        type=Path,
        help="Audio file or directory containing audio files",
    )
    
    transcribe_parser.add_argument(
        "--update-json",
        action="store_true",
        help="Update corresponding tweet JSON files with transcript field",
    )
    
    transcribe_parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output directory for subtitle files (default: same as audio)",
    )
    
    transcribe_parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Re-transcribe audio even if subtitle exists",
    )
    
    transcribe_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="OpenAI transcription model override (else uses OPENAI_TRANSCRIBE_MODEL or default)",
    )
    
    transcribe_parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Optional transcription prompt/hints (else uses OPENAI_TRANSCRIBE_PROMPT)",
    )
    
    transcribe_parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Decoding temperature (else uses OPENAI_TRANSCRIBE_TEMPERATURE). Lower is more deterministic.",
    )
    
    transcribe_parser.add_argument(
        "--clean-audio",
        dest="clean_audio",
        action="store_true",
        default=True,
        help="Enable FFmpeg cleanup before upload (default: enabled)",
    )
    
    transcribe_parser.add_argument(
        "--no-clean-audio",
        dest="clean_audio",
        action="store_false",
        help="Disable FFmpeg cleanup before upload",
    )
    
    transcribe_parser.add_argument(
        "--trim-silence",
        dest="trim_silence",
        action="store_true",
        default=True,
        help="Trim leading/trailing silence before upload (default: enabled)",
    )
    
    transcribe_parser.add_argument(
        "--no-trim-silence",
        dest="trim_silence",
        action="store_false",
        help="Disable silence trimming before upload",
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    # Validate input path
    if not args.input.exists():
        print(f"Error: Input path does not exist: {args.input}")
        sys.exit(1)
    
    # Run the appropriate command
    if args.command == "extract-audio":
        extract_audio_from_videos(
            input_path=args.input,
            output_dir=args.output,
            skip_existing=not args.no_skip,
            clean_audio=args.clean_audio,
            trim_silence=args.trim_silence,
        )
    elif args.command == "transcribe":
        transcribe_audio_files(
            input_path=args.input,
            update_json=args.update_json,
            output_dir=args.output,
            skip_existing=not args.no_skip,
            model=args.model,
            prompt=args.prompt,
            temperature=args.temperature,
            clean_audio=args.clean_audio,
            trim_silence=args.trim_silence,
        )


if __name__ == "__main__":
    main()
