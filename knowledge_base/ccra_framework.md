# Climate Change Risk Assessment (CCRA) Framework

This document provides a comprehensive overview of the Climate Change Risk Assessment framework used for dataset discovery. The CCRA framework is organized into three main components: Hazards, Exposure, and Vulnerability.

## Overview

Climate Change Risk Assessment follows the IPCC framework where:
**Risk = Hazard × Exposure × Vulnerability**

- **Hazards**: Climate-related physical events or trends that may cause harm
- **Exposure**: The presence of people, livelihoods, species, ecosystems, environmental functions, services, resources, infrastructure, or economic, social, or cultural assets in places that could be adversely affected
- **Vulnerability**: The propensity or predisposition to be adversely affected, encompassing susceptibility, lack of coping capacity, and lack of adaptive capacity

## 1. Hazards

Climate hazards are physical climate system events, trends, or their physical impacts that may cause harm.

### 1.1 Heatwave

**Definition**: Periods of excessively hot weather, which may be accompanied by high humidity
**Key Indicators**:

- Heat Wave Magnitude Index (HWMId)
- Warm Spell Duration Index (WSDI)
- Heat index exceedance days
- Wet Bulb Globe Temperature (WBGT)
- Daily maximum temperature percentiles (90th, 95th, 99th)
  **Spatial Resolution**: 250m-1km for cities; 1-10km for regions
  **Temporal Coverage**: Daily data aggregated to seasonal/annual summaries
  **Data Formats**: NetCDF, GeoTIFF, CSV time series

### 1.2 Drought

**Definition**: A period of abnormally dry weather sufficiently prolonged to cause water shortage
**Key Indicators**:

- Standardized Precipitation Index (SPI) - 1, 3, 6, 12 month
- Standardized Precipitation Evapotranspiration Index (SPEI)
- Soil moisture percentiles
- Streamflow/runoff anomalies
- Palmer Drought Severity Index (PDSI)
  **Spatial Resolution**: 1-10km typical; finer if downscaled
  **Temporal Coverage**: Monthly indices with multi-year drought frequency analysis
  **Data Formats**: NetCDF, GeoTIFF, time series data

### 1.3 Flood

**Definition**: Overflow of water onto normally dry land
**Subtypes**:

- **Riverine (Fluvial)**: River overflow due to excessive precipitation or snowmelt
- **Pluvial**: Surface water flooding from intense rainfall
- **Coastal**: Storm surge and sea level rise induced flooding
  **Key Indicators**:
- Water depth by return period (10, 50, 100, 500-year)
- Flood extent maps
- Flow velocity and hazard rating (depth × velocity)
- Annual Exceedance Probability (AEP)
  **Spatial Resolution**: ≤10m for urban areas; 10-30m for riverine
  **Data Formats**: GeoTIFF depth grids, vector flood extents

### 1.4 Landslide

**Definition**: Mass movement of rock, debris, or earth down a slope
**Key Indicators**:

- Landslide susceptibility index (0-1 probability)
- Slope stability factors
- Rainfall intensity thresholds
- Historical landslide inventory
  **Input Factors**: Slope, curvature, lithology, soil type, land cover, rainfall intensity
  **Spatial Resolution**: 10-30m preferred for terrain analysis
  **Data Formats**: GeoTIFF susceptibility maps, vector inventory polygons

### 1.5 Wildfire

**Definition**: Uncontrolled fire in wildland areas
**Key Indicators**:

- Fire Weather Index (FWI) components
- Burn probability maps
- Fire danger rating
- Wildland-Urban Interface (WUI) proximity
- Fuel moisture content
  **Spatial Resolution**: 250m-1km; finer for fuel mapping
  **Temporal Coverage**: Daily fire weather, seasonal burn probability
  **Data Formats**: GeoTIFF, NetCDF for weather indices

### 1.6 Extreme Precipitation

**Definition**: Heavy rainfall events exceeding normal patterns
**Key Indicators**:

