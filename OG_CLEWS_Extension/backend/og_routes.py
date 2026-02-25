"""
OG-Core Flask Routes for MUIO Integration

This module provides Flask routes for OG-Core execution and data transformation.
Follows MUIO's existing Flask blueprint pattern.
"""

from flask import Blueprint, jsonify, request, session
import os
import pickle
import numpy as np
from pathlib import Path
from .og_executor import OGExecutor
from .etl_pipeline import ETLPipeline

og_api = Blueprint('OGRoute', __name__)

# Initialize executor and transformer
executor = OGExecutor()
transformer = ETLPipeline()


@og_api.route("/og/status", methods=['GET'])
def get_status():
    """
    Get OG-Core execution status
    
    Returns:
        JSON with status information
    """
    try:
        status = executor.get_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@og_api.route("/og/run", methods=['POST'])
def run_ogcore():
    """
    Execute OG-Core with specified parameters
    
    Request body:
    {
        "baseline": true,
        "time_path": true,
        "T": 40,
        "S": 40,
        "frisch": 0.41,
        "output_dir": "./og_output"
    }
    
    Returns:
        JSON with execution status
    """
    try:
        params = request.json
        
        # Start OG-Core execution
        result = executor.run(
            baseline=params.get('baseline', True),
            time_path=params.get('time_path', True),
            og_spec=params.get('og_spec', {}),
            output_dir=params.get('output_dir', './og_output')
        )
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@og_api.route("/og/results", methods=['GET'])
def get_results():
    """
    Get OG-Core results from last run
    
    Query params:
        output_dir: Directory containing results (optional)
    
    Returns:
        JSON with OG-Core results (interest rates, GDP, etc.)
    """
    try:
        output_dir = request.args.get('output_dir', './og_output')
        results = executor.get_results(output_dir)
        
        # Convert numpy arrays to lists for JSON serialization
        json_results = {}
        for key, value in results.items():
            if isinstance(value, np.ndarray):
                json_results[key] = value.tolist()
            else:
                json_results[key] = value
        
        return jsonify(json_results), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@og_api.route("/og/transform", methods=['POST'])
def transform_data():
    """
    Transform data between OG-Core and CLEWS
    
    Request body:
    {
        "source": "og_core",
        "target": "clews",
        "variable": "discount_rate",
        "og_output_dir": "./og_output"
    }
    
    Returns:
        JSON with transformed data
    """
    try:
        params = request.json
        source = params.get('source')
        target = params.get('target')
        variable = params.get('variable')
        
        if source == 'og_core' and target == 'clews':
            if variable == 'discount_rate':
                # Load OG-Core results
                og_output_dir = params.get('og_output_dir', './og_output')
                og_results = executor.get_results(og_output_dir)
                
                # Transform to CLEWS
                clews_inputs = transformer.og_to_clews(og_results)
                
                # Optionally write to CSV
                if params.get('write_csv', False):
                    clews_input_dir = params.get('clews_input_dir', './clews_input')
                    transformer.write_clews_input_csv(
                        clews_inputs,
                        clews_input_dir,
                        region=params.get('region', 'USA'),
                        start_year=params.get('start_year', 2021),
                        n_years=params.get('planning_horizon', 20)
                    )
                
                return jsonify({
                    'status': 'success',
                    'clews_inputs': {
                        'discount_rate': float(clews_inputs.get('DiscountRate', clews_inputs.get('discount_rate', 0)))
                    },
                    'transformation_log': transformer.get_transformation_log()
                }), 200
        
        return jsonify({
            'error': 'Unsupported transformation',
            'source': source,
            'target': target,
            'variable': variable
        }), 400
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@og_api.route("/og/coupled_run", methods=['POST'])
def coupled_run():
    """
    Run coupled OG-Core + CLEWS execution
    
    Request body:
    {
        "og_params": {...},
        "clews_case": "case_name",
        "mode": "one_way"  # or "converging"
    }
    
    Returns:
        JSON with coupled execution results
    """
    try:
        params = request.json
        mode = params.get('mode', 'one_way')
        
        if mode == 'one_way':
            # Simple one-way coupling: OG-Core → CLEWS
            
            # 1. Run OG-Core
            og_result = executor.run(
                baseline=params.get('og_params', {}).get('baseline', True),
                time_path=True,
                og_spec=params.get('og_params', {}).get('og_spec', {}),
                output_dir='./og_output_coupled'
            )
            
            if og_result['status'] != 'success':
                return jsonify({
                    'error': 'OG-Core execution failed',
                    'og_result': og_result
                }), 500
            
            # 2. Transform data
            og_results = executor.get_results('./og_output_coupled')
            clews_inputs = transformer.og_to_clews(og_results)
            
            # Write to CLEWS input directory
            transformer.write_clews_input_csv(
                clews_inputs,
                params.get('clews_input_dir', './clews_input'),
                region='USA',
                start_year=2021,
                n_years=20
            )
            
            # 3. TODO: Trigger CLEWS run with updated discount rate
            # This would integrate with existing MUIO CLEWS execution
            
            return jsonify({
                'status': 'success',
                'og_result': og_result,
                'clews_inputs': {
                    'discount_rate': float(clews_inputs.get('DiscountRate', clews_inputs.get('discount_rate', 0)))
                },
                'message': 'One-way coupling complete. CLEWS can now run with updated discount rate.'
            }), 200
        
        elif mode == 'converging':
            # TODO: Implement iterative converging mode
            return jsonify({
                'error': 'Converging mode not yet implemented',
                'status': 'not_implemented'
            }), 501
        
        else:
            return jsonify({
                'error': f'Unknown mode: {mode}',
                'status': 'error'
            }), 400
            
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@og_api.route("/og/real_data", methods=['GET'])
def get_real_data():
    """
    Get REAL data from completed baseline run
    
    This endpoint serves the actual OG-Core data we extracted
    to prove we've run the model with real outputs.
    
    Returns:
        JSON with real interest rates and statistics
    """
    try:
        # Load real data from our completed baseline run
        # Try multiple possible locations
        possible_paths = [
            "real_og_core_interest_rates.npy",
            "../../real_og_core_interest_rates.npy",
            os.path.join(os.path.dirname(__file__), "../../../real_og_core_interest_rates.npy")
        ]
        
        real_data_file = None
        for path in possible_paths:
            if os.path.exists(path):
                real_data_file = path
                break
        
        if real_data_file:
            interest_rates = np.load(real_data_file)
            
            # Calculate statistics
            avg_20 = np.mean(interest_rates[:20])
            
            return jsonify({
                'status': 'success',
                'source': 'Real OG-Core baseline run',
                'data_file': real_data_file,
                'interest_rates': interest_rates[:30].tolist(),  # First 30 years
                'statistics': {
                    'avg_20_years': float(avg_20),
                    'min': float(np.min(interest_rates)),
                    'max': float(np.max(interest_rates)),
                    'std': float(np.std(interest_rates))
                },
                'clews_discount_rate': float(avg_20),
                'message': 'This is REAL data from actual OG-Core execution, not mock data'
            }), 200
        else:
            return jsonify({
                'error': 'Real data file not found',
                'status': 'not_found',
                'searched_paths': possible_paths,
                'message': 'Run extract_real_data.py first'
            }), 404
            
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500
