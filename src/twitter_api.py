"""Twitter API v2 client using Tweepy."""

import os
from datetime import datetime, timezone
from typing import Optional, Generator
from pathlib import Path

import tweepy
from dotenv import load_dotenv

from .models import Tweet, Thread


class TwitterAPIError(Exception):
    """Custom exception for Twitter API errors."""
    pass


class TwitterAPI:
    """Twitter API v2 client for fetching user tweets."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ):
        """
        Initialize the Twitter API client.
        
        Credentials can be passed directly or loaded from environment variables.
        
        Args:
            api_key: Twitter API key
            api_secret: Twitter API secret
            access_token: User access token
            access_token_secret: User access token secret
            bearer_token: App bearer token
        """
        # Load from environment if not provided
        load_dotenv()
        
        self.api_key = api_key or os.getenv("TWITTER_API_KEY")
        self.api_secret = api_secret or os.getenv("TWITTER_API_SECRET")
        self.access_token = access_token or os.getenv("TWITTER_ACCESS_TOKEN")
        self.access_token_secret = access_token_secret or os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        self.bearer_token = bearer_token or os.getenv("TWITTER_BEARER_TOKEN")
        
        # Validate credentials
        if not self.bearer_token:
            raise TwitterAPIError(
                "Missing TWITTER_BEARER_TOKEN. "
                "Please set it in your .env file or pass it directly."
            )
        
        # Initialize Tweepy client
        self.client = tweepy.Client(
            bearer_token=self.bearer_token,
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
            wait_on_rate_limit=True,  # Automatically wait when rate limited
        )
    
    def get_user_id(self, username: str) -> str:
        """
        Get the user ID for a username.
        
        Args:
            username: Twitter username (without @)
            
        Returns:
            User ID string
        """
        # Remove @ if present
        username = username.lstrip("@")
        
        try:
            user = self.client.get_user(username=username)
            if user.data is None:
                raise TwitterAPIError(f"User not found: {username}")
            return str(user.data.id)
        except tweepy.errors.NotFound:
            raise TwitterAPIError(f"User not found: {username}")
        except tweepy.errors.TweepyException as e:
            raise TwitterAPIError(f"Error fetching user: {e}")
    
    def get_user_tweets(
        self,
        username: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_results: int = 100,
        limit: Optional[int] = None,
    ) -> Generator[dict, None, None]:
        """
        Fetch tweets from a user's timeline.
        
        Args:
            username: Twitter username
            start_date: Only fetch tweets after this date
            end_date: Only fetch tweets before this date
            max_results: Results per API request (max 100)
            limit: Maximum total tweets to fetch (None = no limit)
            
        Yields:
            Tweet data dictionaries
        """
        user_id = self.get_user_id(username)
        
        # Convert dates to UTC if provided
        start_time = None
        end_time = None
        
        if start_date:
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            start_time = start_date.isoformat()
        
        if end_date:
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            end_time = end_date.isoformat()
        
        # Tweet fields to fetch
        tweet_fields = [
            "id",
            "text",
            "created_at",
            "author_id",
            "conversation_id",
            "in_reply_to_user_id",
            "referenced_tweets",
            "attachments",
            "public_metrics",
        ]
        
        # Media fields for video info
        media_fields = [
            "type",
            "url",
            "preview_image_url",
            "variants",
            "duration_ms",
        ]
        
        # Expansions to include media
        expansions = [
            "attachments.media_keys",
            "referenced_tweets.id",
            "author_id",
        ]
        
        user_fields = ["username", "name"]
        
        tweet_count = 0
        pagination_token = None
        
        while True:
            try:
                response = self.client.get_users_tweets(
                    id=user_id,
                    start_time=start_time,
                    end_time=end_time,
                    max_results=min(max_results, 100),
                    tweet_fields=tweet_fields,
                    media_fields=media_fields,
                    expansions=expansions,
                    user_fields=user_fields,
                    pagination_token=pagination_token,
                )
            except tweepy.errors.TweepyException as e:
                raise TwitterAPIError(f"Error fetching tweets: {e}")
            
            if response.data is None:
                break
            
            # Build media lookup from includes
            media_lookup = {}
            if response.includes and "media" in response.includes:
                for media in response.includes["media"]:
                    media_lookup[media.media_key] = media
            
            # Process each tweet
            for tweet in response.data:
                tweet_data = self._parse_tweet(tweet, media_lookup, username)
                yield tweet_data
                
                tweet_count += 1
                if limit and tweet_count >= limit:
                    return
            
            # Check for more pages
            if response.meta and "next_token" in response.meta:
                pagination_token = response.meta["next_token"]
            else:
                break
    
    def _parse_tweet(self, tweet, media_lookup: dict, username: str) -> dict:
        """
        Parse a tweet response into a dictionary.
        
        Args:
            tweet: Tweepy tweet object
            media_lookup: Dictionary of media_key -> media object
            username: The username we're fetching from
            
        Returns:
            Parsed tweet dictionary
        """
        # Get video URL if present
        video_url = None
        has_video = False
        
        if hasattr(tweet, "attachments") and tweet.attachments:
            media_keys = tweet.attachments.get("media_keys", [])
            for media_key in media_keys:
                media = media_lookup.get(media_key)
                if media and media.type == "video":
                    has_video = True
                    # Get the best quality video variant
                    if hasattr(media, "variants") and media.variants:
                        video_variants = [
                            v for v in media.variants
                            if v.get("content_type") == "video/mp4"
                        ]
                        if video_variants:
                            # Sort by bitrate (highest first)
                            video_variants.sort(
                                key=lambda v: v.get("bit_rate", 0),
                                reverse=True
                            )
                            video_url = video_variants[0].get("url")
                    break
        
        # Check if it's a reply
        is_reply = tweet.in_reply_to_user_id is not None
        reply_to_id = None
        is_retweet = False
        
        if hasattr(tweet, "referenced_tweets") and tweet.referenced_tweets:
            for ref in tweet.referenced_tweets:
                if ref.type == "replied_to":
                    reply_to_id = str(ref.id)
                elif ref.type == "retweeted":
                    is_retweet = True
        
        return {
            "id": str(tweet.id),
            "author": username,
            "text": tweet.text,
            "datetime": tweet.created_at.isoformat() if tweet.created_at else None,
            "url": f"https://x.com/{username}/status/{tweet.id}",
            "hasVideo": has_video,
            "videoUrl": video_url,
            "isRetweet": is_retweet,
            "isReply": is_reply,
            "replyToId": reply_to_id,
            "conversationId": str(tweet.conversation_id) if tweet.conversation_id else None,
        }
    
    def get_conversation_tweets(
        self,
        conversation_id: str,
        author_username: str,
    ) -> list[dict]:
        """
        Get all tweets in a conversation (thread) by the same author.
        
        Args:
            conversation_id: The conversation ID
            author_username: Filter to only this author's tweets
            
        Returns:
            List of tweet dictionaries in the conversation
        """
        try:
            # Search for tweets in this conversation
            query = f"conversation_id:{conversation_id} from:{author_username}"
            
            tweet_fields = [
                "id", "text", "created_at", "author_id",
                "conversation_id", "in_reply_to_user_id",
                "referenced_tweets", "attachments",
            ]
            media_fields = ["type", "url", "variants"]
            expansions = ["attachments.media_keys"]
            
            response = self.client.search_recent_tweets(
                query=query,
                tweet_fields=tweet_fields,
                media_fields=media_fields,
                expansions=expansions,
                max_results=100,
            )
            
            if response.data is None:
                return []
            
            media_lookup = {}
            if response.includes and "media" in response.includes:
                for media in response.includes["media"]:
                    media_lookup[media.media_key] = media
            
            tweets = []
            for tweet in response.data:
                tweet_data = self._parse_tweet(tweet, media_lookup, author_username)
                tweets.append(tweet_data)
            
            # Sort by date
            tweets.sort(key=lambda t: t.get("datetime", ""))
            
            return tweets
            
        except tweepy.errors.TweepyException as e:
            print(f"Warning: Could not fetch conversation {conversation_id}: {e}")
            return []


def create_twitter_api(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    access_token: Optional[str] = None,
    access_token_secret: Optional[str] = None,
    bearer_token: Optional[str] = None,
) -> TwitterAPI:
    """Create a TwitterAPI instance."""
    return TwitterAPI(
        api_key=api_key,
        api_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        bearer_token=bearer_token,
    )


def extract_username_from_url(url: str) -> str:
    """Extract username from a Twitter/X URL."""
    url = url.rstrip("/")
    # Handle both x.com and twitter.com URLs
    parts = url.split("/")
    for i, part in enumerate(parts):
        if part in ("x.com", "twitter.com") and i + 1 < len(parts):
            return parts[i + 1]
    raise ValueError(f"Could not extract username from URL: {url}")
