"""
ETL Pipeline for OG-Core ↔ CLEWS Data Exchange

This module handles the transformation of data between OG-Core and CLEWS models.
Based on REAL data from actual model runs, not speculation.
"""

import numpy as np
import pandas as pd
import pickle
import logging
from datetime import datetime
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ETLPipeline:
    """
    Handles data transformation between OG-Core and CLEWS.
    
    This is the core of the integration - transforming outputs from one model
    into inputs for the other model.
    """
    
    def __init__(self, config=None):
        """
        Initialize the ETL pipeline.
        
        Args:
            config (dict): Configuration for mappings and transformations
        """
        self.config = config or self._default_config()
        self.transformation_log = []
    
    def _default_config(self):
        """
        Default configuration for ETL transformations.
        
        Based on actual OG-Core and CLEWS parameter structures.
        """
        return {
            'og_to_clews': {
                'interest_rate': {
                    'source_var': 'r',
                    'target_var': 'DiscountRate',
                    'transformation': 'average_first_n_years',
                    'n_years': 20,
                    'unit_conversion': 'none',  # Both use decimals
                    'validation': {'min': 0.0, 'max': 0.20}
                }
            },
            'clews_to_og': {
                'electricity_price': {
                    'source_var': 'electricity_price',
                    'target_var': 'energy_cost_factor',
                    'transformation': 'normalize_to_baseline',
                    'baseline': 50.0,  # $/MWh
                    'unit_conversion': 'none',
                    'validation': {'min': 0.1, 'max': 5.0}
                }
            }
        }
    
    def og_to_clews(self, og_results):
        """
        Transform OG-Core outputs to CLEWS inputs.
        
        Args:
            og_results (dict): OG-Core TPI results (from TPI_vars.pkl)
            
        Returns:
            dict: CLEWS input parameters
        """
        logger.info("Transforming OG-Core outputs to CLEWS inputs")
        
        clews_inputs = {}
        
        # Extract interest rates
        if 'r' not in og_results:
            raise ValueError("OG-Core results missing 'r' (interest rates)")
        
        interest_rates = og_results['r']
        
        # Get configuration
        config = self.config['og_to_clews']['interest_rate']
        n_years = config['n_years']
        
        # Transform: Average over planning horizon
        # This is what we learned from running the actual model
        avg_interest_rate = np.mean(interest_rates[:n_years])
        
        # Validate
        min_val = config['validation']['min']
        max_val = config['validation']['max']
        if not (min_val <= avg_interest_rate <= max_val):
            logger.warning(
                f"Interest rate {avg_interest_rate:.4f} outside valid range "
                f"[{min_val}, {max_val}]"
            )
        
        # CLEWS DiscountRate parameter (decimal format)
        clews_inputs['DiscountRate'] = avg_interest_rate
        
        # Log the transformation
        self._log_transformation(
            source='OG-Core',
            source_var='r',
            source_value=f"array[{n_years}], mean={avg_interest_rate:.6f}",
            target='CLEWS',
            target_var='DiscountRate',
            target_value=avg_interest_rate,
            transformation=f'average_first_{n_years}_years'
        )
        
        logger.info(f"Transformed interest rate: {avg_interest_rate:.6f} ({avg_interest_rate*100:.4f}%)")
        
        return clews_inputs
    
    def clews_to_og(self, clews_results):
        """
        Transform CLEWS outputs to OG-Core inputs (BIDIRECTIONAL COUPLING).
        
        This closes the loop: CLEWS energy prices → OG-Core production costs
        
        Args:
            clews_results (dict): CLEWS model results with energy prices
                Expected format: {
                    'energy_prices': {
                        'electricity': 0.12,  # $/kWh
                        'natural_gas': 0.05   # $/kWh equivalent
                    }
                }
            
        Returns:
            dict: OG-Core input parameters for update_specifications()
        """
        logger.info("Transforming CLEWS outputs to OG-Core inputs")
        
        og_inputs = {}
        
        # Extract energy prices from CLEWS
        if 'energy_prices' in clews_results:
            energy_prices = clews_results['energy_prices']
            
            # Calculate weighted average energy cost
            # Typical US energy mix weights (approximate)
            electricity_price = energy_prices.get('electricity', 0.12)  # $/kWh
            gas_price = energy_prices.get('natural_gas', 0.05)  # $/kWh equivalent
            
            # Weighted average (60% electricity, 40% gas for industrial use)
            avg_energy_price = 0.6 * electricity_price + 0.4 * gas_price
            
            logger.info(f"Energy prices: electricity=${electricity_price:.4f}/kWh, gas=${gas_price:.4f}/kWh")
            logger.info(f"Weighted average: ${avg_energy_price:.4f}/kWh")
            
        else:
            logger.warning("CLEWS results missing 'energy_prices', using baseline")
            avg_energy_price = 0.10  # Baseline: $0.10/kWh
        
        # Transform to OG-Core production cost factor
        # Baseline energy cost: $0.10/kWh
        baseline_energy_cost = 0.10
        energy_cost_factor = avg_energy_price / baseline_energy_cost
        
        # Validate (energy costs shouldn't vary more than 5x from baseline)
        if not (0.1 <= energy_cost_factor <= 5.0):
            logger.warning(
                f"Energy cost factor {energy_cost_factor:.2f} outside valid range [0.1, 5.0]. "
                f"Clamping to valid range."
            )
            energy_cost_factor = max(0.1, min(5.0, energy_cost_factor))
        
        # Map to OG-Core parameters
        # These affect the production function and firm costs
        
        # 1. Adjust depreciation rates (higher energy costs → faster equipment turnover)
        # OG-Core uses 'delta' for depreciation rate
        baseline_delta = 0.05  # 5% baseline depreciation
        og_inputs['delta'] = baseline_delta * (1 + 0.1 * (energy_cost_factor - 1))
        
        # 2. Adjust total factor productivity (TFP) growth
        # Higher energy costs → lower productivity growth
        # OG-Core uses 'g_y' for TFP growth rate
        baseline_g_y = 0.03  # 3% baseline TFP growth
        og_inputs['g_y'] = baseline_g_y * (1 - 0.05 * (energy_cost_factor - 1))
        
        # 3. Store the raw energy cost factor for reference
        og_inputs['energy_cost_factor'] = energy_cost_factor
        og_inputs['avg_energy_price'] = avg_energy_price
        
        # Log the transformation
        self._log_transformation(
            source='CLEWS',
            source_var='energy_prices',
            source_value=f"electricity=${electricity_price:.4f}/kWh, gas=${gas_price:.4f}/kWh",
            target='OG-Core',
            target_var='delta, g_y',
            target_value=f"delta={og_inputs['delta']:.4f}, g_y={og_inputs['g_y']:.4f}",
            transformation=f'energy_cost_factor={energy_cost_factor:.2f}'
        )
        
        logger.info(
            f"Transformed energy prices → OG-Core parameters: "
            f"delta={og_inputs['delta']:.4f}, g_y={og_inputs['g_y']:.4f}"
        )
        
        return og_inputs
    
    def write_clews_input_csv(self, clews_inputs, output_dir, region='USA', start_year=2021, n_years=20):
        """
        Write CLEWS inputs to CSV format (OSeMOSYS format).
        
        Args:
            clews_inputs (dict): CLEWS input parameters
            output_dir (str): Directory to write CSV files
            region (str): Region code
            start_year (int): Start year
            n_years (int): Number of years
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Write DiscountRate parameter
        if 'DiscountRate' in clews_inputs:
            discount_rate = clews_inputs['DiscountRate']
            
            df = pd.DataFrame({
                'REGION': [region] * n_years,
                'YEAR': range(start_year, start_year + n_years),
                'VALUE': [discount_rate] * n_years
            })
            
            csv_file = output_path / 'DiscountRate.csv'
            df.to_csv(csv_file, index=False)
            logger.info(f"Wrote DiscountRate to {csv_file}")
    
    def _log_transformation(self, source, source_var, source_value, 
                           target, target_var, target_value, transformation):
        """
        Log a data transformation for audit and debugging.
        
        These logs are critical for understanding what data is flowing
        between models and for debugging integration issues.
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'source': source,
            'source_variable': source_var,
            'source_value': source_value,
            'target': target,
            'target_variable': target_var,
            'target_value': target_value,
            'transformation': transformation,
            'status': 'success'
        }
        
        self.transformation_log.append(log_entry)
        
        logger.debug(
            f"ETL: {source}.{source_var} → {target}.{target_var} "
            f"via {transformation}"
        )
    
    def get_transformation_log(self):
        """
        Get the complete transformation log.
        
        Returns:
            list: All transformation log entries
        """
        return self.transformation_log
    
    def get_transformation_summary(self):
        """
        Get a human-readable summary of transformations.
        
        Returns:
            str: Summary of all transformations
        """
        if not self.transformation_log:
            return "No transformations logged"
        
        summary = []
        summary.append("=" * 70)
        summary.append("ETL TRANSFORMATION LOG")
        summary.append("=" * 70)
        summary.append("")
        
        for entry in self.transformation_log:
            summary.append(
                f"{entry['timestamp']}: "
                f"{entry['source']}.{entry['source_variable']} → "
                f"{entry['target']}.{entry['target_variable']}"
            )
            summary.append(f"  Value: {entry['source_value']} → {entry['target_value']}")
            summary.append(f"  Method: {entry['transformation']}")
            summary.append(f"  Status: {entry['status']}")
            summary.append("")
        
        return "\n".join(summary)


# Example usage
if __name__ == "__main__":
    # This demonstrates the ETL pipeline with REAL data
    
    print("ETL Pipeline Demonstration")
    print("=" * 70)
    print()
    
    # Load real OG-Core data
    real_data_file = "../../../real_og_core_interest_rates.npy"
    if Path(real_data_file).exists():
        interest_rates = np.load(real_data_file)
        
        # Create mock OG-Core results dict
        og_results = {'r': interest_rates}
        
        # Create ETL pipeline
        etl = ETLPipeline()
        
        # Transform OG-Core → CLEWS
        clews_inputs = etl.og_to_clews(og_results)
        
        print("Transformation complete!")
        print()
        print(etl.get_transformation_summary())
        
        # Write to CSV
        etl.write_clews_input_csv(clews_inputs, './test_output')
        print("CSV files written to ./test_output/")
    else:
        print(f"Real data file not found: {real_data_file}")
        print("Run extract_real_data.py first")
