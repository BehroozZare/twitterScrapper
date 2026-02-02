#!/usr/bin/env python3
"""
Twitter/X Video Scraper

Scrapes tweets and downloads videos from a Twitter profile within a date range
using the Twitter API v2.

Usage:
    python scraper.py --url https://x.com/username --start-date 2024-01-01 --end-date 2024-12-31
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from dateutil import parser as date_parser
from dotenv import load_dotenv

from src.twitter_api import TwitterAPI, TwitterAPIError, extract_username_from_url
from src.extractor import (
    parse_api_tweet,
    filter_tweets_by_date,
    group_tweets_into_threads,
    get_tweets_needing_video_download,
)
from src.downloader import VideoDownloader


# Default output directory
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "data"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape tweets and download videos from Twitter/X profiles using the API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Scrape videos from a profile
    python scraper.py --url https://x.com/username --start-date 2024-01-01 --end-date 2024-12-31
    
    # Scrape with custom output directory
    python scraper.py --url https://x.com/username --start-date 2024-01-01 --end-date 2024-12-31 --output ./my_videos
    
    # Limit number of tweets to fetch
    python scraper.py --url https://x.com/username --start-date 2024-01-01 --end-date 2024-12-31 --limit 50

Setup:
    1. Copy .env.example to .env
    2. Add your Twitter API credentials to .env
    3. Run the scraper
        """,
    )
    
    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="Twitter/X profile URL (e.g., https://x.com/username)",
    )
    
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Start date for scraping (YYYY-MM-DD format)",
    )
    
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="End date for scraping (YYYY-MM-DD format)",
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for videos and JSON files (default: {DEFAULT_OUTPUT_DIR})",
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of tweets to fetch (default: no limit)",
    )
    
    parser.add_argument(
        "--videos-only",
        action="store_true",
        help="Only save tweets that have videos",
    )
    
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> bool:
    """Validate command line arguments."""
    # Validate URL format
    if not ("x.com/" in args.url or "twitter.com/" in args.url):
        print("Error: URL must be a Twitter/X profile URL (e.g., https://x.com/username)")
        return False
    
    return True


def parse_date(date_str: str) -> datetime:
    """Parse a date string into a datetime object."""
    return date_parser.parse(date_str).replace(hour=0, minute=0, second=0, microsecond=0)


def run_scraper(
    url: str,
    start_date: datetime,
    end_date: datetime,
    output_dir: Path,
    limit: int | None = None,
    videos_only: bool = False,
) -> None:
    """Run the main scraping process."""
    # Extract username from URL
    try:
        username = extract_username_from_url(url)
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    print(f"\nScraping profile: @{username}")
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print(f"Output directory: {output_dir}")
    if limit:
        print(f"Tweet limit: {limit}")
    print("-" * 50)
    
    # Initialize API client
    print("\nConnecting to Twitter API...")
    try:
        api = TwitterAPI()
    except TwitterAPIError as e:
        print(f"\nError: {e}")
        print("\nMake sure you have created a .env file with your Twitter API credentials.")
        print("See .env.example for the required format.")
        return
    
    print("Connected successfully!")
    
    # Initialize downloader
    downloader = VideoDownloader(output_dir)
    
    # Fetch tweets
    print(f"\nFetching tweets from @{username}...")
    
    # Add timezone info to dates for API
    start_date_tz = start_date.replace(tzinfo=timezone.utc)
    end_date_tz = end_date.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    
    raw_tweets = []
    try:
        for tweet_data in api.get_user_tweets(
            username=username,
            start_date=start_date_tz,
            end_date=end_date_tz,
            limit=limit,
        ):
            raw_tweets.append(tweet_data)
            
            # Progress indicator
            if len(raw_tweets) % 10 == 0:
                print(f"  Fetched {len(raw_tweets)} tweets...")
    
    except TwitterAPIError as e:
        print(f"\nError fetching tweets: {e}")
        return
    
    print(f"\nFetched {len(raw_tweets)} tweets from API")
    
    if not raw_tweets:
        print("No tweets found in the specified date range.")
        return
    
    # Parse tweet data
    tweets = []
    for data in raw_tweets:
        tweet = parse_api_tweet(data)
        if tweet:
            # Skip retweets
            if not tweet.is_retweet:
                tweets.append(tweet)
    
    print(f"Parsed {len(tweets)} original tweets (excluding retweets)")
    
    # Filter by date range (API should already do this, but double-check)
    tweets = filter_tweets_by_date(tweets, start_date, end_date)
    print(f"Tweets in date range: {len(tweets)}")
    
    # Group into threads
    standalone_tweets, threads = group_tweets_into_threads(tweets, username)
    print(f"Standalone tweets: {len(standalone_tweets)}")
    print(f"Threads: {len(threads)}")
    
    # Get items with videos
    tweets_with_video, threads_with_video = get_tweets_needing_video_download(
        standalone_tweets, threads
    )
    
    print(f"\nTweets with videos: {len(tweets_with_video)}")
    print(f"Threads with videos: {len(threads_with_video)}")
    
    # Determine what to process
    if videos_only:
        tweets_to_process = tweets_with_video
        threads_to_process = threads_with_video
    else:
        tweets_to_process = standalone_tweets
        threads_to_process = threads
    
    if not tweets_to_process and not threads_to_process:
        print("\nNo tweets to process.")
        return
    
    # Process tweets
    print("\n" + "=" * 50)
    print("Downloading videos and saving data...")
    print("=" * 50 + "\n")
    
    video_success_count = 0
    video_fail_count = 0
    json_count = 0
    
    # Process standalone tweets
    for i, tweet in enumerate(tweets_to_process, 1):
        print(f"Processing tweet {i}/{len(tweets_to_process)}: {tweet.id}")
        
        # Download video if present
        if tweet.video_url:
            success, video_path, json_path = downloader.process_tweet(tweet)
            if success:
                print(f"  [OK] Video: {video_path}")
                video_success_count += 1
            else:
                print(f"  [FAIL] Video download failed")
                video_fail_count += 1
        else:
            # Just save JSON
            json_path = downloader.save_tweet_json(tweet)
        
        if json_path:
            print(f"  [OK] JSON: {json_path}")
            json_count += 1
    
    # Process threads
    for i, thread in enumerate(threads_to_process, 1):
        print(f"Processing thread {i}/{len(threads_to_process)}: {thread.id} ({len(thread.tweets)} tweets)")
        
        # Download video if present
        if thread.has_video():
            success, video_path, json_path = downloader.process_thread(thread)
            if success:
                print(f"  [OK] Video: {video_path}")
                video_success_count += 1
            else:
                print(f"  [FAIL] Video download failed")
                video_fail_count += 1
        else:
            # Just save JSON
            json_path = downloader.save_thread_json(thread)
        
        if json_path:
            print(f"  [OK] JSON: {json_path}")
            json_count += 1
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Total items processed: {len(tweets_to_process) + len(threads_to_process)}")
    print(f"JSON files saved: {json_count}")
    print(f"Successful video downloads: {video_success_count}")
    print(f"Failed video downloads: {video_fail_count}")
    print(f"Output directory: {output_dir}")


def main() -> None:
    """Main entry point."""
    # Load environment variables
    load_dotenv()
    
    args = parse_args()
    
    if not validate_args(args):
        sys.exit(1)
    
    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date).replace(hour=23, minute=59, second=59)
    output_dir = Path(args.output)
    
    run_scraper(
        url=args.url,
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir,
        limit=args.limit,
        videos_only=args.videos_only,
    )


if __name__ == "__main__":
    main()
