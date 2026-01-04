import os
import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv
from agents.normalization import normalize_currency_code, normalize_date
from agents.funding_classifier import (
    classify_funding_status,
    classify_implementation_status,
    dedupe_project_key,
    summarize_unmapped_fields,
)

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
    """Get existing URL-country or project_key combinations from the database"""
    try:
        response = supabase.table(table_name).select("url, country, project_key").execute()
        existing = set()
        
        for record in response.data:
            url_country = (record.get('url', ''), record.get('country', ''))
            if url_country[0] or url_country[1]:
                existing.add(("url_country", url_country))
            proj_key = record.get('project_key')
            if proj_key:
                existing.add(("project_key", proj_key))
        
        logger.info(f"Found {len(existing)} existing dedupe keys")
        return existing
    
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
    mapped_fields = set()
    # Handle sector field with multiple fallback strategies
    sector = item.get('sector')
    if isinstance(sector, list):
        sector = ', '.join(sector)
    mapped_fields.update(['sector'])
    
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
    
    # Project-level fields for funded city projects
    project_title = item.get('ProjectTitle') or item.get('project_name') or item.get('name', '')
    location = item.get('Location') or {}
    project_city = location.get('CityName') if isinstance(location, dict) else item.get('city', '')
    project_region = location.get('Region') if isinstance(location, dict) else item.get('region', '')
    project_country = location.get('Country') if isinstance(location, dict) else item.get('country', '')
    mapped_fields.update(['ProjectTitle', 'project_name', 'name', 'Location', 'city', 'region', 'country'])

    # Funding fields
    financing = item.get('Financing') or {}
    funding_amount = financing.get('TotalProjectCost') if isinstance(financing, dict) else item.get('funding_amount')
    funding_currency = normalize_currency_code(
        financing.get('CurrencyCode') if isinstance(financing, dict) else item.get('funding_currency')
    ) or ''
    funding_status_raw = item.get('ProjectStatus') or item.get('funding_status')
    funding_status = funding_status_raw or classify_funding_status(funding_status_raw)
    funding_source = None
    funders = item.get('Funders') or {}
    if isinstance(funders, dict):
        funding_source = funders.get('PrimaryFunderName') or None
        funding_authority = funders.get('FunderType')
    else:
        funding_authority = item.get('funding_authority')
    implementation_status = item.get('implementation_status') or classify_implementation_status(item.get('ProjectStatus'))
    mapped_fields.update(['Financing', 'funding_amount', 'funding_currency', 'ProjectStatus', 'funding_status', 'Funders', 'implementation_status', 'funding_authority'])

    # Dates
    approval_date = normalize_date(item.get('approval_date') or item.get('StartDate'))
    timeline_start = normalize_date(item.get('StartDate'))
    timeline_end = normalize_date(item.get('EndDate'))
    mapped_fields.update(['approval_date', 'StartDate', 'EndDate'])

    evidence_snippet = item.get('evidence_snippet') or ''
    inflation_note = item.get('inflation_note') or ''
    source_url = item.get('Traceability', {}).get('SourceUrl') if isinstance(item.get('Traceability'), dict) else item.get('url', '')

    # Build project_key for dedupe: title + city + year of start date
    project_year = None
    if timeline_start and isinstance(timeline_start, str) and len(timeline_start) >= 4:
        project_year = timeline_start[:4]
    project_key = dedupe_project_key(project_title, project_city or '', project_year)

    record = {
        'project_key': project_key,
        'project_name': project_title,
        'city': project_city,
        'region': project_region,
        'country': project_country,
        'sector': sector or '',
        'funding_status': funding_status or '',
        'implementation_status': implementation_status or '',
        'funding_amount': funding_amount if funding_amount is not None else '',
        'funding_currency': funding_currency or '',
        'funding_source': funding_source or '',
        'funding_authority': funding_authority or '',
        'approval_date': approval_date or '',
        'timeline_start': timeline_start or '',
        'timeline_end': timeline_end or '',
        'evidence_snippet': evidence_snippet,
        'source_url': source_url or item.get('url', ''),
        'inflation_note': inflation_note,
        # legacy fields for backward compatibility
        'method_of_access': item.get('method_of_access', ''),
        'data_format': data_format or '',
        'description': item.get('description', ''),
        'granularity': item.get('granularity', ''),
        'country_locode': item.get('country_locode', ''),
        'human_eval': 0,
        'accepted': 0
    }

    unmapped = summarize_unmapped_fields(item, mapped_fields)
    if unmapped:
        logger.debug(f"Unmapped fields for project {project_title}: {unmapped}")
    
    return record

def insert_records_to_supabase(supabase: Client, table_name: str, records: List[Dict[str, Any]], existing_combinations: set):
    """Insert records to Supabase, skipping duplicates"""
    inserted_count = 0
    skipped_count = 0
    
    for record in records:
        url = record.get('source_url', '')
        country = record.get('country', '')
        project_key = record.get('project_key')

        if ("project_key", project_key) in existing_combinations:
            logger.debug(f"Skipping duplicate by project_key: {project_key}")
            skipped_count += 1
            continue
        if ("url_country", (url, country)) in existing_combinations:
            logger.debug(f"Skipping duplicate by url/country: {url} for {country}")
            skipped_count += 1
            continue
        
        try:
            # Insert the record
            response = supabase.table(table_name).insert(record).execute()
            
            if response.data:
                logger.debug(f"Inserted record: {record.get('name', 'Unknown')} for {country}")
                inserted_count += 1
                # Add to existing combinations to avoid inserting duplicates in the same batch
                if project_key:
                    existing_combinations.add(("project_key", project_key))
                existing_combinations.add(("url_country", (url, country)))
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
