"""Data models for Twitter scraper and transcriber."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


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
    
    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptionSegment":
        """Create a TranscriptionSegment from a dictionary."""
        return cls(
            start=data["start"],
            end=data["end"],
            text=data["text"],
        )


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
    
    @classmethod
    def from_dict(cls, data: dict) -> "Transcription":
        """Create a Transcription from a dictionary."""
        segments = [TranscriptionSegment.from_dict(s) for s in data.get("segments", [])]
        return cls(
            text=data["text"],
            language=data["language"],
            segments=segments,
        )


@dataclass
class Tweet:
    """Represents a single tweet."""
    
    id: str
    author: str
    text: str
    date: datetime
    url: str
    video_url: Optional[str] = None
    video_file: Optional[str] = None
    is_retweet: bool = False
    is_reply: bool = False
    reply_to_id: Optional[str] = None
    transcript: Optional[Transcription] = None
    
    def to_dict(self) -> dict:
        """Convert tweet to dictionary for JSON serialization."""
        result = {
            "id": self.id,
            "author": self.author,
            "text": self.text,
            "date": self.date.isoformat(),
            "url": self.url,
            "video_url": self.video_url,
            "video_file": self.video_file,
            "is_retweet": self.is_retweet,
            "is_reply": self.is_reply,
            "reply_to_id": self.reply_to_id,
        }
        if self.transcript is not None:
            result["transcript"] = self.transcript.to_dict()
        return result
    
    def get_filename_prefix(self) -> str:
        """Get the filename prefix based on date and ID."""
        date_str = self.date.strftime("%Y_%m_%d")
        return f"{date_str}_{self.id}"
    
    def get_video_filename(self) -> str:
        """Get the video filename."""
        return f"{self.get_filename_prefix()}_video.mp4"
    
    def get_tweet_filename(self) -> str:
        """Get the tweet JSON filename."""
        return f"{self.get_filename_prefix()}_twitt.json"
    
    def get_subtitle_filename(self) -> str:
        """Get the subtitle/transcript JSON filename."""
        return f"{self.get_filename_prefix()}_subtitle.json"
    
    def get_voice_filename(self) -> str:
        """Get the extracted audio filename."""
        return f"{self.get_filename_prefix()}_voice.wav"


@dataclass
class Thread:
    """Represents a thread of tweets from the same author."""
    
    id: str  # ID of the first/main tweet
    author: str
    date: datetime  # Date of the first tweet
    tweets: list[Tweet] = field(default_factory=list)
    video_url: Optional[str] = None
    video_file: Optional[str] = None
    transcript: Optional[Transcription] = None
    
    def to_dict(self) -> dict:
        """Convert thread to dictionary for JSON serialization."""
        result = {
            "id": self.id,
            "author": self.author,
            "date": self.date.isoformat(),
            "tweets": [t.to_dict() for t in self.tweets],
            "video_url": self.video_url,
            "video_file": self.video_file,
        }
        if self.transcript is not None:
            result["transcript"] = self.transcript.to_dict()
        return result
    
    def get_filename_prefix(self) -> str:
        """Get the filename prefix based on date and ID."""
        date_str = self.date.strftime("%Y_%m_%d")
        return f"{date_str}_{self.id}"
    
    def get_video_filename(self) -> str:
        """Get the video filename."""
        return f"{self.get_filename_prefix()}_video.mp4"
    
    def get_thread_filename(self) -> str:
        """Get the thread JSON filename."""
        return f"{self.get_filename_prefix()}_thread_twitt.json"
    
    def get_subtitle_filename(self) -> str:
        """Get the subtitle/transcript JSON filename."""
        return f"{self.get_filename_prefix()}_subtitle.json"
    
    def get_voice_filename(self) -> str:
        """Get the extracted audio filename."""
        return f"{self.get_filename_prefix()}_voice.wav"
    
    def has_video(self) -> bool:
        """Check if any tweet in the thread has a video."""
        return self.video_url is not None or any(t.video_url for t in self.tweets)
    
    def get_first_video_url(self) -> Optional[str]:
        """Get the first video URL from the thread."""
        if self.video_url:
            return self.video_url
        for tweet in self.tweets:
            if tweet.video_url:
                return tweet.video_url
        return None


@dataclass
class ScrapingResult:
    """Results from a scraping session."""
    
    profile_url: str
    start_date: datetime
    end_date: datetime
    tweets: list[Tweet] = field(default_factory=list)
    threads: list[Thread] = field(default_factory=list)
    
    def get_all_with_videos(self) -> tuple[list[Tweet], list[Thread]]:
        """Get all tweets and threads that have videos."""
        tweets_with_video = [t for t in self.tweets if t.video_url]
        threads_with_video = [t for t in self.threads if t.has_video()]
        return tweets_with_video, threads_with_video
    
    def to_dict(self) -> dict:
        """Convert results to dictionary."""
        return {
            "profile_url": self.profile_url,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "tweets": [t.to_dict() for t in self.tweets],
            "threads": [t.to_dict() for t in self.threads],
        }
