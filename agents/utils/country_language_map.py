"""
Utility module for mapping countries to their primary languages.
This is used for prompt template substitution in the planner node.
"""

# Mapping of country names to their primary official language(s)
COUNTRY_LANGUAGE_MAP = {
    # South America
    "Chile": "Spanish",
    "Argentina": "Spanish",
    "Brazil": "Portuguese",
    "Colombia": "Spanish",
    "Peru": "Spanish",
    "Venezuela": "Spanish",
    "Ecuador": "Spanish",
    "Bolivia": "Spanish",
    "Paraguay": "Spanish",
    "Uruguay": "Spanish",
    "Guyana": "English",
    "Suriname": "Dutch",
    "French Guiana": "French",
    
    # Europe
    "Spain": "Spanish",
    "Germany": "German",
    "France": "French",
    "Italy": "Italian",
    "Poland": "Polish",
    "Greece": "Greek",
    "Portugal": "Portuguese",
    "Netherlands": "Dutch",
    "Belgium": "Dutch",
    "Sweden": "Swedish",
    "Denmark": "Danish",
    "Finland": "Finnish",
    "Norway": "Norwegian",
    "Austria": "German",
    "Switzerland": "German",
    "Czech Republic": "Czech",
    "Slovakia": "Slovak",
    "Hungary": "Hungarian",
    "Romania": "Romanian",
    "Bulgaria": "Bulgarian",
    "Croatia": "Croatian",
    "Slovenia": "Slovenian",
    "Serbia": "Serbian",
    "Bosnia and Herzegovina": "Bosnian",
    "Montenegro": "Montenegrin",
    "Macedonia": "Macedonian",
    "Albania": "Albanian",
    "Lithuania": "Lithuanian",
    "Latvia": "Latvian",
    "Estonia": "Estonian",
    "Ireland": "English",
    "United Kingdom": "English",
    "Cyprus": "Greek",
    "Malta": "Maltese",
    "Luxembourg": "Luxembourgish",
    "Iceland": "Icelandic",
    "Ukraine": "Ukrainian",
    "Belarus": "Belarusian",
    "Moldova": "Romanian",
    "Russia": "Russian",
    
    # Asia
    "China": "Chinese",
    "Japan": "Japanese",
    "South Korea": "Korean",
    "India": "Hindi",
    "Pakistan": "Urdu",
    "Bangladesh": "Bengali",
    "Thailand": "Thai",
    "Vietnam": "Vietnamese",
    "Indonesia": "Indonesian",
    "Philippines": "Filipino",
    "Malaysia": "Malay",
    "Singapore": "English",
    "Myanmar": "Burmese",
    "Cambodia": "Khmer",
    "Laos": "Lao",
    "Nepal": "Nepali",
    "Sri Lanka": "Sinhala",
    "Afghanistan": "Dari",
    "Iran": "Persian",
    "Iraq": "Arabic",
    "Saudi Arabia": "Arabic",
    "Israel": "Hebrew",
    "Turkey": "Turkish",
    "United Arab Emirates": "Arabic",
    "Kuwait": "Arabic",
    "Qatar": "Arabic",
    "Oman": "Arabic",
    "Yemen": "Arabic",
    "Bahrain": "Arabic",
    "Jordan": "Arabic",
    "Lebanon": "Arabic",
    "Syria": "Arabic",
    "Palestine": "Arabic",
    "Uzbekistan": "Uzbek",
    "Kazakhstan": "Kazakh",
    "Tajikistan": "Tajik",
    "Turkmenistan": "Turkmen",
    "Kyrgyzstan": "Kyrgyz",
    "Mongolia": "Mongolian",
    "Taiwan": "Chinese",
    "Thailand": "Thai",
    "Hong Kong": "Chinese",
    "Macao": "Chinese",
    
    # Africa
    "Egypt": "Arabic",
    "Algeria": "Arabic",
    "Morocco": "Arabic",
    "Tunisia": "Arabic",
    "Libya": "Arabic",
    "Sudan": "Arabic",
    "Kenya": "Swahili",
    "Tanzania": "Swahili",
    "Uganda": "English",
    "Rwanda": "Kinyarwanda",
    "Burundi": "Kirundi",
    "Democratic Republic of the Congo": "French",
    "Cameroon": "French",
    "Ivory Coast": "French",
    "Ghana": "English",
    "Nigeria": "English",
    "Senegal": "French",
    "Mali": "French",
    "Burkina Faso": "French",
    "Niger": "French",
    "Chad": "French",
    "South Africa": "English",
    "Botswana": "English",
    "Lesotho": "English",
    "Namibia": "English",
    "Zimbabwe": "English",
    "Zambia": "English",
    "Malawi": "English",
    "Mozambique": "Portuguese",
    "Angola": "Portuguese",
    "Benin": "French",
    "Togo": "French",
    "Sierra Leone": "English",
    "Liberia": "English",
    "Guinea": "French",
    "Guinea-Bissau": "Portuguese",
    "Cape Verde": "Portuguese",
    "Mauritius": "English",
    "Seychelles": "English",
    "Ethiopia": "Amharic",
    "Eritrea": "Tigrinya",
    "Djibouti": "French",
    "Somalia": "Somali",
    "Mauritania": "Arabic",
    "Madagascar": "Malagasy",
    "Eswatini": "English",
    "Gabon": "French",
    "Republic of the Congo": "French",
    "Equatorial Guinea": "Spanish",
    "Central African Republic": "French",
    
    # North America
    "Mexico": "Spanish",
    "Canada": "English",
    "United States": "English",
    "Guatemala": "Spanish",
    "Honduras": "Spanish",
    "El Salvador": "Spanish",
    "Nicaragua": "Spanish",
    "Costa Rica": "Spanish",
    "Panama": "Spanish",
    "Belize": "English",
    "Jamaica": "English",
    "Bahamas": "English",
    "Barbados": "English",
    "Trinidad and Tobago": "English",
    "Dominican Republic": "Spanish",
    "Haiti": "French",
    "Cuba": "Spanish",
    "Puerto Rico": "Spanish",
    
    # South America
    "Grenada": "English",
    "Saint Lucia": "English",
    "Dominica": "English",
    "Antigua and Barbuda": "English",
    "Saint Kitts and Nevis": "English",
    
    # Oceania
    "Australia": "English",
    "New Zealand": "English",
    "Fiji": "English",
    "Papua New Guinea": "English",
    "Solomon Islands": "English",
    "Vanuatu": "Bislama",
    "Samoa": "Samoan",
    "Tonga": "Tongan",
    "Kiribati": "English",
    "Micronesia": "English",
    "Palau": "English",
    "Marshall Islands": "English",
    "Nauru": "English",
    "Tuvalu": "English",
}


def get_primary_language(country_name: str) -> str:
    """
    Get the primary language for a given country.
    
    Args:
        country_name: The name of the country (case-insensitive)
    
    Returns:
        The primary language of the country, or "English" if not found
    """
    if not country_name:
        return "English"
    
    # Try exact match first
    if country_name in COUNTRY_LANGUAGE_MAP:
        return COUNTRY_LANGUAGE_MAP[country_name]
    
    # Try case-insensitive match
    for key, value in COUNTRY_LANGUAGE_MAP.items():
        if key.lower() == country_name.lower():
            return value
    
    # Default to English if not found
    return "English"


def get_primary_languages_list(country_name: str) -> list:
    """
    Get the primary languages for a given country as a list.
    
    Args:
        country_name: The name of the country
    
    Returns:
        A list containing the primary language(s)
    """
    language = get_primary_language(country_name)
    return [language]

