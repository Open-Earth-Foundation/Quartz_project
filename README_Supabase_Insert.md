# Supabase Data Insertion Script

This script reads JSON files from the `runs` folder and inserts the structured data into your Supabase database, while avoiding duplicate entries.

## Prerequisites

1. **Python 3.7+** installed on your system
2. **Supabase project** with the `city_climate_projects` table created
3. **Environment variables** set in your `.env` file

## Environment Variables

Make sure your `.env` file contains:

```
VITE_SUPABASE_URL="https://gsktkvdfgmvavwxatlmn.supabase.co"
VITE_SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdza3RrdmRmZ212YXZ3eGF0bG1uIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDU0MDE0NjQsImV4cCI6MjA2MDk3NzQ2NH0.0oZcjPiSG0pF0k2gGcM6bNRujOg251A6FRxuycT_nhI"
SUPABASE_TABLE_NAME="city_climate_projects"
```

## Database Schema

The script expects a table with this structure (funded city projects):

```sql
create table if not exists city_climate_projects (
    id serial primary key,
    project_key text unique,
    project_name text,
    city text,
    region text,
    country text,
    sector text,
    funding_status text,
    funding_amount numeric,
    funding_currency text,
    funding_source text,
    funding_authority text,
    approval_date date,
    implementation_status text,
    timeline_start date,
    timeline_end date,
    evidence_snippet text,
    source_url text,
    inflation_note text,
    method_of_access text,
    data_format text,
    description text,
    granularity text,
    country_locode text,
    human_eval integer default 0,
    accepted integer default 0
);
```

## How to Run

### Option 1: Using the Batch Script (Windows)

```cmd
run_supabase_insert.bat
```

### Option 2: Using PowerShell (Windows)

```powershell
.\run_supabase_insert.ps1
```

### Option 3: Manual Installation and Execution

```cmd
# Install dependencies
pip install -r requirements_supabase.txt

# Run the script
python insert_data_to_supabase.py
```

## What the Script Does

1. **Loads Environment Variables**: Reads Supabase credentials from `.env` file
2. **Connects to Supabase**: Creates a client connection to your database
3. **Checks for Duplicates**: Fetches existing URL-country and project_key combinations to avoid duplicates
4. **Reads JSON Files**: Scans the `runs` folder for all JSON files
5. **Extracts Structured Data**: Pulls the `structured_data` arrays from each JSON file
6. **Prepares Records**: Formats the data for database insertion, mapping funded-project fields (title, location, funding, dates, source_url)
7. **Inserts Data**: Adds new records to the database, skipping duplicates
8. **Logs Progress**: Provides detailed logging of the insertion process

## Features

- **Duplicate Prevention**: Checks project_key (title+city+year) and URL + country combination to avoid inserting the same data twice
- **Batch Processing**: Handles all JSON files in the runs folder at once
- **Error Handling**: Gracefully handles file reading errors and database insertion failures
- **Detailed Logging**: Provides comprehensive logs of the process
- **Data Formatting**: Automatically converts array fields (sector, data_format, subsector) to comma-separated strings
- **Default Values**: Sets `human_eval` and `Accepted` to 0 for all new records

## Output

The script will log:

- Number of JSON files processed
- Number of structured data items found
- Number of existing records in database
- Number of records inserted
- Number of duplicates skipped
- Any errors encountered

Example output:

```
2025-06-02 17:00:00,123 - INFO - Using table: environmental_report
2025-06-02 17:00:01,456 - INFO - Supabase client created successfully
2025-06-02 17:00:02,789 - INFO - Found 25 existing URL-country combinations
2025-06-02 17:00:03,012 - INFO - Found 18 structured data items in results_Canada_afolu_20250602_152740.json
2025-06-02 17:00:03,345 - INFO - Found 3 structured data items in results_Chile_ippu_20250602_162506.json
2025-06-02 17:00:04,678 - INFO - Total structured data items collected: 67
2025-06-02 17:00:05,901 - INFO - Prepared 67 records for insertion
2025-06-02 17:00:08,234 - INFO - Insertion complete: 42 records inserted, 25 records skipped (duplicates)
2025-06-02 17:00:08,567 - INFO - Process completed successfully!
2025-06-02 17:00:08,890 - INFO - Summary: 42 new records inserted, 25 duplicates skipped
```

## Troubleshooting

1. **"Missing required environment variables"**: Make sure your `.env` file is in the same directory and contains the correct variables
2. **"Runs folder does not exist"**: Ensure the `runs` folder exists in the same directory as the script
3. **Database connection errors**: Verify your Supabase URL and API key are correct
4. **Permission errors**: Make sure your Supabase API key has the necessary permissions to insert data

## Notes

- The script will skip any JSON files that don't contain a `structured_data` field
- Array fields (sector, data_format, subsector) are automatically converted to comma-separated strings
- The script is idempotent - you can run it multiple times safely without creating duplicates
