# Wyckoff Benchmark System v2.0 - Design Proposal

**Date:** December 28, 2025  
**Purpose:** Refactor the benchmark system for iterative algorithm development  
**Target:** Clean, modular, flexible architecture supporting detection and sequencing experiments

---

## 1. EXECUTIVE SUMMARY

### Current State Analysis

| Aspect | Original (`wyckoff_bench`) | Expanded (`wyckoff_algo`) |
|--------|---------------------------|---------------------------|
| **Strengths** | Clean separation of concerns, pluggable implementations, YAML config, good evaluator | Handles large universes, database integration, coverage reports |
| **Weaknesses** | Hardcoded paths (`research.wyckoff_bench`), limited to comparing implementations | Sprawling structure, brittle path manipulation, duplicated code, experiments lack standardization |
| **Scale** | 20 symbols, 105 symbols | 8,445 symbols |

### Key Problems to Solve

1. **Hardcoded Namespaces** - `sys.path.insert()` everywhere, `research.wyckoff_bench.*` imports
2. **Brittle Path Resolution** - `Path(__file__).resolve().parents[5]` style navigation
3. **Duplicated Code** - TA precomputation in 3 places, loader logic repeated
4. **No Standardized Experiment Protocol** - Each experiment has its own `run.py`, `filter.py` pattern
5. **Mixed Concerns** - Detection, filtering, sequencing, evaluation all intertwined
6. **Missing Experiment Metadata** - Hard to compare across experiment runs

### Proposed Solution

A **three-layer architecture** that cleanly separates:
1. **Detection Layer** - Wyckoff event detection algorithms (pluggable)
2. **Sequence Layer** - Event sequence analysis and filtering (pluggable)  
3. **Evaluation Layer** - Statistical analysis and reporting (standardized)

With a **YAML-driven experiment runner** that allows rapid iteration with minimal code changes.

---

## 2. PROPOSED ARCHITECTURE

```
wyckoff_bench_v2/
├── README.md
├── pyproject.toml                    # Package definition
├── config/
│   ├── defaults.yaml                 # Global defaults
│   ├── detectors/                    # Detector configurations
│   │   ├── baseline_structural.yaml
│   │   └── chatgpt_core.yaml
│   ├── sequencers/                   # Sequencer configurations
│   │   ├── ar_to_sos.yaml
│   │   └── spring_to_markup.yaml
│   └── experiments/                  # Complete experiment configs
│       ├── baseline_universe.yaml
│       └── spring_sos_entry.yaml
├── src/
│   ├── __init__.py
│   ├── core/                         # Core abstractions
│   │   ├── __init__.py
│   │   ├── contract.py               # EventCode, WyckoffSignal, protocols
│   │   ├── config.py                 # Configuration loader/validator
│   │   └── registry.py               # Plugin discovery
│   ├── data/                         # Data access layer
│   │   ├── __init__.py
│   │   ├── loader_pg.py              # PostgreSQL loader
│   │   ├── loader_parquet.py         # Parquet file loader
│   │   └── ta_enricher.py            # Technical analysis (computed once)
│   ├── detectors/                    # Detection algorithms (PLUGGABLE)
│   │   ├── __init__.py
│   │   ├── base.py                   # BaseDetector protocol
│   │   ├── structural_v1.py          # Current baseline
│   │   ├── chatgpt_core.py           # ChatGPT-derived
│   │   └── custom/                   # User-defined detectors
│   ├── sequencers/                   # Sequence analyzers (PLUGGABLE)
│   │   ├── __init__.py
│   │   ├── base.py                   # BaseSequencer protocol
│   │   ├── identity.py               # Pass-through (baseline)
│   │   ├── ar_to_sos.py              # AR→SOS sequence
│   │   └── spring_to_markup.py       # SPRING→TEST→SOS
│   ├── evaluator/                    # Statistical evaluation
│   │   ├── __init__.py
│   │   ├── forward_returns.py        # Return calculations
│   │   ├── metrics.py                # Brier, win rate, MAE/MFE
│   │   └── reports.py                # Output formatters
│   └── runner/                       # Experiment orchestration
│       ├── __init__.py
│       ├── experiment.py             # Single experiment runner
│       ├── batch.py                  # Multi-experiment runner
│       └── cli.py                    # Command-line interface
├── outputs/                          # All outputs here
│   ├── raw/                          # Raw detection outputs
│   ├── experiments/                  # Experiment results
│   └── reports/                      # Aggregate reports
├── watchlists/                       # Symbol lists
│   ├── ai_stocks_140.txt
│   ├── sp500.txt
│   └── full_universe.txt
└── tests/
    ├── conftest.py
    ├── test_detectors.py
    ├── test_sequencers.py
    └── test_evaluator.py
```

