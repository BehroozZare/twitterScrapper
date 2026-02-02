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
    
    @staticmethod
    def _bool_env(name: str, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "y", "on"}
    
    def _build_filter_chain(
        self,
        *,
        clean_audio: bool,
        trim_silence: bool,
    ) -> str | None:
        """
        Build a conservative FFmpeg audio filter chain.
        
        Notes:
        - `silenceremove` is useful but can cut quiet speech if thresholds are too high.
        - Filters are intentionally conservative; tune via code/env if needed.
        """
        filters: list[str] = []
        
        if trim_silence:
            # Conservative thresholds to reduce risk of clipping quiet speech.
            filters.append(
                "silenceremove="
                "start_periods=1:start_duration=0.5:start_threshold=-50dB:"
                "stop_periods=1:stop_duration=0.5:stop_threshold=-50dB"
            )
        
        if clean_audio:
            # Mild denoise + standard loudness normalization (one-pass).
            filters.append("afftdn=nf=-25")
            filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")
        
        return ",".join(filters) if filters else None
    
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
    
    def extract_audio(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        *,
        clean_audio: bool = False,
        trim_silence: bool = False,
    ) -> str:
        """
        Extract audio from a video file.
        
        Args:
            video_path: Path to the input video file
            output_path: Path for the output audio file (optional, creates temp file if not provided)
            clean_audio: Apply denoise + loudness normalization filters
            trim_silence: Trim leading/trailing silence (conservative thresholds)
            
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
        
        filter_chain = self._build_filter_chain(
            clean_audio=clean_audio,
            trim_silence=trim_silence,
        )
        
        # FFmpeg command to extract audio
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(video_path),
            "-vn",  # No video
            "-acodec", "pcm_s16le" if self.output_format == "wav" else "libmp3lame",
            "-ar", str(self.sample_rate),
            "-ac", "1",  # Mono audio
        ]
        if filter_chain:
            cmd += ["-af", filter_chain]
        
        cmd += [
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
    
    def clean_audio_file(
        self,
        audio_path: str,
        output_path: Optional[str] = None,
        *,
        clean_audio: bool = True,
        trim_silence: bool = True,
    ) -> str:
        """
        Clean an existing audio file (denoise/normalize/trim) using FFmpeg.
        
        Returns:
            Path to cleaned WAV audio file.
        """
        audio_path_p = Path(audio_path)
        if not audio_path_p.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path_p}")
        
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
        
        output_path_p = Path(output_path)
        
        filter_chain = self._build_filter_chain(
            clean_audio=clean_audio,
            trim_silence=trim_silence,
        )
        
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(audio_path_p),
            "-acodec", "pcm_s16le",
            "-ar", str(self.sample_rate),
            "-ac", "1",
        ]
        if filter_chain:
            cmd += ["-af", filter_chain]
        cmd += ["-y", str(output_path_p)]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg failed to clean audio: {e.stderr.decode()}")
        
        return str(output_path_p)


class OpenAITranscriber:
    """Transcribe Farsi/Persian audio using OpenAI Whisper API."""
    
    # OpenAI Whisper API model
    FALLBACK_MODEL = "whisper-1"
    DEFAULT_BETTER_MODEL = "gpt-4o-mini-transcribe"
    
    # Maximum file size for OpenAI Whisper API (25MB)
    MAX_FILE_SIZE = 25 * 1024 * 1024
    
    @staticmethod
    def _bool_env(name: str, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "y", "on"}
    
    @staticmethod
    def _float_env(name: str, default: float | None = None) -> float | None:
        raw = os.getenv(name)
        if raw is None or raw.strip() == "":
            return default
        try:
            return float(raw)
        except ValueError:
            return default
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        language: str = "fa",
        *,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        clean_audio: Optional[bool] = None,
        trim_silence: Optional[bool] = None,
        audio_extractor: Optional[AudioExtractor] = None,
    ):
        """
        Initialize the OpenAI transcriber.
        
        Args:
            api_key: OpenAI API key. If None, loads from OPENAI_API_KEY env var.
            language: Language code for transcription (default: 'fa' for Farsi)
            model: Transcription model override (else env OPENAI_TRANSCRIBE_MODEL, else default)
            prompt: Optional prompt/hints for transcription (else env OPENAI_TRANSCRIBE_PROMPT)
            temperature: Optional decoding temperature (else env OPENAI_TRANSCRIBE_TEMPERATURE)
            clean_audio: Whether to run FFmpeg cleanup before upload (else env TRANSCRIBE_CLEAN_AUDIO)
            trim_silence: Whether to trim leading/trailing silence (else env TRANSCRIBE_TRIM_SILENCE)
            audio_extractor: Optional AudioExtractor instance for cleanup
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
        
        # Configurable transcription controls (args > env > defaults)
        self.model = (
            model
            or os.getenv("OPENAI_TRANSCRIBE_MODEL")
            or self.DEFAULT_BETTER_MODEL
        )
        
        self.prompt = prompt if prompt is not None else os.getenv("OPENAI_TRANSCRIBE_PROMPT")
        if self.prompt is not None and self.prompt.strip() == "":
            self.prompt = None
        
        self.temperature = temperature if temperature is not None else self._float_env("OPENAI_TRANSCRIBE_TEMPERATURE", default=None)
        
        # Default on (per plan); allow env/args to disable.
        self.clean_audio = clean_audio if clean_audio is not None else self._bool_env("TRANSCRIBE_CLEAN_AUDIO", default=True)
        self.trim_silence = trim_silence if trim_silence is not None else self._bool_env("TRANSCRIBE_TRIM_SILENCE", default=True)
        
        self.audio_extractor = audio_extractor
    
    def transcribe(
        self,
        audio_path: str,
        return_timestamps: bool = True,
        *,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        clean_audio: Optional[bool] = None,
        trim_silence: Optional[bool] = None,
    ) -> Transcription:
        """
        Transcribe an audio file using OpenAI Whisper API.
        
        Args:
            audio_path: Path to the audio file
            return_timestamps: Whether to include segment timestamps
            model: Optional override model for this call
            prompt: Optional override prompt for this call
            temperature: Optional override temperature for this call
            clean_audio: Optional override cleanup (FFmpeg) for this call
            trim_silence: Optional override trimming for this call
            
        Returns:
            Transcription object with text and optional segments
        """
        audio_path_p = Path(audio_path)
        if not audio_path_p.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path_p}")
        
        selected_model = model or self.model
        selected_prompt = prompt if prompt is not None else self.prompt
        selected_temperature = temperature if temperature is not None else self.temperature
        do_clean = clean_audio if clean_audio is not None else self.clean_audio
        do_trim = trim_silence if trim_silence is not None else self.trim_silence
        
        upload_path = audio_path_p
        temp_clean_path: str | None = None
        try:
            if do_clean or do_trim:
                extractor = self.audio_extractor or AudioExtractor(sample_rate=16000)
                temp_clean_path = extractor.clean_audio_file(
                    str(audio_path_p),
                    clean_audio=do_clean,
                    trim_silence=do_trim,
                )
                upload_path = Path(temp_clean_path)
        
            # Check file size (after optional cleanup)
            file_size = upload_path.stat().st_size
            if file_size > self.MAX_FILE_SIZE:
                raise ValueError(
                    f"Audio file is too large ({file_size / 1024 / 1024:.1f}MB). "
                    f"OpenAI Whisper API has a 25MB limit."
                )
        
            def _create_transcription(*, model_name: str):
                with open(upload_path, "rb") as audio_file:
                    base_kwargs: dict = {
                        "model": model_name,
                        "file": audio_file,
                        "language": self.language,
                    }
                    if selected_prompt:
                        base_kwargs["prompt"] = selected_prompt
                    if selected_temperature is not None:
                        base_kwargs["temperature"] = selected_temperature
                    
                    if return_timestamps:
                        base_kwargs["response_format"] = "verbose_json"
                        base_kwargs["timestamp_granularities"] = ["segment"]
                    else:
                        base_kwargs["response_format"] = "text"
                    
                    return self.client.audio.transcriptions.create(**base_kwargs)
            
            try:
                result = _create_transcription(model_name=selected_model)
            except Exception as e:
                # Safe fallback if the "better" model isn't available on the account/project.
                # We retry once with whisper-1 to avoid breaking existing workflows.
                msg = str(e).lower()
                if selected_model != self.FALLBACK_MODEL and (
                    "model" in msg and ("not found" in msg or "does not exist" in msg or "invalid" in msg)
                ):
                    print(f"Warning: model '{selected_model}' unavailable; retrying with '{self.FALLBACK_MODEL}'.")
                    result = _create_transcription(model_name=self.FALLBACK_MODEL)
                else:
                    raise
                
            if return_timestamps:
                full_text = result.text.strip() if getattr(result, "text", None) else ""
                segments: list[TranscriptionSegment] = []
                
                if hasattr(result, "segments") and result.segments:
                    for seg in result.segments:
                        segments.append(
                            TranscriptionSegment(
                                start=seg.get("start", 0.0) if isinstance(seg, dict) else getattr(seg, "start", 0.0),
                                end=seg.get("end", 0.0) if isinstance(seg, dict) else getattr(seg, "end", 0.0),
                                text=(seg.get("text", "") if isinstance(seg, dict) else getattr(seg, "text", "")).strip(),
                            )
                        )
                
                return Transcription(text=full_text, language=self.language, segments=segments)
            
            # Simple text response
            if isinstance(result, str):
                text_out = result.strip()
            else:
                text_out = (getattr(result, "text", "") or "").strip()
            
            return Transcription(text=text_out, language=self.language, segments=[])
        finally:
            if temp_clean_path and os.path.exists(temp_clean_path):
                try:
                    os.remove(temp_clean_path)
                except OSError:
                    pass
    
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
