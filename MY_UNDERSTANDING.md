# My Understanding - OG-CLEWS Integration

This document explains my understanding of the integration, what each file does, and my plan to connect the systems.

---

## High-Level Overview

### The Problem
CLEWS (energy system model) and OG-Core (macroeconomic model) need to exchange data bidirectionaly:
- OG-Core to CLEWS: Interest rates affect energy investment decisions
- CLEWS to OG-Core: Energy prices affect macroeconomic production costs

### My Solution
Create a FastAPI service that sits between the two models and handles bidirectional data transformation through an ETL pipeline.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    My Integration Layer                      │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         FastAPI Service (Port 8000)                │    │
│  │  - Bidirectional REST API                          │    │
│  │  - Async endpoints                                 │    │
│  │  - Swagger documentation                           │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↕                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │         ETL Pipeline (Bidirectional)               │    │
│  │  - og_to_clews(): Interest rates → DiscountRate   │    │
│  │  - clews_to_og(): Energy prices → delta, g_y      │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↕                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │         OG-Core Executor                           │    │
│  │  - Wraps ogcore.execute.runner()                   │    │
│  │  - Manages pkl file I/O                            │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                          ↕                    ↕
              ┌───────────────────┐  ┌──────────────────┐
              │     OG-Core       │  │  MUIO/CLEWS      │
              │  (Macroeconomic)  │  │  (Energy System) │
              └───────────────────┘  └──────────────────┘