---

## 3. CORE ABSTRACTIONS

### 3.1 Contract Module (`src/core/contract.py`)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol, Dict, List, Any, Optional
import pandas as pd

class EventCode(str, Enum):
    SC = "SC"       # Selling Climax
    AR = "AR"       # Automatic Rally
    ST = "ST"       # Secondary Test
    SPRING = "SPRING"
    TEST = "TEST"
    SOS = "SOS"     # Sign of Strength
    BC = "BC"       # Buying Climax
    SOW = "SOW"     # Sign of Weakness
    UT = "UT"       # Upthrust

class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    CONTEXT = "CONTEXT"

class Role(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    CONTEXT = "CONTEXT"

@dataclass
class WyckoffEvent:
    """Single detected Wyckoff event."""
    symbol: str
    time: datetime
    event: EventCode
    direction: Direction
    role: Role
    confidence: float = 1.0
    bar_index: Optional[int] = None
    debug: Dict[str, Any] = field(default_factory=dict)

@dataclass 
class EventSequence:
    """A sequence of events detected for a symbol."""
    symbol: str
    events: List[WyckoffEvent]
    sequence_type: str  # e.g., "AR_TO_SOS", "SPRING_TO_MARKUP"
    start_time: datetime
    end_time: datetime
    entry_event: Optional[WyckoffEvent] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

# PROTOCOLS - Pluggable interfaces

class Detector(Protocol):
    """Protocol for Wyckoff event detectors."""
    name: str
    version: str
    supported_events: List[EventCode]
    
    def detect(self, df: pd.DataFrame, config: Dict[str, Any]) -> List[WyckoffEvent]:
        """Detect events in OHLCV data."""
        ...
    
    def get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        ...

class Sequencer(Protocol):
    """Protocol for event sequence analyzers."""
    name: str
    version: str
    sequence_pattern: str  # e.g., "AR->SOS", "SPRING->TEST->SOS"
    
    def analyze(
        self, 
        events: List[WyckoffEvent], 
        ohlcv: pd.DataFrame,
        config: Dict[str, Any]
    ) -> List[EventSequence]:
        """Analyze events for sequences."""
        ...
    
    def get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        ...

class Evaluator(Protocol):
    """Protocol for statistical evaluation."""
    name: str
    horizons: List[int]
    
    def evaluate(
        self,
        sequences: List[EventSequence],
        ohlcv_by_symbol: Dict[str, pd.DataFrame],
        config: Dict[str, Any]
    ) -> pd.DataFrame:
        """Evaluate sequences and return metrics."""
        ...
```

### 3.2 Configuration Schema (`config/experiments/example.yaml`)

```yaml
# Experiment configuration
experiment:
  id: "spring_sos_entry_v2"
  description: "Test SPRING→SOS entry sequence with tightened thresholds"
  created: "2025-12-28"
  
# Data source configuration
data:
  source: "postgres"  # or "parquet"
  database_url: "${DATABASE_URL}"  # Environment variable
  watchlist: "watchlists/ai_stocks_140.txt"
  lookback_days: 730
  batch_size: 250

# Detector configuration
detector:
  name: "structural_v1"
  config:
    sc_vol_z: 2.0
    sc_tr_z: 2.0
    bc_vol_z: 2.0
    bc_tr_z: 2.0
    spring_vol_z: 0.8
    spring_break_pct: 0.01
    # ... all configurable thresholds

# Sequencer configuration  
sequencer:
  name: "spring_to_sos"
  config:
    max_gap_days: 20
    require_test: false
    min_confidence: 0.6

# Evaluator configuration
evaluator:
  horizons: [5, 10, 20, 40]
  min_samples: 5
  metrics:
    - forward_return
    - win_rate
    - mae
    - mfe
    - brier_score

# Output configuration
output:
  dir: "outputs/experiments/${experiment.id}"
  formats:
    - parquet
    - csv
  reports:
    - summary
    - coverage
    - timeline
```

---

## 4. KEY COMPONENTS

### 4.1 Detector Implementation Pattern

```python
# src/detectors/structural_v1.py

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

from ..core.contract import (
    Detector, WyckoffEvent, EventCode, Direction, Role
)

@dataclass
class StructuralV1Config:
    """Configuration for structural detector v1."""
    lookback_trend: int = 20
    vol_lookback: int = 40
    range_lookback: int = 40
    min_bars: int = 20
    
    # Climax thresholds
    sc_tr_z: float = 2.0
    sc_vol_z: float = 2.0
    bc_tr_z: float = 2.0
    bc_vol_z: float = 2.0
    
    # Spring/UT thresholds
    spring_vol_z: float = 0.8
    spring_break_pct: float = 0.01
    spring_reentry_bars: int = 2
    spring_close_pos: float = 0.6
    
    # SOW/SOS thresholds
    sos_tr_z: float = 1.5
    sow_tr_z: float = 1.5
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StructuralV1Config":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class StructuralV1Detector:
    """Structural Wyckoff detector v1 - baseline implementation."""
    
    name = "structural_v1"
    version = "1.0.0"
    supported_events = [
        EventCode.SC, EventCode.AR, EventCode.BC, EventCode.SOW,
        EventCode.SOS, EventCode.SPRING, EventCode.UT
    ]
    
    def __init__(self, config: Optional[StructuralV1Config] = None):
        self.config = config or StructuralV1Config()
    
    def detect(self, df: pd.DataFrame, config: Dict[str, Any]) -> List[WyckoffEvent]:
        """Detect Wyckoff events in OHLCV data."""
        # Merge runtime config with defaults
        cfg = StructuralV1Config.from_dict({**self.config.__dict__, **config})
        
        events: List[WyckoffEvent] = []
        df = self._prepare(df)
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"
        
        # Detection logic (from structural.py)
        # ... (your existing detection code)
        
        return events
    
    def get_default_config(self) -> Dict[str, Any]:
        return self.config.__dict__
    
    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare OHLCV data with derived metrics."""
        df = df.copy()
        # ... normalization and z-score computation
        return df
```

### 4.2 Sequencer Implementation Pattern

```python
# src/sequencers/ar_to_sos.py

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import timedelta
import pandas as pd

from ..core.contract import (
    Sequencer, WyckoffEvent, EventSequence, EventCode, Direction, Role
)

@dataclass
class ARtoSOSConfig:
    """Configuration for AR→SOS sequence detector."""
    max_gap_days: int = 20
    require_st: bool = False
    min_confidence: float = 0.5

class ARtoSOSSequencer:
    """Detect AR→SOS entry sequences."""
    
    name = "ar_to_sos"
    version = "1.0.0"
    sequence_pattern = "AR->SOS"
    
    def __init__(self, config: Optional[ARtoSOSConfig] = None):
        self.config = config or ARtoSOSConfig()
    
    def analyze(
        self,
        events: List[WyckoffEvent],
        ohlcv: pd.DataFrame,
        config: Dict[str, Any]
    ) -> List[EventSequence]:
        """Find AR→SOS sequences."""
        cfg = ARtoSOSConfig(**{**self.config.__dict__, **config})
        
        sequences: List[EventSequence] = []
        
        # Group events by symbol
        by_symbol: Dict[str, List[WyckoffEvent]] = {}
        for e in events:
            by_symbol.setdefault(e.symbol, []).append(e)
        
        for symbol, sym_events in by_symbol.items():
            # Sort by time
            sym_events = sorted(sym_events, key=lambda e: e.time)
            
            # Find AR events
            ar_events = [e for e in sym_events if e.event == EventCode.AR]
            
            for ar in ar_events:
                # Look for SOS within max_gap_days
                sos_candidates = [
                    e for e in sym_events
                    if e.event == EventCode.SOS
                    and e.time > ar.time
                    and (e.time - ar.time).days <= cfg.max_gap_days
                ]
                
                if sos_candidates:
                    sos = sos_candidates[0]  # First SOS after AR
                    
                    sequences.append(EventSequence(
                        symbol=symbol,
                        events=[ar, sos],
                        sequence_type=self.sequence_pattern,
                        start_time=ar.time,
                        end_time=sos.time,
                        entry_event=ar,  # Entry on AR detection
                        confidence=(ar.confidence + sos.confidence) / 2,
                        metadata={"gap_days": (sos.time - ar.time).days}
                    ))
        
        return sequences
    
    def get_default_config(self) -> Dict[str, Any]:
        return self.config.__dict__
```

### 4.3 Experiment Runner

```python
# src/runner/experiment.py

from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import pandas as pd
from datetime import datetime

from ..core.config import load_config, validate_config
from ..core.registry import get_detector, get_sequencer
from ..data.loader_pg import PostgresLoader
from ..data.ta_enricher import enrich_ta
from ..evaluator.metrics import compute_metrics
from ..evaluator.reports import write_reports

class ExperimentRunner:
    """Run a single experiment from configuration."""
    
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        validate_config(self.config)
        
        self.experiment_id = self.config["experiment"]["id"]
        self.output_dir = Path(
            self.config["output"]["dir"].replace(
                "${experiment.id}", self.experiment_id
            )
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run(self) -> Dict[str, Any]:
        """Execute the experiment."""
        start_time = datetime.now()
        
        # 1. Load data
        print(f"[{self.experiment_id}] Loading data...")
        loader = self._get_loader()
        ohlcv_by_symbol = loader.load()
        
        # 2. Enrich with TA indicators
        print(f"[{self.experiment_id}] Computing TA indicators...")
        for sym, df in ohlcv_by_symbol.items():
            ohlcv_by_symbol[sym] = enrich_ta(df)
        
        # 3. Run detector
        print(f"[{self.experiment_id}] Running detector...")
        detector = get_detector(self.config["detector"]["name"])
        all_events = []
        for sym, df in ohlcv_by_symbol.items():
            events = detector.detect(df, self.config["detector"].get("config", {}))
            all_events.extend(events)
        
        # 4. Run sequencer (if configured)
        sequences = all_events  # Default: treat events as sequences
        if "sequencer" in self.config:
            print(f"[{self.experiment_id}] Running sequencer...")
            sequencer = get_sequencer(self.config["sequencer"]["name"])
            sequences = sequencer.analyze(
                all_events,
                pd.concat(ohlcv_by_symbol.values()),
                self.config["sequencer"].get("config", {})
            )
        
        # 5. Evaluate
        print(f"[{self.experiment_id}] Computing metrics...")
        results = compute_metrics(
            sequences,
            ohlcv_by_symbol,
            self.config["evaluator"]
        )
        
        # 6. Write reports
        print(f"[{self.experiment_id}] Writing reports...")
        write_reports(results, self.output_dir, self.config["output"])
        
        # 7. Save experiment metadata
        elapsed = (datetime.now() - start_time).total_seconds()
        metadata = {
            "experiment_id": self.experiment_id,
            "config": self.config,
            "run_time": start_time.isoformat(),
            "elapsed_seconds": elapsed,
            "symbols_processed": len(ohlcv_by_symbol),
            "events_detected": len(all_events),
            "sequences_found": len(sequences) if sequences != all_events else None,
            "output_dir": str(self.output_dir)
        }
        
        with open(self.output_dir / "metadata.yaml", "w") as f:
            yaml.dump(metadata, f)
        
        print(f"[{self.experiment_id}] Complete in {elapsed:.1f}s")
        return metadata
    
    def _get_loader(self):
        """Get data loader based on config."""
        if self.config["data"]["source"] == "postgres":
            return PostgresLoader(
                database_url=self.config["data"]["database_url"],
                watchlist_path=self.config["data"]["watchlist"],
                lookback_days=self.config["data"]["lookback_days"],
                batch_size=self.config["data"].get("batch_size", 250)
            )
        else:
            raise ValueError(f"Unknown data source: {self.config['data']['source']}")
```

---

## 5. WORKFLOW: ITERATIVE ALGORITHM DEVELOPMENT

### Step 1: Establish Baseline

```bash
# Run baseline detection across full universe
python -m wyckoff_bench_v2.cli run config/experiments/baseline_universe.yaml
```

**Output:**
- `outputs/experiments/baseline_universe/events.parquet`
- `outputs/experiments/baseline_universe/coverage.csv`
- `outputs/experiments/baseline_universe/benchmark_results.csv`

### Step 2: Tweak Detection Parameters

Create a new config:
```yaml
# config/experiments/structural_v1_tight.yaml
experiment:
  id: "structural_v1_tight_thresholds"
  description: "Test tighter climax thresholds"

detector:
  name: "structural_v1"
  config:
    sc_vol_z: 2.5  # Increased from 2.0
    sc_tr_z: 2.5   # Increased from 2.0
    bc_vol_z: 2.5
    bc_tr_z: 2.5
```

```bash
python -m wyckoff_bench_v2.cli run config/experiments/structural_v1_tight.yaml
```

### Step 3: Compare Experiments

```bash
python -m wyckoff_bench_v2.cli compare \
    outputs/experiments/baseline_universe \
    outputs/experiments/structural_v1_tight
```

**Output:**
```
Experiment Comparison Report
============================

| Metric                | baseline_universe | structural_v1_tight | Delta    |
|-----------------------|-------------------|---------------------|----------|
| Events Detected       | 24,679            | 18,234              | -26.1%   |
| AR Count              | 4,055             | 3,012               | -25.7%   |
| BC Count              | 6,262             | 4,891               | -21.9%   |
| AR Win Rate (10d)     | 52.3%             | 54.8%               | +2.5%    |
| AR Mean Return (10d)  | 1.82%             | 2.14%               | +0.32%   |
| ...                   | ...               | ...                 | ...      |
```

### Step 4: Test Sequence Patterns

```yaml
# config/experiments/ar_sos_sequence_v1.yaml
experiment:
  id: "ar_sos_sequence_v1"
  description: "Test AR→SOS entry sequence"

sequencer:
  name: "ar_to_sos"
  config:
    max_gap_days: 15
    require_st: false
```

### Step 5: Export for LLM Analysis

```bash
python -m wyckoff_bench_v2.cli export \
    outputs/experiments/baseline_universe \
    --format llm-prompt \
    --output analysis_prompt.md
```

**Output:** A markdown file containing:
- Experiment configuration
- Key statistics
- Sample events with context
- Questions for LLM analysis

---

## 6. LLM INTEGRATION WORKFLOW

### Structured Output for LLM Review

```yaml
# config/exports/llm_analysis.yaml
export:
  format: "llm_prompt"
  include:
    - experiment_summary
    - event_distribution
    - performance_by_event
    - sample_events: 20
    - worst_performers: 10
  questions:
    - "What detection threshold adjustments would improve AR win rate?"
    - "Are there any event patterns that suggest false positives?"
    - "What sequence patterns show the strongest forward returns?"
```

### Sample LLM Prompt Output

```markdown
# Wyckoff Algorithm Analysis Request

## Experiment: baseline_universe (2025-12-28)

### Configuration
- Detector: structural_v1
- Thresholds: SC_VOL_Z=2.0, SC_TR_Z=2.0, ...
- Universe: 8,445 symbols
- Period: 730 days

### Event Distribution
| Event  | Count | Density | Symbols |
|--------|-------|---------|---------|
| AR     | 4,055 | 0.526   | 4,055   |
| BC     | 6,262 | 0.526   | 6,262   |
| ...    | ...   | ...     | ...     |

### Performance by Event (10-day horizon)
| Event  | Count | Win Rate | Mean Return | MAE    |
|--------|-------|----------|-------------|--------|
| AR     | 4,055 | 52.3%    | +1.82%      | -3.1%  |
| ...    | ...   | ...      | ...         | ...    |

### Sample AR Events (with context)
1. **NVDA** - 2024-08-05 - AR detected
   - Prior 5 bars: SC on 2024-08-01, volume spike 2.3x
   - 10-day return: +8.2%
   - Context: Post-earnings selloff recovery

2. ...

### Questions for Analysis
1. What detection threshold adjustments would improve AR win rate?
2. Are there any event patterns that suggest false positives?
3. What sequence patterns show the strongest forward returns?

Please provide specific, actionable recommendations that can be 
implemented as configuration changes in YAML format.
```

---

## 7. MIGRATION PATH

### Phase 1: Core Infrastructure (2-3 days)
- [ ] Create package structure
- [ ] Implement contract module
- [ ] Implement config loader
- [ ] Implement registry

### Phase 2: Data Layer (1-2 days)
- [ ] Migrate PostgresLoader
- [ ] Implement TA enricher (consolidate from 3 locations)
- [ ] Add parquet loader for offline analysis

### Phase 3: Detectors (2-3 days)
- [ ] Port structural_v1 to new interface
- [ ] Port chatgpt_core to new interface
- [ ] Add unit tests

### Phase 4: Sequencers (2-3 days)
- [ ] Implement identity sequencer (baseline)
- [ ] Implement ar_to_sos sequencer
- [ ] Implement spring_to_markup sequencer
- [ ] Add unit tests

### Phase 5: Evaluator (1-2 days)
- [ ] Port forward return calculations
- [ ] Port MAE/MFE calculations
- [ ] Add coverage reports

### Phase 6: CLI & Reports (1-2 days)
- [ ] Implement CLI runner
- [ ] Implement comparison tool
- [ ] Implement LLM export

---

## 8. DECISION POINTS FOR DISCUSSION

### Q1: Detector Configuration Storage
**Option A:** All config in YAML files (current proposal)
**Option B:** Config in database for versioning/tracking
**Recommendation:** Start with YAML, add DB persistence post-MVP

### Q2: Event vs Sequence Evaluation
**Option A:** Always evaluate at sequence level (more complex)
**Option B:** Support both event-level and sequence-level (flexible)
**Recommendation:** Support both - event-level for detector tuning, sequence-level for strategy testing

### Q3: Parallel Processing
**Option A:** Single-threaded (simpler, debugging easier)
**Option B:** Parallel by symbol (faster for large universes)
**Recommendation:** Start single-threaded, add parallelism as optimization

### Q4: State Management
**Option A:** Stateless runs (re-detect every time)
**Option B:** Incremental detection (detect only new bars)
**Recommendation:** Stateless for research, incremental for production pipeline

---

## 9. SUCCESS METRICS

| Metric | Target |
|--------|--------|
| Time to run new experiment | < 5 minutes (config change only) |
| Time to add new detector | < 2 hours (implement interface) |
| Time to add new sequencer | < 2 hours (implement interface) |
| Time to compare experiments | < 1 minute (CLI command) |
| Code duplication | Zero (single source of truth for TA, loading, etc.) |
| Test coverage | > 80% for core modules |

---

## 10. NEXT STEPS

If this proposal looks good, I recommend we proceed in this order:

1. **Review and refine** this design document together
2. **Create the package structure** with stub files
3. **Implement the contract module** (your stable API)
4. **Port structural_v1 detector** as first implementation
5. **Create CLI and run baseline** to validate
6. **Iterate** on sequencers and additional detectors

Would you like me to start implementing Phase 1, or do you have questions/modifications to the design?