- Intensity-Duration-Frequency (IDF) curves
- Annual maximum precipitation (AMAX)
- Sub-daily rainfall intensities (1, 3, 6, 24-hour)
- Return period precipitation amounts
  **Spatial Resolution**: Point measurements, 1-10km gridded products
  **Data Formats**: Time series, IDF tables, GeoTIFF grids

### 1.7 Windstorm

**Definition**: Extreme wind events including tropical cyclones, extratropical storms
**Key Indicators**:

- Maximum 3-second gust speeds
- Return period wind speeds (10, 50, 100-year)
- Storm track and intensity data
- Wind hazard maps
  **Spatial Resolution**: 1-10km, with local roughness corrections
  **Data Formats**: GeoTIFF wind speed maps, vector storm tracks

### 1.8 Cold Spell

**Definition**: Periods of unusually cold weather
**Key Indicators**:

- Cold Spell Duration Index (CSDI)
- Heating Degree Days (HDD) extremes
- Frost days frequency
- Minimum temperature percentiles
  **Applications**: Health impacts, energy demand, agriculture
  **Data Formats**: NetCDF, time series, GeoTIFF

### 1.9 Coastal Hazards

**Definition**: Sea level rise and coastal flooding threats
**Key Indicators**:

- Sea level rise projections (+0.5m, +1.0m, +2.0m scenarios)
- Storm surge heights by return period
- Coastal inundation extent
- Wave setup and run-up
- Erosion rates
  **Spatial Resolution**: High-resolution coastal DEMs required
  **Data Formats**: GeoTIFF inundation maps, vector shoreline data

## 2. Exposure

Assets, people, and systems that could be adversely affected by climate hazards.

### 2.1 People

**Definition**: Human populations at risk from climate hazards
**Key Datasets**:

- Population grids (age-stratified, sex-disaggregated)
- Population density maps
- Day vs. night population (commuting patterns)
- Vulnerable populations (elderly, children, disabled)
- Settlement footprints and urban extent
  **Spatial Resolution**: 100m-1km population grids preferred
  **Temporal Coverage**: Annual snapshots, decadal projections
  **Data Formats**: GeoTIFF population grids, vector settlement boundaries

### 2.2 Buildings

**Definition**: Residential, commercial, and institutional structures
**Key Datasets**:

- Building footprints with attributes (height, use, material, age)
- Floor area estimates
- Property values (where available)
- Construction materials and building codes
- Basement presence indicators
  **Attributes**: Use type, construction material, year built, number of floors
  **Spatial Resolution**: Individual building polygons preferred
  **Data Formats**: Vector building footprints, rasterized building density

### 2.3 Infrastructure

**Definition**: Critical systems supporting society and economy
**Subtypes**:

- **Energy**: Power plants, substations, transmission lines, pipelines
- **Transport**: Roads, bridges, railways, airports, ports
- **Water**: Treatment plants, pumping stations, reservoirs, distribution networks
- **Digital**: Cell towers, fiber networks, data centers
- **Health**: Hospitals, clinics, emergency services
  **Key Attributes**: Capacity, service area, redundancy, criticality level
  **Data Formats**: Vector point/line features with attribute tables

### 2.4 Agriculture

**Definition**: Agricultural assets and land use systems
**Key Datasets**:

- Crop type and extent mapping
- Livestock distribution
- Irrigation infrastructure
- Agricultural land values
- Planting and harvest calendars
  **Spatial Resolution**: 10-30m for crop mapping
  **Data Formats**: Land cover/use rasters, vector agricultural boundaries

### 2.5 Economy

**Definition**: Economic activities and asset values
**Key Datasets**:

- Gross Domestic Product (GDP) by region
- Economic activity by sector
- Business establishment locations
- Property and asset values
- Employment statistics
  **Proxies**: Nighttime lights, business density, property values
  **Data Formats**: Statistical tables, gridded economic indicators

## 3. Vulnerability

The propensity to be adversely affected by climate hazards.

### 3.1 Socioeconomic

**Definition**: Social and economic factors affecting adaptive capacity
**Key Indicators**:

- Income levels and poverty rates
- Education attainment
- Employment and unemployment rates
- Housing quality and crowding
- Access to resources and services
  **Orientation**: Higher values indicate greater vulnerability
  **Data Sources**: Census data, household surveys, administrative records
  **Spatial Resolution**: Administrative units (census tracts, districts)

