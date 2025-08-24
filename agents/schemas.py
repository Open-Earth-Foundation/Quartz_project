from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, HttpUrl

class SearchQuery(BaseModel):
    query: str = Field(..., description="The precise search query string to be used.")
    language: str = Field(default="en", description="ISO 639-1 language code for the query, e.g., 'en', 'es'. Defaults to 'en'.")
    priority: str = Field(default="medium", description="Priority of the search query, e.g., 'high', 'medium', 'low'. This can be used for initial sorting.")
    rank: int = Field(default=0, description="A numerical rank assigned by the planner, lower numbers indicate higher importance/earlier execution.")
    target_type: str = Field(default="generic", description="The type of information this query targets, e.g., 'climate_hazard', 'exposure_data', 'vulnerability_indicator', 'meteorological_data', 'risk_assessment'.")

class SearchPlanSchema(BaseModel):
    search_queries: List[SearchQuery] = Field(..., description="A list of search queries to be executed by the research agent.")
    target_country_locode: Optional[str] = Field(default=None, description="The 2-letter ISO 3166-1 alpha-2 country code (LOCODE) if identified, e.g., 'PL', 'DE'.")
    primary_languages: Optional[List[str]] = Field(default_factory=list, description="A list of primary languages spoken in the target country, e.g., ['Polish', 'German'].")
    key_institutions: Optional[List[str]] = Field(default_factory=list, description="List of key national institutions relevant to CCRA data (e.g., meteorological services, disaster management agencies).")
    international_sources: Optional[List[str]] = Field(default_factory=list, description="List of relevant international data sources (e.g., IPCC, UNFCCC, World Bank, ECMWF).")
    document_types: Optional[List[str]] = Field(default_factory=list, description="Common or expected document types containing relevant data (e.g., 'Climate Risk Assessment', 'National Adaptation Plan', '.nc', '.tif', '.csv').")
    confidence: Optional[str] = Field(default=None, description="Initial assessment of data availability confidence (e.g., 'High', 'Medium', 'Low').")
    challenges: Optional[List[str]] = Field(default_factory=list, description="Potential challenges in acquiring data for this country.")

class SearchResultItem(BaseModel):
    url: HttpUrl = Field(..., description="URL of the search result.")
    title: str = Field(..., description="Title of the search result.")
    content: str = Field(..., description="Relevant snippet or content from the search result.")
    score: Optional[float] = Field(default=None, description="Relevance score of the search result, if available.")

class ReviewerLLMResponse(BaseModel):
    overall_assessment_notes: str = Field(description="A concise summary of the LLM's findings, highlighting key strengths and weaknesses of the provided structured_data_json.")
    relevance_score: Literal["High", "Medium", "Low"] = Field(description="Relevance score assigned by the LLM.")
    relevance_reasoning: str = Field(description="Reasoning for the relevance score.")
    credibility_score: Literal["High", "Medium", "Low"] = Field(description="Credibility score assigned by the LLM.")
    credibility_reasoning: str = Field(description="Reasoning for the credibility score.")
    completeness_score: Literal["High", "Medium", "Low"] = Field(description="Completeness score assigned by the LLM.")
    completeness_reasoning: str = Field(description="Reasoning for the completeness score.")
    overall_confidence: Literal["High", "Medium", "Low"] = Field(description="Overall confidence in the data.")
    suggested_action: Literal["accept", "deep_dive", "reject"] = Field(description="The action suggested by the LLM.")
    action_reasoning: str = Field(description="Justification for the suggested action.")

    refinement_details: Optional[str] = Field(None, description="Specific details for refinement or deep dive if applicable, derived from action_reasoning.")

class DeepDiveAction(BaseModel):
    """Schema for the action decided by the DeepDiveProcessorLLM."""
    action_type: Literal["scrape", "crawl", "terminate_deep_dive"] = Field(description="The type of action to take: scrape (single URL), crawl (entire website/domain), or terminate")
    target: Optional[str] = Field(None, description="URL for scrape/crawl action. Must be null if terminating.")
    justification: str = Field(description="Clear reasoning for the chosen action.")
    max_pages: Optional[int] = Field(default=10, description="For crawl action: maximum pages to crawl (default: 10, max: 50)")
    exclude_patterns: Optional[List[str]] = Field(default=None, description="For crawl action: URL patterns to exclude (e.g., ['blog/*', 'admin/*'])")

