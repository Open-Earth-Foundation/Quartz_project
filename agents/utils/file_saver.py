import logging
from pathlib import Path
import json # Added for JSON operations
import re # Added for sanitize_filename

logger = logging.getLogger(__name__)

def sanitize_filename(filename: str) -> str:
    """Sanitizes a string to be a valid filename."""
    # Remove or replace characters that are not allowed in filenames
    # This is a basic example; more comprehensive sanitization might be needed
    # depending on the target file systems.
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename) # Windows and common illegal chars
    filename = re.sub(r'\s+', '_', filename) # Replace spaces with underscores
    filename = filename.strip('._ ') # Remove leading/trailing dots, underscores, spaces
    if not filename: # If filename becomes empty after sanitization
        filename = "sanitized_empty_filename"
    max_len = 200 # Common max filename length, adjust as needed
    return filename[:max_len]

def save_scrape_to_file(data: str, country_name: str, filename: str, sector: str, run_id: str) -> str | None:
    """Saves scraped data to a file within a folder structure including country, sector, and run_id."""
    try:
        sanitized_sector = sector.replace(" ", "_").replace("/", "_").replace("\\", "_")
        sanitized_run_id = run_id.replace(" ", "_").replace("/", "_").replace("\\", "_")

        base_path = Path("data/scrape_results")
        # Sanitize country_name for path component
        sane_country_name = sanitize_filename(country_name) 
        sane_folder_name = sanitize_filename(f"{sanitized_sector}_{sanitized_run_id}")
        sane_filename = sanitize_filename(filename)

        filepath = base_path / sane_country_name / sane_folder_name / sane_filename
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(data)
        logger.info(f"Successfully saved scrape to {filepath}")
        return str(filepath)
    except Exception as e:
        path_str = 'path_not_yet_defined'
        if 'filepath' in locals():
            path_str = str(filepath)
        logger.error(f"Error saving scrape to file ({path_str}): {e}", exc_info=True)
        return None

def save_final_output_to_file(data_to_save: list, filename: str, output_dir: str) -> str | None:
    """Saves the final structured data to a JSON file in the specified output directory."""
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Filename should already be sanitized by the caller if needed, or we can sanitize here
        # For consistency with save_scrape_to_file, let's sanitize it here too.
        sane_filename = sanitize_filename(filename) 
        filepath = output_path / sane_filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        
        logger.info(f"Final structured data successfully saved to {filepath}")
        return str(filepath)
    except Exception as e:
        path_str = 'path_not_yet_defined'
        if 'filepath' in locals():
            path_str = str(filepath)
        logger.error(f"Error saving final output to JSON file ({path_str}): {e}", exc_info=True)
        return None 