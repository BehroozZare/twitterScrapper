"""Tweet parsing and thread grouping from API responses."""

from datetime import datetime
from typing import Optional
from dateutil import parser as date_parser

from .models import Tweet, Thread


def parse_api_tweet(data: dict) -> Optional[Tweet]:
    """
    Parse API tweet data into a Tweet object.
    
    Args:
        data: Tweet dictionary from Twitter API
        
    Returns:
        Tweet object or None if parsing fails
    """
    try:
        # Parse datetime
        date = None
        if data.get("datetime"):
            date = date_parser.parse(data["datetime"])
        else:
            date = datetime.now()
        
        return Tweet(
            id=data["id"],
            author=data["author"],
            text=data["text"],
            date=date,
            url=data["url"],
            video_url=data.get("videoUrl"),
            is_retweet=data.get("isRetweet", False),
            is_reply=data.get("isReply", False),
            reply_to_id=data.get("replyToId"),
        )
    except Exception as e:
        print(f"Error parsing tweet data: {e}")
        return None


def filter_tweets_by_date(
    tweets: list[Tweet],
    start_date: datetime,
    end_date: datetime,
) -> list[Tweet]:
    """
    Filter tweets to only include those within the date range.
    
    Args:
        tweets: List of Tweet objects
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)
        
    Returns:
        Filtered list of tweets
    """
    filtered = []
    for t in tweets:
        tweet_date = t.date.replace(tzinfo=None) if t.date.tzinfo else t.date
        if start_date <= tweet_date <= end_date:
            filtered.append(t)
    return filtered


def filter_tweets_with_video(tweets: list[Tweet]) -> list[Tweet]:
    """Filter to only tweets that have videos."""
    return [t for t in tweets if t.video_url]


def group_tweets_into_threads(
    tweets: list[Tweet],
    target_author: str,
) -> tuple[list[Tweet], list[Thread]]:
    """
    Group tweets into threads based on reply chains.
    
    A thread is identified when an author replies to their own tweet.
    
    Args:
        tweets: List of Tweet objects
        target_author: The author we're scraping (for thread detection)
        
    Returns:
        Tuple of (standalone_tweets, threads)
    """
    # Index tweets by ID for quick lookup
    tweet_by_id = {t.id: t for t in tweets}
    
    # Track which tweets are part of threads
    in_thread = set()
    threads = []
    
    # Find thread starters (tweets that are replied to by the same author)
    for tweet in tweets:
        if tweet.is_reply and tweet.reply_to_id:
            parent = tweet_by_id.get(tweet.reply_to_id)
            if parent and parent.author == tweet.author == target_author:
                # This is a thread continuation
                if parent.id not in in_thread:
                    # Start a new thread
                    thread = Thread(
                        id=parent.id,
                        author=parent.author,
                        date=parent.date,
                        tweets=[parent],
                    )
                    threads.append(thread)
                    in_thread.add(parent.id)
                
                # Add this tweet to the thread
                for thread in threads:
                    if thread.id == parent.id or parent.id in [t.id for t in thread.tweets]:
                        if tweet.id not in in_thread:
                            thread.tweets.append(tweet)
                            in_thread.add(tweet.id)
                        break
    
    # Sort tweets within each thread by date
    for thread in threads:
        thread.tweets.sort(key=lambda t: t.date)
        # Set video URL from first tweet with video
        thread.video_url = thread.get_first_video_url()
    
    # Get standalone tweets (not part of any thread)
    standalone = [t for t in tweets if t.id not in in_thread]
    
    return standalone, threads


def has_video_content(tweet: Tweet) -> bool:
    """Check if a tweet has video content (video URL or could have video)."""
    return tweet.video_url is not None


def get_tweets_needing_video_download(
    standalone_tweets: list[Tweet],
    threads: list[Thread],
) -> tuple[list[Tweet], list[Thread]]:
    """
    Get tweets and threads that have videos to download.
    
    Args:
        standalone_tweets: List of standalone Tweet objects
        threads: List of Thread objects
        
    Returns:
        Tuple of (tweets_with_video, threads_with_video)
    """
    tweets_with_video = [t for t in standalone_tweets if t.video_url]
    threads_with_video = [t for t in threads if t.has_video()]
    
    return tweets_with_video, threads_with_video
