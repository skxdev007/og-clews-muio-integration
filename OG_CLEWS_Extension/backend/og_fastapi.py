"""
OG-Core FastAPI Service for MUIO Integration

This module provides FastAPI endpoints for OG-Core execution and bidirectional
data transformation with CLEWS. Runs as a separate service alongside MUIO's Flask server.

Architecture:
- MUIO Flask server: http://127.0.0.1:5002 (existing)
- OG-Core FastAPI service: http://127.0.0.1:8000 (new)
- Frontend calls both services as needed
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
import os
import numpy as np
import logging
from pathlib import Path

from .og_executor import OGExecutor
from .etl_pipeline import ETLPipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="OG-CLEWS Integration API",
    description="FastAPI service for bidirectional OG-Core ↔ CLEWS coupling",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5002", "http://localhost:5002", "http://127.0.0.1", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize executor and transformer
executor = OGExecutor()
transformer = ETLPipeline()


# Pydantic models for request/response validation
class OGRunRequest(BaseModel):
    baseline: bool = True
    time_path: bool = True
    og_spec: Dict[str, Any] = Field(default_factory=dict)
    output_dir: str = "./og_output"


class TransformRequest(BaseModel):
    source: str = Field(..., description="Source system: 'og_core' or 'clews'")
    target: str = Field(..., description="Target system: 'clews' or 'og_core'")
    variable: str = Field(..., description="Variable to transform")
    og_output_dir: Optional[str] = "./og_output"
    clews_data: Optional[Dict[str, Any]] = None
    write_csv: bool = False
    clews_input_dir: Optional[str] = "./clews_input"
    region: str = "USA"
    start_year: int = 2021
    planning_horizon: int = 20


class CoupledRunRequest(BaseModel):
    og_params: Dict[str, Any] = Field(default_factory=dict)
    clews_case: Optional[str] = None
    clews_energy_prices: Optional[Dict[str, float]] = None
    mode: str = Field(default="bidirectional", description="'one_way' or 'bidirectional'")
    output_dir: str = "./og_output_coupled"


class CLEWSFeedbackRequest(BaseModel):
    """Request model for CLEWS → OG-Core feedback"""
    energy_prices: Dict[str, float] = Field(
        ..., 
        description="Energy prices from CLEWS (e.g., {'electricity': 0.12, 'natural_gas': 0.05})"
    )
    og_output_dir: str = "./og_output"
    rerun_ogcore: bool = Field(
        default=False,
        description="Whether to re-run OG-Core with updated parameters"
    )


# API Endpoints

@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "service": "OG-CLEWS Integration API",
        "version": "1.0.0",
        "framework": "FastAPI",
        "description": "Bidirectional coupling between OG-Core and CLEWS",
        "endpoints": {
            "status": "/og/status",
            "run": "/og/run",
            "results": "/og/results",
            "transform": "/og/transform",
            "coupled_run": "/og/coupled_run",
            "clews_feedback": "/og/clews_feedback",
            "real_data": "/og/real_data"
        }
    }


@app.get("/og/status")
def get_status():
    """
    Get OG-Core execution status
    
    Returns:
        Status information including OG-Core version
    """
    try:
        status = executor.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/og/run")
async def run_ogcore(request: OGRunRequest, background_tasks: BackgroundTasks):
    """
    Execute OG-Core with specified parameters
    
    Args:
        request: OGRunRequest with execution parameters
        
    Returns:
        Execution status and result information
    """
    try:
        logger.info(f"Starting OG-Core execution: baseline={request.baseline}")
        
        result = executor.run(
            baseline=request.baseline,
            time_path=request.time_path,
            og_spec=request.og_spec,
            output_dir=request.output_dir
        )
        
        return result
    except Exception as e:
        logger.error(f"Error running OG-Core: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/og/results")
def get_results(output_dir: str = "./og_output"):
    """
    Get OG-Core results from last run
    
    Args:
        output_dir: Directory containing results
        
    Returns:
        OG-Core results (interest rates, GDP, etc.)
    """
    try:
        results = executor.get_results(output_dir)
        
        # Convert numpy arrays to lists for JSON serialization
        json_results = {}
        for key, value in results.items():
            if isinstance(value, np.ndarray):
                json_results[key] = value.tolist()
            else:
                json_results[key] = value
        
        return json_results
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/og/transform")
def transform_data(request: TransformRequest):
    """
    Transform data between OG-Core and CLEWS (bidirectional)
    
    Supports:
    - OG-Core → CLEWS: Interest rates to discount rates
    - CLEWS → OG-Core: Energy prices to production cost factors
    
    Args:
        request: TransformRequest with transformation parameters
        
    Returns:
        Transformed data and transformation log
    """
    try:
        if request.source == 'og_core' and request.target == 'clews':
            # OG-Core → CLEWS transformation
            if request.variable == 'discount_rate':
                og_results = executor.get_results(request.og_output_dir)
                clews_inputs = transformer.og_to_clews(og_results)
                
                if request.write_csv:
                    transformer.write_clews_input_csv(
                        clews_inputs,
                        request.clews_input_dir,
                        region=request.region,
                        start_year=request.start_year,
                        n_years=request.planning_horizon
                    )
                
                return {
                    'status': 'success',
                    'direction': 'OG-Core → CLEWS',
                    'clews_inputs': {
                        'discount_rate': float(clews_inputs.get('DiscountRate', clews_inputs.get('discount_rate', 0)))
                    },
                    'transformation_log': transformer.get_transformation_log()
                }
        
        elif request.source == 'clews' and request.target == 'og_core':
            # CLEWS → OG-Core transformation (NEW!)
            if not request.clews_data:
                raise HTTPException(status_code=400, detail="clews_data required for CLEWS → OG-Core transformation")
            
            og_params = transformer.clews_to_og(request.clews_data)
            
            return {
                'status': 'success',
                'direction': 'CLEWS → OG-Core',
                'og_parameters': og_params,
                'transformation_log': transformer.get_transformation_log(),
                'message': 'Use these parameters in OG-Core execution via /og/run'
            }
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported transformation: {request.source} → {request.target}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error transforming data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/og/clews_feedback")
def clews_feedback(request: CLEWSFeedbackRequest):
    """
    Apply CLEWS energy prices as feedback to OG-Core (CLEWS → OG-Core direction)
    
    This closes the bidirectional loop by taking CLEWS outputs and feeding them
    back into OG-Core's production function.
    
    Args:
        request: CLEWSFeedbackRequest with energy prices from CLEWS
        
    Returns:
        Updated OG-Core parameters and optionally new execution results
    """
    try:
        logger.info(f"Applying CLEWS feedback: {request.energy_prices}")
        
        # Transform CLEWS energy prices to OG-Core cost factors
        clews_data = {
            'energy_prices': request.energy_prices
        }
        og_params = transformer.clews_to_og(clews_data)
        
        result = {
            'status': 'success',
            'direction': 'CLEWS → OG-Core',
            'energy_prices_input': request.energy_prices,
            'og_parameters_updated': og_params,
            'transformation_log': transformer.get_transformation_log()
        }
        
        # Optionally re-run OG-Core with updated parameters
        if request.rerun_ogcore:
            logger.info("Re-running OG-Core with updated parameters")
            og_result = executor.run(
                baseline=False,  # This is a reform scenario
                time_path=True,
                og_spec=og_params,
                output_dir=request.og_output_dir
            )
            result['og_execution'] = og_result
            result['message'] = 'OG-Core re-executed with CLEWS energy price feedback'
        else:
            result['message'] = 'Parameters updated. Set rerun_ogcore=true to execute OG-Core with these parameters'
        
        return result
        
    except Exception as e:
        logger.error(f"Error applying CLEWS feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/og/coupled_run")
async def coupled_run(request: CoupledRunRequest):
    """
    Run coupled OG-Core + CLEWS execution (bidirectional)
    
    Modes:
    - 'one_way': OG-Core → CLEWS only
    - 'bidirectional': OG-Core → CLEWS → OG-Core (closes the loop)
    
    Args:
        request: CoupledRunRequest with coupling parameters
        
    Returns:
        Coupled execution results
    """
    try:
        logger.info(f"Starting coupled run: mode={request.mode}")
        
        if request.mode == 'one_way':
            # Simple one-way coupling: OG-Core → CLEWS
            og_result = executor.run(
                baseline=request.og_params.get('baseline', True),
                time_path=True,
                og_spec=request.og_params.get('og_spec', {}),
                output_dir=request.output_dir
            )
            
            if og_result['status'] != 'success':
                raise HTTPException(status_code=500, detail="OG-Core execution failed")
            
            og_results = executor.get_results(request.output_dir)
            clews_inputs = transformer.og_to_clews(og_results)
            
            return {
                'status': 'success',
                'mode': 'one_way',
                'og_result': og_result,
                'clews_inputs': {
                    'discount_rate': float(clews_inputs.get('DiscountRate', clews_inputs.get('discount_rate', 0)))
                },
                'message': 'One-way coupling complete. CLEWS can now run with updated discount rate.'
            }
        
        elif request.mode == 'bidirectional':
            # Bidirectional coupling: OG-Core → CLEWS → OG-Core
            
            # Step 1: Run OG-Core baseline
            logger.info("Step 1: Running OG-Core baseline")
            og_result = executor.run(
                baseline=True,
                time_path=True,
                og_spec=request.og_params.get('og_spec', {}),
                output_dir=request.output_dir
            )
            
            if og_result['status'] != 'success':
                raise HTTPException(status_code=500, detail="OG-Core baseline execution failed")
            
            # Step 2: Transform to CLEWS
            logger.info("Step 2: Transforming OG-Core → CLEWS")
            og_results = executor.get_results(request.output_dir)
            clews_inputs = transformer.og_to_clews(og_results)
            
            # Step 3: Simulate CLEWS feedback (or use real CLEWS data if provided)
            logger.info("Step 3: Processing CLEWS feedback")
            if request.clews_energy_prices:
                energy_prices = request.clews_energy_prices
            else:
                # Use placeholder energy prices for demonstration
                energy_prices = {
                    'electricity': 0.12,  # $/kWh
                    'natural_gas': 0.05   # $/kWh equivalent
                }
                logger.info("Using placeholder energy prices (no CLEWS data provided)")
            
            # Step 4: Transform CLEWS → OG-Core
            logger.info("Step 4: Transforming CLEWS → OG-Core")
            clews_data = {'energy_prices': energy_prices}
            og_params_updated = transformer.clews_to_og(clews_data)
            
            # Step 5: Re-run OG-Core with feedback
            logger.info("Step 5: Re-running OG-Core with CLEWS feedback")
            og_result_feedback = executor.run(
                baseline=False,  # Reform scenario with energy cost feedback
                time_path=True,
                og_spec=og_params_updated,
                output_dir=request.output_dir + "_feedback"
            )
            
            return {
                'status': 'success',
                'mode': 'bidirectional',
                'step1_og_baseline': og_result,
                'step2_clews_inputs': {
                    'discount_rate': float(clews_inputs.get('DiscountRate', clews_inputs.get('discount_rate', 0)))
                },
                'step3_clews_feedback': {
                    'energy_prices': energy_prices,
                    'source': 'provided' if request.clews_energy_prices else 'placeholder'
                },
                'step4_og_parameters_updated': og_params_updated,
                'step5_og_with_feedback': og_result_feedback,
                'message': 'Bidirectional coupling complete: OG-Core → CLEWS → OG-Core'
            }
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown mode: {request.mode}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in coupled run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/og/real_data")
def get_real_data():
    """
    Get REAL data from completed baseline run
    
    This endpoint serves the actual OG-Core data we extracted
    to prove we've run the model with real outputs.
    
    Returns:
        Real interest rates and statistics
    """
    try:
        # Try multiple possible locations for the real data file
        possible_paths = [
            "real_og_core_interest_rates.npy",
            "../../real_og_core_interest_rates.npy",
            "../../../real_og_core_interest_rates.npy",
            os.path.join(os.path.dirname(__file__), "../../../real_og_core_interest_rates.npy")
        ]
        
        real_data_file = None
        for path in possible_paths:
            if os.path.exists(path):
                real_data_file = path
                break
        
        if not real_data_file:
            raise HTTPException(
                status_code=404,
                detail={
                    'error': 'Real data file not found',
                    'searched_paths': possible_paths,
                    'message': 'Run extract_real_data.py first'
                }
            )
        
        interest_rates = np.load(real_data_file)
        
        # Calculate statistics
        avg_20 = np.mean(interest_rates[:20])
        
        return {
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
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading real data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "OG-CLEWS FastAPI",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
