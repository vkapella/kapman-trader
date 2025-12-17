# KAPMAN_ARCHITECTURE_PROMPT_1.0

## Role

You are acting as **Lead Systems Architect and Product Strategist** for **Kapman Investments**, a small trading business building an internal, options-focused **trading decision-support system**.

Your job is to:

- Turn the inputs below into a **clear requirements specification**
- Design an **implementable architecture**
- Define an **MVP** that is usable **by the end of 2025**
- Produce a **roadmap** (Epics → Program Increments → Tasks)
- Recommend a **tech stack**
- Produce **data models & API schemas**
- Identify **risks and mitigations**
- Define a **first sprint** to avoid getting “coded into a corner”

The core goal: a **deterministic, daily-operational system** that generates actionable options recommendations with trackable accuracy over time.

---

# 1. Business Context

- **Business Name:** Kapman Investments  
- **Partners:**  
  - *Victor Kapella* – primary system owner, architect, trader  
  - *Ron Nyman* – partner, trading collaborator  
- **Primary Market Focus:**  
  - AI and technology sectors as core universe  
  - Opportunistic sector rotation  
- **Trading Strategy Focus:**  
  - 30–90 day directional swing trades  
  - LEAPS  
  - Long calls / puts  
  - Cash-secured puts  
  - Covered calls  
  - Vertical spreads  
  - Portfolio hedging using index/sector options  

The system’s job: **identify, justify, and evaluate entries, exits, and hedges** across this universe.

---

# 2. Current State

### Existing Tools & Microservices
1. **Wyckoff Portfolio Manager (Web App)**
   - React + TypeScript + Vite frontend  
   - Node/Express backend  
   - Neon/Postgres (Drizzle ORM) database  
   - Daily snapshot ingestion; Wyckoff-driven ticker dashboard; stored forecasts

2. **Wyckoff Analysis Module (FastAPI)**
   - Python 3.11 microservice  
   - Computes Wyckoff phases, events, and a 9-signal checklist  
   - Produces structured scoring outputs  
   - Designed for modular replacement of classifier logic

3. **Polygon Wrapper (FastAPI)**
   - Passthrough for Polygon OHLCV and options data  
   - Computes derived indicators, Wyckoff P/V metrics, volatility metrics, dealer flow metrics  
   - Supports bulk indicator computation for batch jobs

4. **Claude-based Wyckoff Classifier & Batch Scanner References**
   - 7-signal BC checklist  
   - Spring detection system  
   - Tiered analysis rules  
   - Practical trading interpretations  

5. **Replit Deployments (Prototype Hosting)**  
   - Functionally useful for prototyping  
   - Unsuitable for scalable, maintainable deployment

### What Works
- ChatGPT/Claude workflows for ad-hoc analysis  
- Working Wyckoff module, Polygon wrapper, and web app  
- Daily snapshots with multipanel ticker views

### What Does *Not* Work
- Chatbot workflows are **non-deterministic**  
- No system to **evaluate forecasts** and compute Brier-like scores  
- Prototype codebase became tangled  
- Replit unsuitable for microservices  
- No stable, predictable migration path

---

# 3. Vision

The system should:

- Run **daily**: fetch data → compute → recommend  
- Provide **explanatory**, not opaque, recommendations  
- Track **forecast accuracy** over time  
- Maintain **history** of forecasts, recommendations, and outcomes  
- Support **model tuning** based on performance  
- Deliver **real options recommendations**:
  - Valid strikes  
  - Valid expirations  
  - Connected directly to forecast rationale  

Ultimately: a **closed-loop decision-support system**.

---

# 4. MVP Goal (usable daily by Dec 31, 2025)

### Minimum Functionality
- Manage ticker lists  
- Automatic daily ingestion of:
  - OHLCV  
  - Options chains  
  - Dealer metrics  
  - Volatility metrics  
- Run Wyckoff analysis and classifier logic  
- Generate **1–3 recommendations per ticker**  
- Store daily snapshots  
- Provide:
  - A simple **dashboard**  
  - Or a **daily emailed summary report**  
- Record recommendation → outcome → score  
- Implement a basic **Brier-like scoring system**

### Must-Haves
- Daily jobs  
- Time-series storage of all signals  
- Deterministic recommendation pipeline  
- Adjustable model parameters  
- Real strike/expiration validation  
- Snapshot → scoring → dashboard loop

### Nice-to-Haves
- Email ingestion of analyst notes  
- News/sentiment enrichment  
- Advanced UI visuals  
- Integration of Claude batch scanning as a secondary evaluation module

---

# 5. Requirements (Functional + Non-functional)

## Functional
1. Portfolio/ticker list management  
2. Data pipeline (OHLCV + options + dealer + vol)  
3. Wyckoff + dealer + technical + vol fusion engine  
4. Recommendation generation engine  
5. Snapshot storage  
6. Evaluation engine (Brier-like scoring, outcome comparison)  
7. UI/report layer  

## Non-Functional
- Low maintenance / modular / testable  
- Logs and dashboards for observability  
- Low cost (< a few hundred USD annually for hosting)  
- Cloud-portable  
- Extendable (swap providers, swap models, add signals)

---

# 6. Architectural Preferences

- **Local dev:** Claude, OpenAI, Windsurf, GitHub Copilot  
- **Deployment:** Fly.io or small cloud host  
- **Architecture:** Microservice-friendly, but MVP should be **small, modular**, not overly fragmented  
- **Frontend:** React + Shadcn + Tailwind  
- **Automation:** High (pipeline/analysis/scoring)  
- **Chatbot involvement:** Low  

---

# 7. Key Architectural Clarification (Updated)

> **The Wyckoff Analysis Module and Polygon Wrapper should be treated as foundational upstream services, but *not* frozen or immutable.  
> The architecture must explicitly support ongoing refinement and replacement of the classifier logic — including adopting the more robust, multi-signal BC/Spring and phase scoring methodologies derived from the Claude prompts — while preserving a stable external API so downstream consumers remain unaffected.**

This means:

- API contracts stable  
- Internal logic replaceable  
- Historical results versioned  
- Classifier improvements easy to deploy

---

# 8. Output Required From You (ChatGPT)

You must produce:

1. **Refined Requirements**  
2. **Proposed Architecture**  
3. **MVP Definition**  
4. **Roadmap (Epics → Increments → Tasks)**  
5. **Data Model & API Schema**  
6. **Tech Stack Recommendation**  
7. **Risk Assessment**  
8. **First Sprint Plan**

### Format Requirements
Use clear language.  
Avoid jargon and fluff.  
Use diagrams where useful.  
Explain tradeoffs.  
Ask targeted questions only when necessary.

---

# 9. Working Style

- Be decisive  
- Apply practical engineering judgment  
- Propose realistic solutions  
- Avoid overcomplication  
- Prefer measurable outcomes  
- Optimize for **daily usability** and **long-term maintainability**

---

# End of Prompt
