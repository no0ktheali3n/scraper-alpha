# utils/post_to_twitter.py – Posts full summary threads to Twitter using Tweepy with polish improvements

import sys
import os
import json
import time
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Ensure project root is in path for utils import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.twitter_threading import generate_tweet_thread
from utils.tweepy_client import post_tweet
from utils.logger import get_logger

load_dotenv()

# Setup logger
logger = get_logger("poster")

# Constants
DEFAULT_HASHTAGS = ["#AI"]
SUMMARY_PATH = "/tmp/summarized_output.json"
#SUMMARY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "summarized_output.json"))
ARCHIVE_DIR = "/tmp/archive"
#ARCHIVE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "archive"))

REQUIRED_ENV_VARS = [
    "TWITTER_BEARER_TOKEN", "TWITTER_API_KEY", "TWITTER_API_SECRET",
    "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"
]

# ENV validation
def validate_env_vars(skip_if_dry_run=False):
    if skip_if_dry_run:
        return
    missing = [key for key in REQUIRED_ENV_VARS if not os.getenv(key)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")


# Load summaries
def load_articles():
    try:
        with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"[ERROR] summarized_output.json not found at {SUMMARY_PATH}")
        return []

# Archive summaries
def archive_output_file():
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(ARCHIVE_DIR, f"summarized_output_{timestamp}.json")
    os.rename(SUMMARY_PATH, archive_path)
    logger.info(f"Archived summarized_output.json to {archive_path}")

def run_posting_pipeline(variant="summary", limit=0, dry_run=False, confirm_post=False, start_index=0):
    validate_env_vars(skip_if_dry_run=dry_run)
    articles = load_articles()
    results = []

    for i, article in enumerate(articles[start_index : start_index + limit]):
        logger.info(f"Posting Article {start_index + i + 1}: {article.get('title', '')[:60]}")
        metadata = post_thread(article, variant=variant, dry_run=dry_run)
        if metadata and not dry_run:
            archive_output_file()
            logger.info(f"Appending metadata: {metadata}")
            results.append(metadata)

    return results

# Post full summary as a thread
def post_thread(article, variant="summary", dry_run=False, confirm_post=False):
    summary = article.get(variant, "")
    title = article.get("title", "")
    url = article.get("url", "")

    raw_tags = article.get("hashtags", "")
    if isinstance(raw_tags, str):
        hashtags = [tag for tag in raw_tags.split(",") if tag.startswith("#")]
    else:
        hashtags = [tag for tag in raw_tags if isinstance(tag, str) and tag.startswith("#")]
    
    tag_block = DEFAULT_HASHTAGS + hashtags[:3]  # Limit to 3 hashtags

    thread = generate_tweet_thread(summary, title, url, tag_block)

    print("\n=== Tweet Thread Preview ===")
    for i, tweet in enumerate(thread):
        print(f"\n--- Tweet {i+1} ---\n{tweet}\nCharacters: {len(tweet)}")

    if dry_run:
        print("\n[DRY RUN] Skipping post...")
        return None
    if confirm_post:
        confirm = input("\nDo you want to post this thread to Twitter? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ Cancelled.")
            return None

    tweet_ids = []
    reply_to = None

    for i, tweet in enumerate(thread):
        print(f"\n🌀 Posting tweet {i+1} of {len(thread)}...")
        logger.info(f"Posting tweet {i+1} of {len(thread)}")
        tweet_id = post_tweet(tweet, reply_to_id=reply_to)
        if tweet_id:
            tweet_ids.append(tweet_id)
            reply_to = tweet_id
            time.sleep(2)
        else:
            print("❌ Error posting one of the tweets. Aborting thread.")
            logger.error("Error posting tweet. Aborting thread.")
            return None

    if tweet_ids:
        logger.info(f"Thread posted! View the first tweet: https://twitter.com/user/status/{tweet_ids[0]}")
        first_tweet_url = f"https://twitter.com/user/status/{tweet_ids[0]}"

    return {
        "article_title": title,
        "url": url,
        "variant": variant,
        "tweet_ids": tweet_ids,
        "thread_url": first_tweet_url
    }

# CLI Interface
def main():
    parser = argparse.ArgumentParser(description="Post AI summaries to Twitter as threads.")
    parser.add_argument("--variant", default="v1_summary", help="Summary variant to use (default: v1_summary)")
    parser.add_argument("--dry-run", action="store_true", help="Preview the thread without posting")
    parser.add_argument("--limit", type=int, default=2, help="Limit number of articles to post")
    args = parser.parse_args()

    if not args.dry_run:
        validate_env_vars()  # Only check secrets if we’re actually posting

    articles = load_articles()

    run_posting_pipeline(variant=args.variant, limit=args.limit, dry_run=args.dry_run)

    for i, article in enumerate(articles[:args.limit]):
        print(f"\n=== Posting Article {i+1}: {article.get('title', '')[:60]} ===")
        metadata = post_thread(article, variant=args.variant, dry_run=args.dry_run)
        if metadata and not args.dry_run:
            archive_output_file()