class StructuredDataItem(BaseModel):
    """Schema for a single CCRA dataset item extracted from a document."""
    name: str
    url: str
    method_of_access: str = Field(description="How the data is accessed (e.g., download, API, web_interface, ftp, database)")
    
    # CCRA-specific categorization
    ccra_mode: Optional[str] = Field(default=None, description="CCRA component: hazards, exposure, or vulnerability")
    ccra_type: Optional[str] = Field(default=None, description="Specific type within mode (e.g., heatwave, buildings, socioeconomic)")

    # Enhanced exposure categorization
    exposure_category: Optional[str] = Field(default=None, description="Specific exposure category (population, infrastructure, economic, socioeconomic, environmental, etc.)")
    exposure_subcategory: Optional[str] = Field(default=None, description="Specific exposure subcategory (demographics, critical_infrastructure, transportation, health_facilities, etc.)")
    indicator_type: Optional[List[str]] = Field(default_factory=list, description="Types of indicators covered (e.g., ['population_density', 'building_footprints', 'poverty_rate', 'health_facilities'])")
    
    # Data characteristics
    data_format: Optional[str] = Field(default=None, description="Format of the data (e.g., NetCDF, GeoTIFF, CSV, JSON, API, Shapefile)")
    description: Optional[str] = Field(default=None, description="Brief description of the dataset content and methodology.")
    
    # Spatial and temporal coverage
    spatial_resolution: Optional[str] = Field(default=None, description="Spatial resolution (e.g., '1km', '250m', 'administrative units')")
    spatial_coverage: Optional[str] = Field(default=None, description="Geographic coverage (e.g., 'Global', 'Europe', 'National', 'Urban')")
    temporal_coverage: Optional[str] = Field(default=None, description="Time period covered (e.g., '1981-2010', '2021-2050', 'Daily 2020-2023')")
    temporal_resolution: Optional[str] = Field(default=None, description="Temporal resolution (e.g., 'Daily', 'Monthly', 'Annual', 'Return periods')")
    
    # Geographic information
    country: Optional[str] = Field(default=None, description="Primary country coverage (None for global datasets)")
    country_locode: Optional[str] = Field(default=None, description="ISO country code (None for global datasets)")
    city: Optional[str] = Field(default=None, description="City name if city-specific dataset")
    
    # Climate and scenario information
    climate_scenario: Optional[List[str]] = Field(default_factory=list, description="Climate scenarios if applicable (e.g., ['RCP4.5', 'RCP8.5', 'SSP2-4.5'])")
    baseline_period: Optional[str] = Field(default=None, description="Reference/baseline period (e.g., '1981-2010', '1991-2020')")
    projection_period: Optional[List[str]] = Field(default_factory=list, description="Future projection periods (e.g., ['2030s', '2050s', '2080s'])")
    
    # Data quality and processing
    data_source: Optional[str] = Field(default=None, description="Original data source or provider organization")
    processing_level: Optional[str] = Field(default=None, description="Level of processing (e.g., 'Raw', 'Processed', 'Derived', 'Modeled')")
    quality_grade: Optional[str] = Field(default=None, description="Quality assessment (A=high, B=medium, C=basic)")
    uncertainty_info: Optional[str] = Field(default=None, description="Information about data uncertainty or confidence intervals")
    
    # Technical metadata
    coordinate_system: Optional[str] = Field(default=None, description="Coordinate reference system (e.g., 'WGS84', 'EPSG:3857')")
    units: Optional[str] = Field(default=None, description="Data units (e.g., 'degrees Celsius', 'mm/day', 'persons/km2')")
    nodata_value: Optional[str] = Field(default=None, description="No-data value representation")
    
    # Legacy fields for compatibility
    year: Optional[List[int]] = Field(default_factory=list, description="Year(s) the data pertains to")
    value: Optional[Any] = Field(None, description="Actual data value, can be complex")
    confidence_score: Optional[float] = Field(None, description="Confidence score from extractor, if any")
    raw_text_snippet: Optional[str] = Field(None, description="Raw text snippet from which data was extracted")
    
    # Status and access information
    status: Optional[str] = Field(default=None, description="Dataset status (e.g., 'Active', 'Archived', 'Under development')")
    access_restrictions: Optional[str] = Field(default=None, description="Access limitations (e.g., 'Open', 'Registration required', 'Commercial')")
    last_updated: Optional[str] = Field(default=None, description="Last update date if available")

class ExtractorLLMResponse(BaseModel):
    extracted_data: List[StructuredDataItem] = Field(description="List of structured data items extracted from a document.")
    extraction_summary: str = Field(description="Summary of the extraction process for a single document.")
    confidence_score: Optional[float] = Field(None, description="Overall confidence in the extraction quality for this document.")

class RawReviewerLLMResponse(BaseModel):
    """Schema for the LLM response when reviewing raw scraped content."""
    overall_assessment: str = Field(description="A brief summary of the LLM's review of the raw documents provided.")
    documents_to_extract: List[str] = Field(default_factory=list, description="List of URLs from the input that the LLM identified as promising and worth sending to the Extractor agent.")
    suggested_next_action: str = Field(description="Suggested next step for the workflow (e.g., 'proceed_to_extraction', 'end').")
    action_reasoning: Optional[str] = Field(default=None, description="Justification for the suggested_next_action.")
   