import os
import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_environment_variables():
    """Load environment variables from .env file"""
    load_dotenv()
    
    supabase_url = os.getenv('VITE_SUPABASE_URL')
    supabase_key = os.getenv('VITE_SUPABASE_ANON_KEY')
    table_name = os.getenv('SUPABASE_TABLE_NAME', 'environmental_report')
    
    if not supabase_url or not supabase_key:
        raise ValueError("Missing required environment variables: VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY")
    
    return supabase_url, supabase_key, table_name

def create_supabase_client(url: str, key: str) -> Client:
    """Create and return Supabase client"""
    return create_client(url, key)

def get_existing_records(supabase: Client, table_name: str) -> set:
    """Get existing URL-country combinations from the database"""
    try:
        response = supabase.table(table_name).select("url, country").execute()
        existing_combinations = set()
        
        for record in response.data:
            # Create a tuple of (url, country) for duplicate checking
            combination = (record.get('url', ''), record.get('country', ''))
            existing_combinations.add(combination)
        
        logger.info(f"Found {len(existing_combinations)} existing URL-country combinations")
        return existing_combinations
    
    except Exception as e:
        logger.error(f"Error fetching existing records: {e}")
        return set()

def extract_country_from_filename(filename: str) -> Optional[str]:
    """Extract country name from filename pattern: results_{Country}_{sector}_{timestamp}.json"""
    if not filename.startswith('results_') or not filename.endswith('.json'):
        return None
    
    # Remove 'results_' prefix and '.json' suffix
    core_name = filename[8:-5]  # Remove 'results_' (8 chars) and '.json' (5 chars)
    
    # Split by underscore and reconstruct country name
    parts = core_name.split('_')
    if len(parts) < 4:  # Should have at least country, sector, date, and time parts
        return None
    
    # The filename pattern is: results_{Country}_{sector}_{YYYYMMDD}_{HHMMSS}.json
    # The last three parts should be sector, date (YYYYMMDD), and time (HHMMSS)
    # So everything except the last 3 parts is the country name
    country_parts = parts[:-3]
    if not country_parts:
        return None
    
    # Join country parts with spaces (convert underscores back to spaces)
    country_name = ' '.join(country_parts)
    return country_name

def get_available_countries(runs_folder: str = "runs") -> List[str]:
    """Get list of all available countries from JSON files in runs folder"""
    runs_path = Path(runs_folder)
    
    if not runs_path.exists():
        logger.error(f"Runs folder '{runs_folder}' does not exist")
        return []
    
    countries = set()
    for json_file in runs_path.glob("*.json"):
        country = extract_country_from_filename(json_file.name)
        if country:
            countries.add(country)
    
    return sorted(list(countries))

