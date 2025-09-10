# Comprehensive Exposure Indicators for CCRA Dataset Review

This document outlines the comprehensive exposure indicators that reviewers should use to evaluate datasets found during CCRA research. These criteria ensure that exposure datasets are suitable for climate risk assessment by covering all relevant aspects of human and physical systems at risk.

## Core Exposure Categories & Required Indicators

### 1. Demographic & Population Indicators

**Essential for all exposure assessments:**

- Population density (people/km²)
- Total population counts
- Age distribution (especially elderly 65+ and children 0-14)
- Dependency ratios
- Household size and composition
- Migration patterns (if available)

**Acceptable Sources:** WorldPop, CIESIN GPWv4, HRSL, National Census, UN DESA

### 2. Built Environment & Infrastructure

**Critical infrastructure locations:**

- Building footprints and polygons
- Built-up areas and urban extent
- Critical facilities (hospitals, schools, emergency services)
- Transportation networks (roads, railways, airports, ports)
- Energy infrastructure (power plants, substations, transmission lines)
- Water infrastructure (reservoirs, pipelines, treatment plants)

**Acceptable Sources:** GHSL, Copernicus WorldCover, OpenStreetMap, Healthsites.io, WRI Global Power Plant Database

### 3. Economic & Financial Exposure

**Asset values and economic indicators:**

- Property values and real estate assessments
- Replacement costs and insurance values
- Business/economic activity indicators
- Critical infrastructure replacement values
- Agricultural production values
- Industrial and commercial facility locations

**Acceptable Sources:** Real estate databases, Insurance industry data, National property records, UNIDO

### 4. Socioeconomic Vulnerability Indicators

**Adaptive capacity and vulnerability factors:**

- Poverty rates and deprivation indicators
- Education attainment and literacy rates
- Unemployment and employment structure
- Informal settlements and housing conditions
- Housing material vulnerability
- Access to basic services (electricity, water, sanitation)

**Acceptable Sources:** World Bank PovcalNet, UNESCO UIS, DHS, National statistical offices

### 5. Health & Social Services

**Public health infrastructure:**

- Health facility locations and capacity
- Accessibility to healthcare services
- Sanitation access and quality
- Nutrition status indicators
- Social protection coverage
- Insurance penetration rates

**Acceptable Sources:** WHO/UNICEF JMP, World Bank ASPIRE, National health ministries

### 6. Environmental & Geographic Factors

**Environmental exposure and quality:**

- Land cover and land use types
- Coastal settlements and low-lying areas
- Water sources and watershed boundaries
- Environmental quality (air pollution, PM2.5, NO2)
- Proximity to hazardous sites
- Ecosystem extent and biodiversity

**Acceptable Sources:** Copernicus LC, NASA MAIAC, ECMWF CAMS, HydroSHEDS, CoastalDEM

### 7. Governance & Resilience

**Institutional capacity:**

- Disaster response capacity and resources
- Early warning system coverage
- Community organizations and social capital
- Governance effectiveness indicators
- Corruption perception indices
- Digital connectivity and access

**Acceptable Sources:** World Bank WGI, UNDRR, Transparency International, ITU, GSMA

## Data Quality Requirements for CCRA

### Spatial Requirements

- **Preferred:** Point-level data for facilities, 100m-1km grids for population/socioeconomic
- **Minimum:** Administrative boundary level (national/regional)
- **Required:** Must have spatial component for risk mapping; gridded datasets must be 5 km or finer (≤5 km)

### Temporal Requirements

- **Preferred:** Recent data (last 5 years), multi-year series
- **Minimum:** Data from last 10 years
- **Required:** Temporal coverage appropriate for risk assessment

### Format Requirements

- **Preferred:** Spatial formats (Shapefile, GeoJSON, GeoTIFF/COG, NetCDF/Zarr)
- **Acceptable:** Tabular formats (CSV, Excel) with location data only when joinable to geometry (coordinates or administrative codes)
- **Required:** Machine-readable format suitable for GIS/risk analysis

### Source Authority

- **Preferred:** Government agencies, international organizations, research institutions
- **Acceptable:** Academic sources, reputable NGOs
- **Rejected:** Commercial blogs, personal websites, unverified sources

## Review Decision Criteria

### ACCEPT if the dataset:

- Covers multiple indicator categories with specific metrics
- Has location-specific data for the target area
- Comes from authoritative sources
- Includes spatial components for risk mapping
- Has appropriate temporal coverage
- Is in a usable format for analysis

### REJECT if the dataset:

- Contains only general/global data without location specificity
- Lacks key indicators (no population data, no infrastructure locations, no socioeconomic factors)
- Is from non-credible sources
- Has insufficient spatial or temporal coverage
- Is in unusable format or outdated
- Cannot be used for quantitative risk assessment

## Indicator Prioritization by Hazard Type

### Heatwave Hazards

- **Priority:** Population density, elderly populations, health facilities, urban heat islands, air conditioning access
- **Secondary:** Built-up areas, socioeconomic vulnerability, governance capacity

### Flood Hazards

- **Priority:** Population in flood zones, building locations, critical infrastructure, elevation data, drainage systems
- **Secondary:** Poverty rates, health facilities, emergency services, insurance coverage

### Landslide Hazards

- **Priority:** Buildings on steep slopes, population in hazard zones, road networks, emergency access routes
- **Secondary:** Housing construction materials, socioeconomic vulnerability, community preparedness

### Drought Hazards

- **Priority:** Agricultural areas, water sources, livestock density, rural populations, irrigation infrastructure
- **Secondary:** Poverty rates, food security indicators, social protection coverage

This comprehensive framework ensures that exposure datasets are thoroughly evaluated for their suitability in climate change risk assessments across all relevant dimensions of human and physical vulnerability.