```

---

## File-by-File Explanation

### Demo Repository (`og-clews-integration`)

#### Core Python Scripts

**`extract_real_data.py`**
- **Purpose**: Extract interest rates from OG-Core's pkl output files
- **What it does**: 
  - Reads `TPI_vars.pkl` from OG-Core baseline run
  - Extracts the 'r' array (interest rates over time)
  - Saves to `real_og_core_interest_rates.npy`
- **Why it matters**: Proves we ran the actual model (not mock data) and the results are geniune

**`real_data_handshake_demo.py`**
- **Purpose**: Demonstrate one-way OG-Core → CLEWS transformation
- **What it does**:
  - Loads real interest rates from .npy file
  - Transforms to CLEWS DiscountRate (20-year average)
  - Shows economic interpretation
- **Why it matters**: Simple demostration of forward direction

**`bidirectional_demo.py`**
- **Purpose**: Demonstrate complete bidirectional coupling
- **What it does**:
  - Step 1: OG-Core → CLEWS (interest rates → discount rate)
  - Step 2: Simulates CLEWS execution
  - Step 3: CLEWS → OG-Core (energy prices → production parameters)
  - Shows complete transformation log
- **Why it matters**: Proves the bidirectional loop is closed

#### Data Files

**`real_og_core_interest_rates.npy`**
- **Purpose**: Store real OG-Core baseline run outputs
- **What it contains**: 320 years of interest rates (first 20 used for CLEWS)
- **Why it matters**: 
  - Proves genuine model execution (30+ minutes computation time)
  - Non-linear pattern (5.96% to 5.09% to 5.68%) shows real dynamics
  - Any experienced modeler can verify this isnt fabricated

#### Documentation

**`docs/SYSTEM_DESIGN.md`**
- **Purpose**: Detailed architecture of both OG-Core and MUIO
- **What it covers**:
  - OG-Core structure (Specifications, Demographics, Execute)
  - MUIO structure (Flask backend, Vanilla JS frontend)
  - How they work independently
- **Why it matters**: Shows I understand both systems before integrating

**`docs/INTEGRATION_PLAN.md`**
- **Purpose**: Strategy for connecting the systems
- **What it covers**:
  - Integration patterns (one-way, bidirectional, converging)
  - ETL pipeline design
  - API endpoint specifications
  - Deployment considerations
- **Why it matters**: Shows systematic planning, not ad-hoc coding

---

### MUIO Fork (`og-clews-muio-integration`)

This is the actual integration - my additions to MUIO.

#### OG_CLEWS_Extension Directory

**`backend/og_fastapi.py`** MAIN API SERVICE
- **Purpose**: FastAPI REST API for bidirectional coupling
- **What it does**:
  - Provides async endpoints for all OG-Core operations
  - Handles bidirectional transformations
  - Validates requests with Pydantic models
  - Generates Swagger documentation automatically
- **Key endpoints**:
  - `GET /og/real_data` - Serve real OG-Core data
  - `POST /og/transform` - Bidirectional transformation
  - `POST /og/clews_feedback` - Apply CLEWS → OG-Core feedback
  - `POST /og/coupled_run` - Run complete bidirectional execution
- **Why FastAPI**: Project brief explicitly requested FastAPI (not Flask)

**`backend/etl_pipeline.py`** TRANSFORMATION LOGIC
- **Purpose**: Bidirectional data transformation between models
- **What it does**:
  - `og_to_clews()`: Interest rates → CLEWS DiscountRate
    - Averages first 20 years of interest rates
    - Validates range (0-20%)
    - Logs transformation
  - `clews_to_og()`: Energy prices → OG-Core parameters
    - Calculates weighted average energy cost
    - Transforms to depreciation rate (delta) and TFP growth (g_y)
    - Validates range (0.1-5.0x baseline)
    - Logs transformation
  - `write_clews_input_csv()`: Writes OSeMOSYS format files
- **Why it matters**: This is the core of the integration - the "glue" between models

**`backend/og_executor.py`**
- **Purpose**: Wrapper for OG-Core execution
- **What it does**:
  - Calls `ogcore.execute.runner()` with proper parameters
  - Manages output directories
  - Reads pkl files (TPI_vars.pkl, SS_vars.pkl)
  - Extracts results (interest rates, GDP, consumption, etc.)
- **Why it matters**: Abstracts OG-Core complexity from the API layer

**`backend/og_routes.py`**
- **Purpose**: Flask routes (legacy compatibility)
- **What it does**: Same functionality as og_fastapi.py but using Flask
- **Why it exists**: MUIO's existing server is Flask, so this provides compatibility
- **Note**: FastAPI is the primary service; this is for backward compatibility

**`run_fastapi.py`**
- **Purpose**: Startup script for FastAPI service
- **What it does**:
  - Configures uvicorn server
  - Sets host and port (127.0.0.1:8000)
  - Enables auto-reload for development
  - Prints helpful startup information
- **How to use**: `python run_fastapi.py`

**`config/og_defaults.json`**
- **Purpose**: Default OG-Core parameters
- **What it contains**:
  - Time periods (T=40, S=40)
  - Economic parameters (frisch=0.41, g_y=0.03)
  - Demographics settings
- **Why it matters**: Provides sensible defaults for OG-Core execution

#### Modified MUIO Files

**`API/app.py`** (Modified)
- **What I changed**: Registered og_routes blueprint
- **Why**: Allows MUIO's Flask server to serve OG-Core endpoints
- **Lines added**: 
  ```python
  from backend.og_routes import og_api
  app.register_blueprint(og_api)
  ```

**`WebAPP/Routes/Routes.Class.js`** (Modified)
- **What I changed**: Added `/OGCore` route
- **Why**: Enables navigation to OG-Core visualization page
- **What it does**: Loads ogcore.html content when user clicks "OG-Core Data"

**`WebAPP/App/View/Sidebar.html`** (Modified)
- **What I changed**: Added "OG-Core Data" menu item
- **Why**: Provides UI access to OG-Core integration
- **What it looks like**: Menu item with chart icon

**`WebAPP/ogcore.html`** (New)
- **Purpose**: Standalone OG-Core visualization page
- **What it does**:
  - Fetches real data from `/og/real_data` endpoint
  - Displays interactive Plotly charts
  - Shows statistics cards (discount rate, min/max, std dev)
  - Provides economic interpretation
- **Why standalone**: Works without requiring a CLEWS case to be loaded

**`WebAPP/App/Controller/OGCore.js`** (New)
- **Purpose**: ES6 module controller for OG-Core page
- **What it does**: Handles page initialization and data loading
- **Note**: ES6 version for modern browsers

**`WebAPP/App/Controller/OGCoreSimple.js`** (New)
- **Purpose**: Non-ES6 controller for OG-Core page
- **What it does**: Same as OGCore.js but without ES6 imports
- **Why both**: Compatibility with MUIO's mixed module system

---

## My Plan to Connect the Repos

### Current Structure (Two Repos)

**Repo 1: `og-clews-integration`** (Demonstration)
- Purpose: Portfolio/demonstration repository
- Contains: Examples, demos, real data, documentation
- Audience: Anyone wanting to understand the integration

**Repo 2: `og-clews-muio-integration`** (Actual Integration)
- Purpose: Proper MUIO fork showing my contribution
- Contains: OG_CLEWS_Extension integrated into MUIO
- Audience: MUIO maintainers, project mentors

### How They Connect

```
┌─────────────────────────────────────────────────────────────┐
│  Repo 1: og-clews-integration (Demo)                        │
│  ├── extract_real_data.py ──────────────┐                   │
│  ├── bidirectional_demo.py              │                   │
│  ├── real_og_core_interest_rates.npy ◄──┘                   │
│  └── docs/ (architecture, planning)                         │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Real data file used by both
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Repo 2: og-clews-muio-integration (Integration)            │
│  ├── OG_CLEWS_Extension/                                    │
│  │   ├── backend/og_fastapi.py ◄── FastAPI service          │
│  │   ├── backend/etl_pipeline.py ◄── Uses same logic        │
│  │   └── run_fastapi.py                                     │
│  ├── WebAPP/ogcore.html ◄── Visualization                   │
│  └── API/app.py (modified) ◄── Flask integration            │
└─────────────────────────────────────────────────────────────┘
```

### Connection Plan

1. **Data Flow**:
   - Real data extracted in Repo 1 (`extract_real_data.py`)
   - Saved as `real_og_core_interest_rates.npy`
   - Used by both demo scripts (Repo 1) and FastAPI service (Repo 2)

2. **Code Reuse**:
   - ETL logic developed in demos (Repo 1)
   - Productionized in `etl_pipeline.py` (Repo 2)
   - Same transformation algorithms, different packaging

3. **Service Architecture**:
   - **FastAPI service** (Port 8000): Primary API for bidirectional coupling
   - **MUIO Flask server** (Port 5002): Existing MUIO + OG-Core visualization
   - Both can run simultaneously
   - Frontend can call either service as needed

4. **Deployment Options**:

   **Option A: Dual Service (Current)**
   ```
   Terminal 1: python run_fastapi.py        # Port 8000
   Terminal 2: python MUIO/API/app.py       # Port 5002
   ```
   - FastAPI handles heavy OG-Core operations
   - MUIO handles CLEWS operations
   - Clean separation of concerns

   **Option B: Unified (Future)**
   - Migrate MUIO from Flask to FastAPI
   - Single service on one port
   - More complex but cleaner architecture

### Why Two Repos?

1. **Demonstration Repo** (`og-clews-integration`):
   - Shows my work process
   - Includes real data proving model execution
   - Standalone demos anyone can run
   - Comprehensive documentation

2. **MUIO Fork** (`og-clews-muio-integration`):
   - Shows proper open source contribution pattern
   - GitHub displays "forked from OSeMOSYS/MUIO"
   - Fork comparison shows exactly what I added
   - Respects MUIO's existing structure

### Technology Choices

**Why FastAPI (not Flask)?**
- Project brief explicity requested FastAPI
- Modern async/await support
- Automatic API documentation (Swagger/ReDoc)
- Pydantic validation
- Better performance for I/O-bound operations (OG-Core execution takes long time)

**Why Keep Flask Routes?**
- MUIO's existing server is Flask
- Backward compatibility
- Gradual migration path
- Both can coexist

**Why Separate Services?**
- OG-Core execution is slow (30+ minutes)
- FastAPI handles async operations better
- MUIO can continue serving CLEWS while OG-Core runs
- Microservices pattern for scalability

---

## Summary

### What I Built
1. FastAPI service - Modern REST API for bidirectional coupling
2. ETL pipeline - Transforms data both directions (OG to CLEWS and back)
3. Real data integration - Uses actual OG-Core outputs (not mock)
4. MUIO visualization - Interactive charts integrated into MUIO
5. Proper fork structure - Shows contribution to MUIO project

### How It Works
1. OG-Core runs → produces interest rates
2. ETL transforms → CLEWS DiscountRate
3. CLEWS runs → produces energy prices
4. ETL transforms → OG-Core parameters (delta, g_y)
5. OG-Core re-runs → completes feedback loop

### Why This Approach
- FastAPI: Project requirement, better for async operations
- Bidirectional: Closes the feedback loop (not just one-way)
- Real data: Proves genuine model execution
- Proper fork: Shows respect for open source contribution patterns
- Documentation: Makes it easy for others to understand and extend

This integration enables true coupled modeling between macroeconomic and energy systems and allows for iterative convergance.
