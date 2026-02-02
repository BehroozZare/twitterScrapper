"""Audio extraction and Farsi speech-to-text transcription module."""

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI


@dataclass
class TranscriptionSegment:
    """A segment of transcribed audio with timestamps."""
    
    start: float
    end: float
    text: str
    
    def to_dict(self) -> dict:
        """Convert segment to dictionary for JSON serialization."""
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }


@dataclass
class Transcription:
    """Complete transcription result."""
    
    text: str
    language: str
    segments: list[TranscriptionSegment] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert transcription to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "language": self.language,
            "segments": [s.to_dict() for s in self.segments],
        }


class AudioExtractor:
    """Extract audio from video files using FFmpeg."""
    
    def __init__(self, output_format: str = "wav", sample_rate: int = 16000):
        """
        Initialize the audio extractor.
        
        Args:
            output_format: Audio format to extract to (wav recommended for Whisper)
            sample_rate: Sample rate in Hz (16000 is optimal for Whisper)
        """
        self.output_format = output_format
        self.sample_rate = sample_rate
        self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> None:
        """Check if FFmpeg is installed and accessible."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "FFmpeg not found. Please install FFmpeg:\n"
                "  macOS: brew install ffmpeg\n"
                "  Ubuntu: sudo apt install ffmpeg\n"
                "  Windows: Download from https://ffmpeg.org/download.html"
            )
    
    def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> str:
        """
        Extract audio from a video file.
        
        Args:
            video_path: Path to the input video file
            output_path: Path for the output audio file (optional, creates temp file if not provided)
            
        Returns:
            Path to the extracted audio file
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if output_path is None:
            # Create a temporary file
            fd, output_path = tempfile.mkstemp(suffix=f".{self.output_format}")
            os.close(fd)
        
        output_path = Path(output_path)
        
        # FFmpeg command to extract audio
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vn",  # No video
            "-acodec", "pcm_s16le" if self.output_format == "wav" else "libmp3lame",
            "-ar", str(self.sample_rate),
            "-ac", "1",  # Mono audio
            "-y",  # Overwrite output file
            str(output_path),
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg failed to extract audio: {e.stderr.decode()}")
        
        return str(output_path)


class OpenAITranscriber:
    """Transcribe Farsi/Persian audio using OpenAI Whisper API."""
    
    # OpenAI Whisper API model
    MODEL = "whisper-1"
    
    # Maximum file size for OpenAI Whisper API (25MB)
    MAX_FILE_SIZE = 25 * 1024 * 1024
    
    def __init__(self, api_key: Optional[str] = None, language: str = "fa"):
        """
        Initialize the OpenAI transcriber.
        
        Args:
            api_key: OpenAI API key. If None, loads from OPENAI_API_KEY env var.
            language: Language code for transcription (default: 'fa' for Farsi)
        """
        load_dotenv()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Please set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.language = language
        self.client = OpenAI(api_key=self.api_key)
    
    def transcribe(self, audio_path: str, return_timestamps: bool = True) -> Transcription:
        """
        Transcribe an audio file using OpenAI Whisper API.
        
        Args:
            audio_path: Path to the audio file
            return_timestamps: Whether to include segment timestamps
            
        Returns:
            Transcription object with text and optional segments
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Check file size
        file_size = audio_path.stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"Audio file is too large ({file_size / 1024 / 1024:.1f}MB). "
                f"OpenAI Whisper API has a 25MB limit."
            )
        
        with open(audio_path, "rb") as audio_file:
            if return_timestamps:
                # Use verbose_json to get timestamps
                result = self.client.audio.transcriptions.create(
                    model=self.MODEL,
                    file=audio_file,
                    language=self.language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
                
                full_text = result.text.strip() if result.text else ""
                segments = []
                
                if hasattr(result, "segments") and result.segments:
                    for seg in result.segments:
                        segments.append(TranscriptionSegment(
                            start=seg.get("start", 0.0) if isinstance(seg, dict) else getattr(seg, "start", 0.0),
                            end=seg.get("end", 0.0) if isinstance(seg, dict) else getattr(seg, "end", 0.0),
                            text=(seg.get("text", "") if isinstance(seg, dict) else getattr(seg, "text", "")).strip(),
                        ))
                
                return Transcription(
                    text=full_text,
                    language=self.language,
                    segments=segments,
                )
            else:
                # Simple text response
                result = self.client.audio.transcriptions.create(
                    model=self.MODEL,
                    file=audio_file,
                    language=self.language,
                    response_format="text",
                )
                
                return Transcription(
                    text=result.strip() if isinstance(result, str) else result.text.strip(),
                    language=self.language,
                    segments=[],
                )
    
    def transcribe_video(
        self,
        video_path: str,
        audio_extractor: Optional[AudioExtractor] = None,
        return_timestamps: bool = True,
        keep_audio: bool = False,
    ) -> Transcription:
        """
        Transcribe audio from a video file.
        
        Args:
            video_path: Path to the video file
            audio_extractor: AudioExtractor instance (creates one if not provided)
            return_timestamps: Whether to include segment timestamps
            keep_audio: Whether to keep the extracted audio file
            
        Returns:
            Transcription object with text and optional segments
        """
        if audio_extractor is None:
            audio_extractor = AudioExtractor()
        
        # Extract audio to temporary file
        audio_path = audio_extractor.extract_audio(video_path)
        
        try:
            # Transcribe the audio
            result = self.transcribe(audio_path, return_timestamps=return_timestamps)
        finally:
            # Clean up temporary audio file
            if not keep_audio and os.path.exists(audio_path):
                os.remove(audio_path)
        
        return result


# Backwards compatibility alias
FarsiTranscriber = OpenAITranscriber
