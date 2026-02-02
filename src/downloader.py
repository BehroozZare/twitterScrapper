"""Video downloader using yt-dlp for Twitter videos."""

import os
import json
from pathlib import Path
from typing import Optional

import yt_dlp

from .models import Tweet, Thread


class VideoDownloader:
    """Downloads videos from Twitter using yt-dlp."""
    
    def __init__(self, output_dir: Path):
        """
        Initialize the video downloader.
        
        Args:
            output_dir: Directory to save downloaded videos
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_yt_dlp_options(self, output_path: str) -> dict:
        """Get yt-dlp options for downloading."""
        return {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
            },
        }
    
    def download_video(self, tweet_url: str, output_filename: str) -> Optional[str]:
        """
        Download a video from a tweet URL.
        
        Args:
            tweet_url: URL of the tweet containing the video
            output_filename: Filename for the downloaded video
            
        Returns:
            Path to the downloaded file or None if failed
        """
        output_path = self.output_dir / output_filename
        
        # Remove extension for yt-dlp template (it adds its own)
        output_template = str(output_path.with_suffix(''))
        
        options = self._get_yt_dlp_options(output_template + '.%(ext)s')
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                # Extract info first to check if video exists
                info = ydl.extract_info(tweet_url, download=False)
                
                if not info:
                    print(f"No video found at {tweet_url}")
                    return None
                
                # Download the video
                ydl.download([tweet_url])
                
                # Find the downloaded file (extension might vary)
                for ext in ['mp4', 'mkv', 'webm', 'mov']:
                    potential_file = output_path.with_suffix(f'.{ext}')
                    if potential_file.exists():
                        # Rename to mp4 if different
                        if ext != 'mp4':
                            final_path = output_path.with_suffix('.mp4')
                            potential_file.rename(final_path)
                            return str(final_path)
                        return str(potential_file)
                
                print(f"Downloaded file not found for {tweet_url}")
                return None
                
        except Exception as e:
            print(f"Error downloading video from {tweet_url}: {e}")
            return None
    
    def download_tweet_video(self, tweet: Tweet) -> bool:
        """
        Download video from a tweet and update the tweet object.
        
        Args:
            tweet: Tweet object with video_url
            
        Returns:
            True if download successful
        """
        if not tweet.video_url and tweet.url:
            # Use tweet URL for yt-dlp to find the video
            video_path = self.download_video(tweet.url, tweet.get_video_filename())
        else:
            video_path = self.download_video(tweet.url, tweet.get_video_filename())
        
        if video_path:
            tweet.video_file = os.path.basename(video_path)
            return True
        return False
    
    def download_thread_video(self, thread: Thread) -> bool:
        """
        Download video from a thread and update the thread object.
        
        Args:
            thread: Thread object
            
        Returns:
            True if download successful
        """
        # Find the first tweet with a video
        video_tweet = None
        for tweet in thread.tweets:
            if tweet.video_url or tweet.url:
                # Try to download from each tweet URL until success
                video_path = self.download_video(tweet.url, thread.get_video_filename())
                if video_path:
                    thread.video_file = os.path.basename(video_path)
                    return True
        
        return False
    
    def save_tweet_json(self, tweet: Tweet) -> str:
        """
        Save tweet data to JSON file.
        
        Args:
            tweet: Tweet object to save
            
        Returns:
            Path to the saved JSON file
        """
        output_path = self.output_dir / tweet.get_tweet_filename()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(tweet.to_dict(), f, indent=2, ensure_ascii=False)
        
        return str(output_path)
    
    def save_thread_json(self, thread: Thread) -> str:
        """
        Save thread data to JSON file.
        
        Args:
            thread: Thread object to save
            
        Returns:
            Path to the saved JSON file
        """
        output_path = self.output_dir / thread.get_thread_filename()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(thread.to_dict(), f, indent=2, ensure_ascii=False)
        
        return str(output_path)
    
    def process_tweet(self, tweet: Tweet) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Process a tweet: download video and save JSON.
        
        Args:
            tweet: Tweet object to process
            
        Returns:
            Tuple of (success, video_path, json_path)
        """
        video_path = None
        json_path = None
        
        # Download video
        if self.download_tweet_video(tweet):
            video_path = str(self.output_dir / tweet.video_file)
        
        # Save JSON (even if video download failed)
        json_path = self.save_tweet_json(tweet)
        
        return video_path is not None, video_path, json_path
    
    def process_thread(self, thread: Thread) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Process a thread: download video and save JSON.
        
        Args:
            thread: Thread object to process
            
        Returns:
            Tuple of (success, video_path, json_path)
        """
        video_path = None
        json_path = None
        
        # Download video
        if thread.has_video():
            if self.download_thread_video(thread):
                video_path = str(self.output_dir / thread.video_file)
        
        # Save JSON (even if video download failed)
        json_path = self.save_thread_json(thread)
        
        return video_path is not None, video_path, json_path


def create_downloader(output_dir: Path) -> VideoDownloader:
    """Create a VideoDownloader instance."""
    return VideoDownloader(output_dir)