def read_json_files_from_runs(runs_folder: str = "runs", target_country: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read JSON files from the runs folder and extract structured data
    
    Args:
        runs_folder: Path to the runs folder
        target_country: If specified, only process files for this country
    """
    runs_path = Path(runs_folder)
    
    if not runs_path.exists():
        logger.error(f"Runs folder '{runs_folder}' does not exist")
        return []
    
    all_structured_data = []
    files_processed = 0
    files_skipped = 0
    
    for json_file in runs_path.glob("*.json"):
        # Extract country from filename
        file_country = extract_country_from_filename(json_file.name)
        
        # Skip if target_country is specified and this file doesn't match
        if target_country and file_country != target_country:
            files_skipped += 1
            logger.debug(f"Skipping {json_file.name} - country '{file_country}' doesn't match target '{target_country}'")
            continue
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            structured_data = data.get('structured_data', [])
            target_sector = data.get('target_sector')  # Extract target_sector from file
            
            # Extract sector from filename as additional fallback
            # Pattern: results_Country_sector_timestamp.json
            filename_parts = json_file.stem.split('_')
            filename_sector = None
            if len(filename_parts) >= 3:
                # Look for known sector names in filename
                known_sectors = ['afolu', 'ippu', 'waste', 'transportation', 'stationary_energy']
                for part in filename_parts:
                    if part.lower() in known_sectors:
                        filename_sector = part.lower()
                        break
            
            if structured_data:
                logger.info(f"Found {len(structured_data)} structured data items in {json_file.name} (Country: {file_country})")
                
                # Add metadata to each item
                for item in structured_data:
                    if target_sector:
                        item['_file_target_sector'] = target_sector
                    if filename_sector:
                        item['_filename_sector'] = filename_sector
                    item['_source_file'] = json_file.name
                    item['_file_country'] = file_country
                
                all_structured_data.extend(structured_data)
                files_processed += 1
            else:
                logger.warning(f"No structured_data found in {json_file.name}")
                files_processed += 1
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON file {json_file}: {e}")
        except Exception as e:
            logger.error(f"Error reading file {json_file}: {e}")
    
    if target_country:
        logger.info(f"Filtered for country '{target_country}': {files_processed} files processed, {files_skipped} files skipped")
    else:
        logger.info(f"Processed all files: {files_processed} files processed")
    
    logger.info(f"Total structured data items collected: {len(all_structured_data)}")
    return all_structured_data

def prepare_record_for_insertion(item: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare a structured data item for database insertion"""
    # Handle sector field with multiple fallback strategies
    sector = item.get('sector')
    if isinstance(sector, list):
        sector = ', '.join(sector)
    
    # Use multiple fallbacks if sector is empty or None
    if not sector:
        # Fallback 1: target_sector from file metadata
        sector = item.get('_file_target_sector', '')
        
        # Fallback 2: sector extracted from filename
        if not sector:
            sector = item.get('_filename_sector', '')
    
    # Handle data_format field - convert list to string if necessary
    data_format = item.get('data_format')
    if isinstance(data_format, list):
        data_format = ', '.join(data_format)
    
    # Handle subsector field - convert list to string if necessary
    subsector = item.get('subsector')
    if isinstance(subsector, list):
        subsector = ', '.join(subsector)
    
    record = {
        'name': item.get('name', ''),
        'method_of_access': item.get('method_of_access', ''),
        'sector': sector or '',
        'data_format': data_format or '',
        'description': item.get('description', ''),
        'granularity': item.get('granularity', ''),
        'url': item.get('url', ''),
        'country': item.get('country', ''),
        'country_locode': item.get('country_locode', ''),
        'human_eval': 0,
        'accepted': 0
    }
    
    return record

def insert_records_to_supabase(supabase: Client, table_name: str, records: List[Dict[str, Any]], existing_combinations: set):
    """Insert records to Supabase, skipping duplicates"""
    inserted_count = 0
    skipped_count = 0
    
    for record in records:
        url = record.get('url', '')
        country = record.get('country', '')
        combination = (url, country)
        
        # Skip if this URL-country combination already exists
        if combination in existing_combinations:
            logger.debug(f"Skipping duplicate: {url} for {country}")
            skipped_count += 1
            continue
        
        try:
            # Insert the record
            response = supabase.table(table_name).insert(record).execute()
            
            if response.data:
                logger.debug(f"Inserted record: {record.get('name', 'Unknown')} for {country}")
                inserted_count += 1
                # Add to existing combinations to avoid inserting duplicates in the same batch
                existing_combinations.add(combination)
            else:
                logger.warning(f"No data returned for insertion: {record.get('name', 'Unknown')}")
                
        except Exception as e:
            logger.error(f"Error inserting record {record.get('name', 'Unknown')}: {e}")
    
    logger.info(f"Insertion complete: {inserted_count} records inserted, {skipped_count} records skipped (duplicates)")
    return inserted_count, skipped_count

def main(target_country: Optional[str] = None):
    """Main function to orchestrate the data insertion process
    
    Args:
        target_country: If specified, only process files for this country
    """
    try:
        # Load environment variables
        supabase_url, supabase_key, table_name = load_environment_variables()
        logger.info(f"Using table: {table_name}")
        
        if target_country:
            logger.info(f"Filtering data for country: {target_country}")
            
            # Show available countries
            available_countries = get_available_countries()
            logger.info(f"Available countries in runs folder: {', '.join(available_countries)}")
            
            if target_country not in available_countries:
                logger.warning(f"Target country '{target_country}' not found in available countries.")
                logger.info("Available countries:")
                for country in available_countries:
                    logger.info(f"  - {country}")
                return
        else:
            logger.info("Processing all countries")
        
        # Create Supabase client
        supabase = create_supabase_client(supabase_url, supabase_key)
        logger.info("Supabase client created successfully")
        
        # Get existing records to avoid duplicates
        existing_combinations = get_existing_records(supabase, table_name)
        
        # Read structured data from JSON files
        all_structured_data = read_json_files_from_runs(target_country=target_country)
        
        if not all_structured_data:
            logger.warning("No structured data found to insert")
            return
        
        # Prepare records for insertion
        records_to_insert = []
        for item in all_structured_data:
            try:
                record = prepare_record_for_insertion(item)
                records_to_insert.append(record)
            except Exception as e:
                logger.error(f"Error preparing record: {e}")
        
        logger.info(f"Prepared {len(records_to_insert)} records for insertion")
        
        # Insert records to Supabase
        inserted_count, skipped_count = insert_records_to_supabase(
            supabase, table_name, records_to_insert, existing_combinations
        )
        
        logger.info(f"Process completed successfully!")
        logger.info(f"Summary: {inserted_count} new records inserted, {skipped_count} duplicates skipped")
        
        if target_country:
            logger.info(f"Data processed for country: {target_country}")
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Insert research data to Supabase database')
    parser.add_argument('--country', '-c', type=str, help='Target country to process (e.g., "United Arab Emirates")')
    parser.add_argument('--list-countries', '-l', action='store_true', help='List all available countries and exit')
    
    args = parser.parse_args()
    
    if args.list_countries:
        print("Available countries:")
        countries = get_available_countries()
        for country in countries:
            print(f"  - {country}")
    else:
        main(target_country=args.country) 