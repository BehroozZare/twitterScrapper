# Twitter/X Video Scraper & Farsi Transcriber

A Python tool to scrape tweets and download videos from Twitter/X profiles, then transcribe Farsi/Persian audio using AI speech-to-text.

## Features

### Scraper
- Download videos from Twitter/X profiles via API
- Filter tweets by date range
- Detect and group tweet threads
- Save tweet metadata as JSON
- Uses official Twitter API (no browser automation)
- Handles rate limiting automatically

### Transcriber
- Transcribe Farsi/Persian audio from videos
- Uses fine-tuned Whisper model (`vhdm/whisper-large-fa-v1`) for best Persian accuracy
- Generates timestamped transcription segments
- Updates existing JSON files or creates new transcript files
- Supports GPU acceleration (CUDA, MPS) and CPU fallback

## Requirements

- Python 3.10+
- Twitter API credentials (Basic tier or higher)
- FFmpeg (for audio extraction)
- GPU with ~10GB VRAM (recommended for transcription) or CPU (slower)

## Getting Twitter API Credentials

1. Go to [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. Create a new project and app
3. Generate the following credentials:
   - API Key and Secret
   - Access Token and Secret
   - Bearer Token

## Installation

1. Clone or download this project

2. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Install FFmpeg (required for transcriber):

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (using Chocolatey)
choco install ffmpeg
```

5. Set up your API credentials:

```bash
cp .env.example .env
```

6. Edit `.env` and add your Twitter API credentials:

```
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
TWITTER_BEARER_TOKEN=your_bearer_token
```

## Usage

### Basic Usage

Scrape videos from a Twitter profile within a date range:

```bash
python scraper.py --url https://x.com/username --start-date 2024-01-01 --end-date 2024-12-31
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `--url URL` | Twitter/X profile URL (required) |
| `--start-date DATE` | Start date for scraping, YYYY-MM-DD (required) |
| `--end-date DATE` | End date for scraping, YYYY-MM-DD (required) |
| `--output DIR` | Output directory (default: ./data) |
| `--limit N` | Maximum number of tweets to fetch |
| `--videos-only` | Only save tweets that have videos |

### Examples

```bash
# Scrape all videos from January 2024
python scraper.py --url https://x.com/elonmusk --start-date 2024-01-01 --end-date 2024-01-31

# Scrape with custom output directory
python scraper.py --url https://x.com/elonmusk --start-date 2024-01-01 --end-date 2024-12-31 --output ./my_videos

# Limit to 50 tweets
python scraper.py --url https://x.com/elonmusk --start-date 2024-01-01 --end-date 2024-12-31 --limit 50

# Only save tweets with videos (skip text-only tweets)
python scraper.py --url https://x.com/elonmusk --start-date 2024-01-01 --end-date 2024-12-31 --videos-only
```

## Step 2: Extract Audio

After scraping videos, extract audio from them for transcription.

### Basic Usage

```bash
# Extract audio from all videos in data folder
python transcriber.py extract-audio data/

# Extract audio from a single video
python transcriber.py extract-audio data/2024_01_15_1234567890_video.mp4

# Save audio to a different directory
python transcriber.py extract-audio data/ --output ./audio
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `input` | Video file or directory containing videos (required) |
| `--output DIR` | Output directory for audio files (default: same as video) |
| `--no-skip` | Re-extract audio even if voice file exists |

## Step 3: Transcribe Audio

Convert the extracted audio files to Farsi subtitles.

### Basic Usage

```bash
# Transcribe all audio files in data folder
python transcriber.py transcribe data/

# Update existing JSON files with transcript field
python transcriber.py transcribe data/ --update-json

# Save subtitles to a separate directory
python transcriber.py transcribe data/ --output ./subtitles
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `input` | Audio file or directory containing audio files (required) |
| `--update-json` | Update corresponding tweet JSON files with transcript field |
| `--output DIR` | Output directory for subtitle files (default: same as audio) |
| `--device` | Device for inference: cuda, mps, or cpu (default: auto-detect) |
| `--no-skip` | Re-transcribe audio even if subtitle exists |

### Examples

```bash
# Full workflow: extract audio then transcribe
python transcriber.py extract-audio data/
python transcriber.py transcribe data/

# Transcribe with GPU acceleration
python transcriber.py transcribe data/ --device cuda

# Update tweet JSON files with transcripts
python transcriber.py transcribe data/ --update-json

# Force re-transcription
python transcriber.py transcribe data/ --no-skip
```

## Output Format

Files are saved to the `data/` directory (or your custom output directory):

### Video Files

```
2024_01_15_1234567890_video.mp4
```

Format: `{YYYY}_{MM}_{DD}_{tweet_id}_video.mp4`

### Tweet JSON Files

Single tweet:
```
2024_01_15_1234567890_twitt.json
```

Thread:
```
2024_01_15_1234567890_thread_twitt.json
```

### Subtitle Files (after transcription)

```
2024_01_15_1234567890_subtitle.json
```

Format: `{YYYY}_{MM}_{DD}_{tweet_id}_subtitle.json`

### Audio Files (extracted during transcription)

```
2024_01_15_1234567890_voice.wav
```

Format: `{YYYY}_{MM}_{DD}_{tweet_id}_voice.wav`

### JSON Structure

**Single Tweet:**
```json
{
  "id": "1234567890",
  "author": "username",
  "text": "Tweet content here...",
  "date": "2024-01-15T14:30:00+00:00",
  "url": "https://x.com/username/status/1234567890",
  "video_url": "...",
  "video_file": "2024_01_15_1234567890_video.mp4",
  "is_retweet": false,
  "is_reply": false,
  "reply_to_id": null
}
```

**Single Tweet with Transcript (after running transcriber):**
```json
{
  "id": "1234567890",
  "author": "username",
  "text": "Tweet content here...",
  "date": "2024-01-15T14:30:00+00:00",
  "url": "https://x.com/username/status/1234567890",
  "video_url": "...",
  "video_file": "2024_01_15_1234567890_video.mp4",
  "is_retweet": false,
  "is_reply": false,
  "reply_to_id": null,
  "transcript": {
    "text": "Full Farsi transcript text here...",
    "language": "fa",
    "segments": [
      {"start": 0.0, "end": 2.5, "text": "First segment..."},
      {"start": 2.5, "end": 5.0, "text": "Second segment..."}
    ]
  }
}
```

**Thread:**
```json
{
  "id": "1234567890",
  "author": "username",
  "date": "2024-01-15T14:30:00+00:00",
  "tweets": [
    {"id": "1234567890", "text": "First tweet...", ...},
    {"id": "1234567891", "text": "Second tweet...", ...}
  ],
  "video_url": "...",
  "video_file": "2024_01_15_1234567890_video.mp4"
}
```

**Subtitle File (separate transcription output):**
```json
{
  "text": "Full Farsi transcript text here...",
  "language": "fa",
  "segments": [
    {"start": 0.0, "end": 2.5, "text": "First segment..."},
    {"start": 2.5, "end": 5.0, "text": "Second segment..."}
  ]
}
```

## Project Structure

```
ScrappingProject/
├── scraper.py              # Step 1: Scraper CLI
├── transcriber.py          # Step 2: Transcriber CLI
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── .env.example            # API credentials template
├── .env                    # Your API credentials (not in git)
├── .gitignore              # Git ignore rules
├── src/
│   ├── __init__.py
│   ├── twitter_api.py      # Twitter API v2 client
│   ├── extractor.py        # Tweet parsing and thread grouping
│   ├── downloader.py       # Video download with yt-dlp
│   ├── models.py           # Data models (Tweet, Thread, Transcription)
│   └── transcriber.py      # Audio extraction and Whisper transcription
└── data/                   # Output folder (created automatically)
```

## How It Works

### Step 1: Scraping
1. **API Authentication**: Uses Twitter API v2 with your Bearer Token
2. **Tweet Fetching**: Fetches tweets from user timeline with pagination
3. **Thread Detection**: Groups consecutive replies from the same author
4. **Video Download**: Uses yt-dlp to download videos from tweet URLs
5. **Data Storage**: Saves video files (`*_video.mp4`) and tweet metadata (`*_twitt.json`)

### Step 2: Audio Extraction
1. **FFmpeg Processing**: Uses FFmpeg to extract audio from MP4 videos
2. **Audio Conversion**: Converts to WAV format at 16kHz (optimal for Whisper)
3. **File Storage**: Saves audio files as `*_voice.wav`

### Step 3: Transcription
1. **Model Loading**: Loads `vhdm/whisper-large-fa-v1` Persian Whisper model
2. **Audio Processing**: Processes audio in 30-second chunks for efficiency
3. **Transcription**: Generates Farsi text from audio
4. **Timestamp Segments**: Creates timestamped segments for the transcript
5. **Data Storage**: Saves subtitles as `*_subtitle.json` or updates tweet JSON

## API Rate Limits

With the Basic tier ($100/month):
- 10,000 tweets/month read limit
- 900 requests per 15-minute window
- Each request returns up to 100 tweets

The scraper automatically waits when rate limited.

## Troubleshooting

### "Missing TWITTER_BEARER_TOKEN" error
Make sure you have created a `.env` file with your API credentials. Copy from `.env.example`:
```bash
cp .env.example .env
```

### "User not found" error
- Check the username is correct
- The account might be private or suspended

### No videos found
- The user might not have posted videos in the date range
- Try a wider date range or different user

### Rate limit errors
The scraper automatically handles rate limits by waiting. For large scrapes, this might take time.

### FFmpeg not found
Make sure FFmpeg is installed and accessible from your PATH:
```bash
ffmpeg -version
```

### CUDA out of memory
The Whisper model requires ~10GB VRAM. If you don't have enough GPU memory:
- Use `--device cpu` (slower but works on any machine)
- Close other GPU-intensive applications
- Try a smaller batch of videos at a time

### Transcription is slow on CPU
CPU transcription can take 5-10x longer than real-time audio length. For faster processing:
- Use a GPU with CUDA support
- On Apple Silicon Macs, MPS acceleration is used automatically

## Notes

- Retweets are automatically excluded (only original tweets are saved)
- The scraper respects Twitter's API terms of service
- Your API credentials are stored locally in `.env` (not committed to git)
- Videos are downloaded using yt-dlp for best quality

## License

MIT License
