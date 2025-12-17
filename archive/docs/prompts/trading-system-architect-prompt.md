Here is the **Markdown (.md) version** of the prompt file — clean, structured, and ready for copy/paste into your repo, notes, or a custom GPT.

---

# 📝 **Trading Decision-Support System – Architecture & Roadmap Prompt Template**

Use this prompt **as-is**, filling in the blanks.
It is designed to allow ChatGPT to act as your **consultant, systems architect, and product strategist** to produce a full requirements document, EPIC roadmap, and MVP plan.

---

## **1. Business Context**

* **Business name (if any):Kapman Investments
* **Team members and roles:Victor Kapella, Partner; Ron Nyman, Partner
* **Target users (just me / partner / external traders):Just Me
* **Primary market focus (options / equities / AI stocks / swing trades / etc.): Focus on the AI stocks and Technology Sectors.   However, dabble in sectors that rotate into prominence..  Focusing on monetizing momentum and directiion through Options Trading: Swing Trades over 30-90 days, Long Calls/Puts, Short Puts, Covered Calls, Spreads.  Smart portfolio protection with Market/Sector Hedging.

---

## **2. Current State**

* **Brief summary of what I’ve already built: ChatGPT 5.1 Custom GPT with Action integration with data sources (Schwab, Polygon) and custom Wyckoff classifer module to perform Wyckoff analysis.   Claude Project with MCP integration to Polygon to perfom Wyckoff Analysis.   kapman-portfolio-manager to keep portfolio lists, pull data and send payloads to OpenAi for interpretive analysis and then store it all in a dabase.
* **What works today: ChatGPT and Claude chatbot driven workflow using OpenAI Actions within Custom GPTs and MCP server interaction within Claude Projects are easy to use   kapman-portfolio-manager is demonstrating the feasibily of using AI to write code and build a system.
* **What does *not* work / main pain points: The chatbot driven approach are difficult to get detirministic results.   Also, no system to capture computations, recommendations and score agaiinst reality. The development approach with kapman-portfolio-manager wasn't well planned out leading to a lot of code, database records and code that is probably too jangy to grow.  The Replit tool does not deal well with a complex, layered application approach.   Cannot see a clear migraton
* **Technical stack so far (Python, Replit, GitHub, APIs used, DBs, etc.): Developed apps/microservices using Replit, assisted with ChatGPT and Claude.   Using Polygon as the main source of stock and options data.  Schwab is available but unreliable.  See attached README files for more information about whats been built so far.

---

## **3. Vision**

* **Ultimate goal for the system (1–2 sentences):   The system should be usable within a trading day to evaluate adjustments that should be made.
* **What I want the system to do automatically: gather the underlying OHLCV data, dealer and volatility metrics and perform computations.  provide a self-evaluation score of the accuracy of the recommendations it makes.  capture daily computations and recommendations in snapshots that can be evaluated for historical accuracy as time unfolds.  some sort of statistical scoring method like a simple Brier Scoring method to capture and track forecast accuracy.
* **What I want the system to recommend: I need a system that accurately recommend timing of good entry and exit points, using Wyckoff or other methods I may develop over time, for a list of tickers.  The system needs to provide daily recommendations on s associated option strike and expirations that best fit the forecast.
* **What decisions the system should *not* make:   The use of estimated or assumed data - unless explicitly authorized by the operator.   Make recommendations without justification, quantification of accuracy and risk.   

---

## **4. MVP Goal (usable by me & partner by Dec 31, 2025)**

* **Minimum functionality needed for daily use:**
* **Data sources required: raw OHLCV bars from Polygon; raw option chains form Polygon; source of market sentiment; best practices for making trading recommendataions; adjustable parameters for computation methods that can be adjusted based on feedback.
* **Core workflows:   daily scheduled jobs, data base updates with daily OHLCV data and option chains, scanning portfolio lists to identify target tickers, phase/event scoring, recommendation generation, dashboard updates, Brier scoring of past recommendations,  portfolio management (enter tickers, delete tickers, create lists of tickers, export data by ticker, automatic portfolio creation based on criteria by the nightly job ); daily automatic jobs to load data, perform computations and generate recommentions; potentially email processing to capture analyst reports and analyze them for inclusiong into tickers. 
* **Must-have vs Nice-to-have: must have: Must have: daily jobs, time series data, portfolio management, entry/exit recommendations with justification, options recommendations with justification, time series recommendations,  with statistical (brier similar/better) scoring for success or failure, ability to tweak model parameters based on statistical scoring results (were the recommendations accurate/profitable);  Nice to Have include: email scraping and idea ingestions

