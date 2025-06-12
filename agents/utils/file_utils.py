import re
from urllib.parse import urlparse

def sanitize_filename(url: str) -> str:
    """Sanitizes a URL to create a valid and descriptive filename."""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    path = parsed_url.path.strip('/')
    
    filename_parts = [domain]
    if path:
        # Replace path separators with underscores and remove trailing extensions
        path_part = re.sub(r'[\\/]', '_', path)
        path_part = re.sub(r'\.[^.]*$', '', path_part) # Remove extension like .html, .php
        filename_parts.append(path_part)

    base_filename = "_".join(filename_parts)
    
    # Remove or replace invalid filename characters (common across OS)
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', base_filename)
    # Replace multiple underscores with a single one
    sanitized = re.sub(r'_+', '_', sanitized)
    # Ensure it's not too long
    # The original function in generate_web_mockup.py appends ".md". 
    # This might need to be removed or made optional if the caller expects to control the extension.
    # For now, replicating the behavior. 
    # Consider if researcher.py's sanitization logic is preferred.
    return sanitized[:100] + ".md" 