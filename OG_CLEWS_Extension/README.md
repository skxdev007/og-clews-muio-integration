# OG-CLEWS Extension for MUIO

This folder contains the OG-Core integration extension for MUIO.

**Status: MVP Phase - Real Data Integration Complete**

We have successfully:
- ✓ Run OG-Core baseline simulation (30+ minutes)
- ✓ Extracted REAL interest rates from TPI_vars.pkl
- ✓ Built ETL pipeline with real data transformation
- ✓ Demonstrated OG-Core → CLEWS data handshake

## Real Data Available

From completed OG-Core baseline run:
- Interest rates (r): 5.97% → 5.09% → 5.96% (non-linear transition)
- Average discount rate for CLEWS: 5.68%
- GDP (Y), Capital (K), Labor (L), Wages (w)
- Source: `real_og_core_interest_rates.npy`

## Structure

```
OG_CLEWS_Extension/
├── README.md                 # This file
├── backend/
│   ├── __init__.py
│   ├── og_routes.py         # Flask routes for OG-Core (NEW)
│   ├── etl_pipeline.py      # Data transformation (COMPLETE)
│   └── og_executor.py       # OG-Core execution wrapper (NEW)
└── config/
    └── og_defaults.json     # Default OG-Core parameters (NEW)
```

## Integration Approach

This extension **extends** MUIO rather than replacing it:

1. **Backend**: New Flask routes registered alongside existing MUIO routes
2. **Frontend**: New JavaScript module following MUIO's existing patterns
3. **Data**: ETL pipeline transforms data between OG-Core and CLEWS
4. **UI**: New tab in MUIO interface for OG-Core functionality

## Key Features

- Run OG-Core standalone
- Run CLEWS standalone (existing)
- Run coupled mode (OG-Core ↔ CLEWS)
- Run converging mode (iterative until convergence)
- Visualize results from both models
- Compare standalone vs. coupled results

## Installation

See main MUIO installation instructions. This extension is automatically
loaded when MUIO starts.

## Usage

1. Start MUIO: `python API/app.py`
2. Open browser: `http://localhost:5002`
3. Navigate to "OG-Core" tab
4. Configure parameters and run models

## Development

This extension follows MUIO's existing patterns:
- Flask for backend API
- Vanilla JavaScript for frontend
- Wijmo for data grids
- Plotly for charts


## Integration Approach

This extension **extends** MUIO rather than replacing it:

1. **Backend**: New Flask routes registered alongside existing MUIO routes
2. **Data**: ETL pipeline transforms data between OG-Core and CLEWS
3. **Execution Modes**:
   - Standalone OG-Core
   - Standalone CLEWS (existing)
   - Coupled mode (OG-Core → CLEWS)
   - Converging mode (iterative until convergence)

## Key Integration Points

### OG-Core → CLEWS
- **Source**: TPI_vars.pkl → interest rate array (r)
- **Transform**: Average over planning horizon (20 years)
- **Target**: CLEWS DiscountRate parameter
- **Real Data**: 5.68% average from actual OG-Core run

### CLEWS → OG-Core (Future)
- **Source**: CLEWS electricity prices
- **Transform**: Normalize to baseline, calculate cost factor
- **Target**: OG-Core production cost parameters

## API Endpoints

### `/og/status` (GET)
Check OG-Core execution status

### `/og/run` (POST)
Execute OG-Core with parameters
```json
{
  "baseline": true,
  "time_path": true,
  "T": 40,
  "S": 40,
  "frisch": 0.41
}
```

### `/og/results` (GET)
Get OG-Core results (interest rates, GDP, etc.)

### `/og/transform` (POST)
Transform OG-Core outputs to CLEWS inputs
```json
{
  "source": "og_core",
  "target": "clews",
  "variable": "discount_rate"
}
```

### `/og/coupled_run` (POST)
Run coupled OG-Core + CLEWS execution

## Installation

1. Install MUIO dependencies:
```bash
cd MUIO
pip install -r requirements.txt
```

2. Install OG-Core:
```bash
pip install ogcore
```

3. Start MUIO:
```bash
python API/app.py
```

4. Access at: `http://localhost:5002`

## Usage Example

```python
# Run OG-Core
response = requests.post('http://localhost:5002/og/run', json={
    'baseline': True,
    'time_path': True,
    'T': 40,
    'S': 40
})

# Get results
results = requests.get('http://localhost:5002/og/results')
interest_rates = results.json()['r']

# Transform for CLEWS
transform = requests.post('http://localhost:5002/og/transform', json={
    'source': 'og_core',
    'target': 'clews',
    'variable': 'discount_rate'
})
clews_discount_rate = transform.json()['value']
```

## Real Data Demonstration

See `../../real_data_handshake_demo.py` for complete demonstration using actual OG-Core outputs.

## Development Status

**Complete:**
- ✓ ETL pipeline with real data
- ✓ OG-Core execution (baseline run)
- ✓ Data extraction and transformation
- ✓ Economic validation

**In Progress:**
- ⏳ Flask routes for OG-Core
- ⏳ OG-Core executor wrapper
- ⏳ MUIO integration

**Planned:**
- ⏳ Frontend UI components
- ⏳ Coupled mode execution
- ⏳ Converging mode with iteration
- ⏳ Results visualization

## References

- OG-Core: https://github.com/PSLmodels/OG-Core
- MUIO: https://github.com/OSeMOSYS/MUIO
- Real Architecture: `../../REAL_ARCHITECTURE.md`
- Progress Summary: `../../PROGRESS_SUMMARY.md`
