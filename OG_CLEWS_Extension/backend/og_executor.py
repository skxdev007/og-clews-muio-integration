"""
OG-Core Execution Wrapper

Wraps OG-Core execution for MUIO integration.
Handles parameter configuration, execution, and result extraction.
"""

import os
import pickle
import multiprocessing
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np


class OGExecutor:
    """
    Wrapper for OG-Core execution
    
    Provides a clean interface for running OG-Core from MUIO
    and extracting results.
    """
    
    def __init__(self):
        self.status = 'idle'
        self.last_output_dir = None
        
    def get_status(self) -> Dict[str, Any]:
        """
        Get current execution status
        
        Returns:
            Dictionary with status information
        """
        return {
            'status': self.status,
            'last_output_dir': self.last_output_dir
        }
    
    def run(
        self,
        baseline: bool = True,
        time_path: bool = True,
        og_spec: Optional[Dict[str, Any]] = None,
        output_dir: str = './og_output',
        num_workers: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run OG-Core with specified parameters
        
        Args:
            baseline: Whether this is a baseline run
            time_path: Whether to solve time path (vs steady-state only)
            og_spec: Dictionary of OG-Core parameters to override
            output_dir: Directory to save outputs
            num_workers: Number of parallel workers (default: min(cpu_count, 4))
        
        Returns:
            Dictionary with execution results
        """
        try:
            # Import here to avoid issues if ogcore not installed
            from ogcore.execute import runner
            from ogcore.parameters import Specifications
            from distributed import Client
            
            self.status = 'running'
            
            # Set up workers
            if num_workers is None:
                num_workers = min(multiprocessing.cpu_count(), 4)
            
            client = Client(n_workers=num_workers, threads_per_worker=1)
            
            # Default parameters for faster execution
            default_spec = {
                "frisch": 0.41,
                "start_year": 2021,
                "cit_rate": [[0.21]],
                "debt_ratio_ss": 1.0,
                "initial_guess_r_SS": 0.04,
                "T": 40,  # Fewer time periods for faster execution
                "S": 40,  # Fewer age groups for faster execution
            }
            
            # Merge with user-provided spec
            if og_spec:
                default_spec.update(og_spec)
            
            # Create specifications
            p = Specifications(
                baseline=baseline,
                num_workers=num_workers,
                baseline_dir=output_dir,
                output_base=output_dir,
            )
            
            # Update with parameters
            p.update_specifications(default_spec)
            
            # Run the model
            runner(p, time_path=time_path, client=client)
            
            # Clean up
            client.close()
            
            self.status = 'complete'
            self.last_output_dir = output_dir
            
            return {
                'status': 'success',
                'output_dir': output_dir,
                'parameters': default_spec,
                'message': 'OG-Core execution complete'
            }
            
        except ImportError as e:
            self.status = 'error'
            return {
                'status': 'error',
                'error': 'OG-Core not installed. Run: pip install ogcore',
                'details': str(e)
            }
        except Exception as e:
            self.status = 'error'
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_results(self, output_dir: str = './og_output') -> Dict[str, Any]:
        """
        Extract results from OG-Core output directory
        
        Args:
            output_dir: Directory containing OG-Core outputs
        
        Returns:
            Dictionary with extracted results
        """
        try:
            # Load TPI results
            tpi_file = Path(output_dir) / "TPI" / "TPI_vars.pkl"
            
            if not tpi_file.exists():
                raise FileNotFoundError(f"TPI results not found at: {tpi_file}")
            
            with open(tpi_file, 'rb') as f:
                tpi_results = pickle.load(f)
            
            # Extract key variables
            results = {
                'r': tpi_results.get('r'),  # Interest rates
                'Y': tpi_results.get('Y'),  # GDP
                'K': tpi_results.get('K'),  # Capital
                'L': tpi_results.get('L'),  # Labor
                'w': tpi_results.get('w'),  # Wages
                'C': tpi_results.get('C'),  # Consumption
            }
            
            # Load steady-state results if available
            ss_file = Path(output_dir) / "SS" / "SS_vars.pkl"
            if ss_file.exists():
                with open(ss_file, 'rb') as f:
                    ss_results = pickle.load(f)
                results['ss'] = {
                    'r_ss': ss_results.get('r_ss'),
                    'w_ss': ss_results.get('w_ss'),
                    'K_ss': ss_results.get('K_ss'),
                    'L_ss': ss_results.get('L_ss'),
                    'Y_ss': ss_results.get('Y_ss'),
                }
            
            return results
            
        except Exception as e:
            raise Exception(f"Error extracting results: {str(e)}")
    
    def extract_interest_rates(self, output_dir: str = './og_output') -> np.ndarray:
        """
        Extract just the interest rate array
        
        Args:
            output_dir: Directory containing OG-Core outputs
        
        Returns:
            NumPy array of interest rates over time
        """
        results = self.get_results(output_dir)
        return results['r']
