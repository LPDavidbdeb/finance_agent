"""
OECD & Macro Data Access Object

Provides functions to fetch historical macro data (GDP, Inflation) to drive
dynamic portfolio weighting and liability adjustments.

Primary Sources:
- OECD SDMX API (for member countries & OECD-specific metrics)
- World Bank API (for global GDP weighting including non-OECD members like China)
"""

import requests
import pandas as pd
from io import StringIO
from typing import Dict, List, Optional
from datetime import datetime

class MacroDAO:
    @staticmethod
    def fetch_world_bank_gdp(countries: List[str], start_year: int = 1995) -> pd.DataFrame:
        """
        Fetches nominal GDP in current USD from World Bank API.
        Reliable for global weighting (includes China, India, etc.)
        """
        end_year = datetime.now().year
        country_str = ";".join(countries)
        url = f"https://api.worldbank.org/v2/country/{country_str}/indicator/NY.GDP.MKTP.CD"
        params = {
            "format": "json",
            "date": f"{start_year}:{end_year}",
            "per_page": 1000
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if len(data) < 2:
            return pd.DataFrame()
            
        records = data[1]
        df = pd.DataFrame([
            {
                "year": int(r["date"]),
                "country": r["countryiso3code"],
                "gdp": r["value"]
            }
            for r in records if r["value"] is not None
        ])
        
        return df.pivot(index="year", columns="country", values="gdp").sort_index()

    @staticmethod
    def calculate_biased_gdp_weights(
        gdp_df: pd.DataFrame, 
        home_country: str = 'CAN', 
        home_bias: float = 0.20
    ) -> pd.DataFrame:
        """
        Calculates dynamic weights based on GDP with a specific Home Bias.
        
        Formula:
        Weight_Home = home_bias + (1 - home_bias) * (GDP_Home / GDP_Total)
        Weight_Other = (1 - home_bias) * (GDP_Other / GDP_Total)
        """
        # Calculate annual global total for the subset
        total_gdp = gdp_df.sum(axis=1)
        
        weights = pd.DataFrame(index=gdp_df.index)
        
        # Apply Home Bias
        weights[home_country] = home_bias + (1 - home_bias) * (gdp_df[home_country] / total_gdp)
        
        # Apply shared GDP weighting for the rest
        other_countries = [c for c in gdp_df.columns if c != home_country]
        for country in other_countries:
            weights[country] = (1 - home_bias) * (gdp_df[country] / total_gdp)
            
        return weights

if __name__ == "__main__":
    # Test fetch and weight calculation
    countries = ["CAN", "USA", "EMU", "CHN", "IND"] # EMU = Euro Area
    dao = MacroDAO()
    gdp = dao.fetch_world_bank_gdp(countries, start_year=1995)
    
    print("\nHistorical Nominal GDP (Billions USD):")
    print((gdp / 1e9).tail())
    
    weights = dao.calculate_biased_gdp_weights(gdp, home_bias=0.25)
    print("\nDynamic Biased Weights (Home Bias = 25%):")
    print(weights.tail())
    
    weights.to_csv("notebooks/historical_gdp_weights.csv")
    print("\nWeights saved to notebooks/historical_gdp_weights.csv")