---

## **5. Requirements (list freely; ChatGPT will structure them)**

Examples: Wyckoff, automated scanner, option alignment, volatility overlays, scoring engine, dashboards.

**My list of requirements:**
1. ability to move 
2. Low maintenance / self-maintainble - good development practices, segmentation/modularity, testability, observability of the system through logs/dashbaords, 
2. Economical but fast time series database - raw data x day x ticker, event and phase detection data x day x ticker x model; recommendations x day x ticker x model; statistical scoring of predicition success by recommendation
3. Ability to easily deploy to the cloud
4. Modern and intuitive graphical interface
5. Ability to get daily recommendations very quickly - even if by daily emailed report
6. Chatbot interface - actions/MCP integration is fine - for adhoc followup

(Add as many as needed.)

---

## **6. Constraints**

* **Cost Constraints** Lets keep development costs down - I don't want to spend more than $100's of dollars on the tools/hosting to get an MVP going - I already have Polygon data subscriptions
* **Time Constraints** Need an MVP by end of 2025
* **Technical Constraints** Need to have independence - ability to host in different places, swap database, swap market data provider, add analysis modules, extend the UI, test historical recommendation
* **Data/latency constraints:** I need something that easily runs in batch for data pipeline tasks; UI should be snappy to browse the portfolio and related recommendations and data

---

## **7. Architectural Preferences**

* **Where I want to run it (local, Replit, Fly.io, etc.):** local development using claude, openai or windsurf, github copilot - deploy to cloud provider - fly.io or other low cost hosting or  gcp/azure/aws
* **Preferred architecture (microservices, monolith, event-driven, etc.):** microservice
* **Frontend preference:** use of FIGMA or other UI development tool so I can use AI to iterate aesthics
* **Desired level of automation (low / medium / high):** highly automatic data pipeline, event/phase detection and recommendation generationm and statistical scoring; medium human intervention for recommendation of parameter adjustments; use of chatbot is low

---

## **8. Output I Want From ChatGPT**

(Check all that apply.)

* [X ] System architecture diagrams
* [ X] MVP requirements list
* [ X] Roadmap: Epics → Increments → Tasks
* [ X] Data model + API schema
* [X ] Tech stack recommendation
* [X ] Build-vs-buy analysis
* [X ] Dev environment setup plan
* [ X] Risk assessment
* [ X] First-sprint implementation plan
* [ ] High-level or detailed code samples

---

## **9. Anything Else Relevant**

(Add anything not captured above.)

---

## **How ChatGPT Will Use This**

Once you fill this out, ChatGPT will produce:

* A clear requirements document
* EPIC-level roadmap (with Program Increments and sequencing)
* MVP definition optimized for year-end availability
* Architecture diagrams and service blueprint
* Recommended tech stack
* Prioritized task list ready for development
* Optional scaffolding code to begin building

---

Here is the publically available github repo with ".md" files that describe my current endeavors.  Load ALL SIX of the following files:
                                                                                                                                        | RAW URL                                                                                                                                                                                                                                                                                      |
Load this file:
https://raw.githubusercontent.com/vkapella/kapman-trader/main/docs/prompts/kapman-portfolio-manager/architecture-kapman-portfolio-manager.md

Load this file:
https://raw.githubusercontent.com/vkapella/kapman-trader/main/docs/prompts/kapman-portfolio-manager/architecture-kapman-wyckoff-compute.md

Load this file:
https://raw.githubusercontent.com/vkapella/kapman-trader/main/docs/prompts/kapman-portfolio-manager/kapman-claude-batch-scanner-reference.md

Load this file:
https://raw.githubusercontent.com/vkapella/kapman-trader/main/docs/prompts/kapman-portfolio-manager/kapman-claude-integration-arch.md

Load this file:
https://raw.githubusercontent.com/vkapella/kapman-trader/main/docs/prompts/kapman-portfolio-manager/replit-kapman-polygon-wrapper.md

Load this file:
https://raw.githubusercontent.com/vkapella/kapman-trader/main/docs/prompts/kapman-portfolio-manager/replit-kapman-portfolio-manager.md



Take all of these inputs and provide a setup wizard with my choices and your observations with an interactive and iterative review of the requirements with observations, recommendations and tweaks to the final requirements.   As a result of completing the wizard, you should output a clean Prompt file "KAPMAN_ARCHITECTURE_PROMPT_1.0.MD" in MD format to be used to generate desired output.  I want to capture and version this MD prompt file in Github before proceeding.