### 3.2 Health

**Definition**: Health status and demographic factors affecting climate sensitivity
**Key Indicators**:

- Age structure (elderly >65, children <5)
- Disability rates
- Chronic disease prevalence (cardiovascular, respiratory)
- Baseline mortality and morbidity rates
- Healthcare access and quality
  **Applications**: Heat stress, air quality, vector-borne disease vulnerability
  **Data Formats**: Statistical tables, gridded health indicators

### 3.3 Access to Services

**Definition**: Spatial accessibility to essential services
**Key Indicators**:

- Travel time to nearest hospital/clinic
- Distance to emergency services (fire, police)
- Access to evacuation shelters
- Public transport availability
- Market and service accessibility
  **Measurement**: Travel time analysis, network analysis
  **Units**: Minutes travel time, kilometers distance
  **Data Formats**: GeoTIFF travel time surfaces, vector service locations

### 3.4 Environmental Buffers

**Definition**: Natural and built features that provide climate protection
**Key Indicators**:

- Urban tree canopy cover
- Green space accessibility
- Wetland and floodplain extent
- Permeable surface percentage
- Natural coastal protection (mangroves, reefs)
  **Function**: Heat mitigation, flood protection, air quality improvement
  **Spatial Resolution**: 10-30m for urban canopy, varies by feature type
  **Data Formats**: GeoTIFF land cover, vector green space boundaries

### 3.5 Governance

**Definition**: Institutional capacity for climate adaptation and response
**Key Indicators**:

- Disaster preparedness and response capacity
- Early warning system coverage
- Climate adaptation planning
- Emergency shelter capacity
- Institutional coordination mechanisms
  **Measurement**: Often qualitative assessments, capacity indices
  **Spatial Scale**: Administrative units, institutional boundaries
  **Data Formats**: Indicator databases, policy documents

## Data Quality and Metadata Requirements

### Essential Metadata Fields

- **Spatial Resolution**: Grid cell size or minimum mapping unit
- **Temporal Coverage**: Time period, update frequency
- **Coordinate Reference System**: Projection and datum
- **Data Lineage**: Processing methods, source datasets
- **Uncertainty**: Quality flags, confidence intervals
- **Scenarios**: Climate scenarios, socioeconomic pathways
- **Units**: Measurement units and definitions
- **NoData Policy**: How missing values are handled

### Quality Indicators

- **A Grade**: Locally validated, high spatial/temporal resolution
- **B Grade**: Regionally validated, moderate resolution
- **C Grade**: Global datasets, coarse resolution, first-order estimates

### Recommended Spatial Resolutions

- **Urban Analysis**: 10-100m
- **Regional Analysis**: 250m-1km
- **National Analysis**: 1-10km
- **Global Analysis**: 10-50km

### Temporal Requirements

- **Historical Baseline**: 1981-2010 or 1991-2020
- **Future Projections**: 2030s, 2050s, 2080s
- **Return Periods**: 10, 50, 100, 500-year events
- **Climate Scenarios**: RCP4.5/8.5 or SSP2-4.5/SSP5-8.5

## Integration Guidelines

### Risk Assessment Workflow

1. **Hazard Assessment**: Identify relevant climate hazards and obtain intensity/frequency data
2. **Exposure Mapping**: Map assets, people, and systems in hazard-prone areas
3. **Vulnerability Assessment**: Evaluate susceptibility and adaptive capacity
4. **Risk Calculation**: Combine hazard, exposure, and vulnerability components
5. **Uncertainty Analysis**: Propagate uncertainties through the assessment

### Data Alignment Requirements

- **Common Coordinate System**: All datasets projected to same CRS
- **Consistent Spatial Resolution**: Resample to common grid
- **Temporal Alignment**: Match baseline periods and projection horizons
- **NoData Handling**: Consistent treatment of missing values
- **Scenario Consistency**: Use compatible climate and socioeconomic scenarios

This framework provides the foundation for systematic discovery and integration of climate risk assessment datasets across all three CCRA components.
