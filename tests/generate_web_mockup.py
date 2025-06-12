import argparse
import os
import logging
import re
from urllib.parse import urlparse
from firecrawl import FirecrawlApp
FIRECRAWL_AVAILABLE = True

from agents.utils import sanitize_filename

# Attempt to import config, handle if it's not found during standalone execution
try:
    import config
    FIRECRAWL_API_KEY = config.FIRECRAWL_API_KEY
except ImportError:
    # Fallback if running standalone or config is not in PYTHONPATH
    # You might need to set this manually or via .env if config is not found
    from dotenv import load_dotenv
    load_dotenv()
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    if not FIRECRAWL_API_KEY:
        print("Warning: FIRECRAWL_API_KEY not found in .env or config.py. Script may fail.")


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = "tests/mock_data/webpages"

def main():
    parser = argparse.ArgumentParser(description="Generate a mockup of a website using Firecrawl.")
    parser.add_argument("--url", required=True, help="The URL of the website to mockup.")
    parser.add_argument("--output_dir", default=DEFAULT_OUTPUT_DIR, help=f"Directory to save the mockup. Defaults to {DEFAULT_OUTPUT_DIR}")
    args = parser.parse_args()

    if not FIRECRAWL_AVAILABLE:
        logger.error("Firecrawl library is not installed. Please install it with 'pip install firecrawl-py'.")
        return

    if not FIRECRAWL_API_KEY:
        logger.error("FIRECRAWL_API_KEY is not set. Please set it in your .env file or config.py.")
        return

    try:
        firecrawl_app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize FirecrawlApp: {e}")
        return

    output_dir = args.output_dir
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")
        except OSError as e:
            logger.error(f"Failed to create output directory {output_dir}: {e}")
            return
            
    output_filename = sanitize_filename(args.url)
    output_path = os.path.join(output_dir, output_filename)

    logger.info(f"Attempting to scrape URL: {args.url}")
    try:
        # Firecrawl's scrape_url returns an object with attributes like .markdown, .html etc.
        scraped_data = firecrawl_app.scrape_url(args.url, only_main_content=True)
        
        content_to_save = None
        output_ext = ".md" # Default to markdown

        if scraped_data:
            if hasattr(scraped_data, 'markdown') and scraped_data.markdown:
                content_to_save = scraped_data.markdown
                logger.info("Using Markdown content from Firecrawl.")
            elif hasattr(scraped_data, 'html') and scraped_data.html: # Check for .html if markdown is not present/empty
                content_to_save = scraped_data.html
                output_ext = ".html"
                logger.info("Markdown not found or was empty, using HTML content from Firecrawl.")
            else:
                logger.warning(f"No usable content (markdown, html, or content attribute) found in Firecrawl response for {args.url}. Response object: {vars(scraped_data) if scraped_data else 'None'}")
                return
        else:
            logger.warning(f"Firecrawl returned no data for {args.url}.")
            return

        # Adjust output path if extension changed
        if output_ext == ".html" and output_path.endswith(".md"):
            output_path = output_path[:-3] + ".html"
        
        if content_to_save:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content_to_save)
            logger.info(f"Successfully saved mockup for {args.url} to {output_path}")
        else:
            # This case should ideally be caught by the checks above
            logger.warning(f"No content was ultimately extracted to save for {args.url}.")

    except Exception as e:
        logger.error(f"An error occurred while scraping {args.url} or saving the file: {e}")

if __name__ == "__main__":
    main() 