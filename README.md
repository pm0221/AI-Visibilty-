# 🚀 AI Visibility Audit

**AI Visibility Audit** is an AI-powered auditing system that analyzes how a brand appears in AI-generated answers.

The system understands the brand and its competitors, scrapes relevant websites, extracts and ranks keywords, mines real consumer search patterns, generates realistic consumer queries, filters and scores those queries, and then sends the final query set to Gemini. The resulting AI responses are analyzed for brand and competitor mentions, converted into visibility metrics, and presented through a final interactive HTML dashboard.

> **⚡ Quick Start:** Clone the repository → open in VS Code → create a virtual environment → `pip install -r requirements.txt` → configure `.env` with Groq/Gemini API keys → run `python app.py` → enter brand details → select competitors → start the audit → view the generated HTML report.
>
>
>

## ✨ Features

- **Competitor Discovery & Web Scraping:** Automatically identifies competitors and extracts context from brand/competitor websites.

- **Consumer Context Mining:** Pulls real-world language patterns from Google, Reddit, Quora, and PAA (People Also Ask) to understand how consumers actually phrase questions.

- **Smart Query Generation & Filtering:** Uses Groq to generate hundreds of queries, which are then cleaned, deduplicated, and scored for "naturalness" to ensure only realistic organic questions are audited.

- **Multi-Session AI Auditing:** Runs queries through multiple Gemini sessions to check for consistency in brand visibility.

- **Comprehensive Analytics:** Calculates Share of Voice (SOV), Mention Rate, Query-level visibility, and brand/competitor-exclusive visibility.

- **Interactive Dashboard:** Generates a visually rich HTML report detailing all findings, intent distributions, and dropped queries.




## 🧠 How It Works (The Pipeline)

The complete backend pipeline follows a strict, multi-stage workflow:

1. **User Input** (Brand name, website, category)

2. **Competitor Discovery**

3. **Website Scraping**

4. **Keyword Extraction**

5. **Keyword Intersection**

6. **Keyword Ranking**

7. **Consumer Context Mining**

8. **Category Analysis**

9. **Query Generation** (via Groq)

10. **Query Filtering & Scoring** (Cleaning, deduplication, naturalness grading)

11. **Gemini AI Audit** (Multi-session testing)

12. **Response Parsing**

13. **Scoring & Analytics**

14. **HTML Dashboard Generation**




## ⚙️ Requirements

- Python 3.10+

- Git

- A Code Editor (VS Code recommended)

- **Groq API Key** (for fast query generation and scoring)

- **Gemini API Key** (for the core visibility audit)




## 📥 Installation

**1. Clone the repository:**

```bash
git clone https://github.com/YOUR-USERNAME/AI-Visibility-Audit.git
cd AI-Visibility-Audit

```

**2. Create and activate a virtual environment:**

- **Windows:**

  Bash

  ```
  python -m venv venv
  venv\Scripts\activate

  ```

- **Mac/Linux:**

  Bash

  ```
  python3 -m venv venv
  source venv/bin/activate

  ```

**3. Install dependencies:**

```bash
pip install -r requirements.txt

```

## 🔑 API Key Configuration

Create a `.env` file in the root of your project directory to store your environment variables safely.

**`.env` example:**

```env
GROQ_API_KEY=YOUR_GROQ_API_KEY
GROQ_MODEL=openai/gpt-oss-120b # Or your preferred model
GEMINI_API_KEY=YOUR_GEMINI_API_KEY

```

⚠️ **IMPORTANT:** Never commit your `.env` file to GitHub. Ensure it is included in your `.gitignore` file along with directories like `venv/`, `__pycache__/`, `outputs/`, `chroma_db/`, and `chrome_profile/`.

## ▶️ Running the Project

Once dependencies are installed and API keys are set, start the web interface:

```bash
python app.py

```

*(If your project is configured to start via a different entry point like `main.py` or `web_runner.py`, use that instead).*

The application will start a local server. You should see output similar to:

`Uvicorn running on [http://127.0.0.1:8000](http://127.0.0.1:8000)`

Open that URL in your web browser.

## 📝 How to Use

1. **Enter Brand Details:** Provide the Brand Name (e.g., *Jaguar*), Website (e.g., [*https://www.jaguar.com/*](https://www.jaguar.com/?utm_source=gemini)), and Category/Industry (e.g., *EV Car*).

2. **Select Competitors:** The system will auto-suggest competitors based on your inputs. Select the ones you want to include in the audit (e.g., *Tesla, Mercedes-Benz, BMW*).

3. **Start Audit:** Click "Start Audit" and leave the application running. The backend will execute the pipeline and generate the final HTML report.




## ⏱️ Approximate Execution Time

The audit is a resource-intensive process involving browser automation, scraping, context mining, and hundreds of LLM calls. The total time depends on the number of competitors, website size, and API response times.

- **Small audit:** \~10–20 minutes

- **Medium audit:** \~20–40 minutes

- **Large audit:** 40+ minutes




## 🔎 Query Generation & Filtering

This is the most critical logic block in the project. The system **does not** simply generate queries and blindly pass them to Gemini. It uses a rigorous filtering pipeline:

1. **Raw Generation:** The system prompts Groq to generate 100 consumer-style queries per API call. It can make up to 3 generation attempts to build a sufficiently large pool.

2. **Basic Cleaning:** Removes URLs, website fragments, and garbage characters.

3. **Brand Removal:** Removes explicit mentions of the target brand or competitors to test organic visibility.

4. **Deduplication:** Removes highly similar queries based on word overlap.

5. **Naturalness Scoring:** Groq scores every query (3 = Definitely natural, 2 = Borderline, 1 = Unnatural/AI-generated). Queries scoring `1` are dropped.

6. **Intent Classification:** Queries are tagged by intent (informational, features, situational, purchase).

7. **Final Selection:** The system selects up to **90 high-quality queries** (with a minimum target of 60) and sends them to the Gemini audit.




*(Audit logs for this stage are saved in `outputs/queries_sourced.json`, `queries_all.json`, and `queries_mining_record.json`)*.

## 🎯 How to Change Query Count

To increase or decrease the Gemini workload, modify the configuration variables at the top of `query_generator.py`:

```python
AUDIT_TARGET_QUERIES = 90
AUDIT_MIN_QUERIES = 60
MAX_GENERATION_ATTEMPTS = 3

```

- **To increase queries:** Set `AUDIT_TARGET_QUERIES = 120`.

- **To allow more generation attempts:** Set `MAX_GENERATION_ATTEMPTS = 5`.




⚠️ **Warning:** Increasing query counts significantly increases API usage and execution time. For example, 90 queries run across 3 Gemini audit sessions results in **270 query executions**. Scale these numbers carefully.

## 📊 Final Report

Once complete, the system outputs an interactive HTML dashboard containing:

- **Executive Summary & Scoring:** Overall visibility points and performance metrics.

- **Share of Voice & Mention Rate:** Visual breakdown of how often the brand appears vs. competitors.

- **Intent & Query Analysis:** Success rates grouped by query intent.

- **Exclusive Visibility:** Identifies queries where *only* your brand (or only a competitor) was mentioned.

- **Pipeline Stats:** Displays exact counts for queries generated, filtered, dropped, and audited.




## 📁 Project Structure

```text
AI-Visibility-Audit/
│
├── app.py
├── main.py
├── web_runner.py
│
├── competitor_finder.py
├── website_scraper.py
├── keyword_extractor.py
├── keyword_intersection.py
├── keyword_ranker.py
│
├── context_miner.py
├── category_builder.py
├── query_generator.py
│
├── gemini_auditor.py
├── response_parser.py
├── confidence_engine.py
├── brand_matcher.py
│
├── chroma_memory.py
├── analytics.py
├── report_generator.py
│
├── config.py
│
├── templates/
│   └── index.html
│
├── outputs/
│
├── requirements.txt
├── Dockerfile
└── README.md

```

## 📄 File-by-File Explanation

| **File**                  | **Purpose**                                                      |
| ------------------------- | ---------------------------------------------------------------- |
| `app.py`                  | Web application/backend API and audit progress handling          |
| `main.py`                 | Main pipeline/orchestration entry point                          |
| `web_runner.py`           | Runs the complete audit workflow phase-by-phase                  |
| `competitor_finder.py`    | Discovers potential competitors                                  |
| `website_scraper.py`      | Scrapes website information                                      |
| `keyword_extractor.py`    | Extracts relevant keywords                                       |
| `keyword_intersection.py` | Finds keyword intersections/signals                              |
| `keyword_ranker.py`       | Ranks keywords by relevance                                      |
| `context_miner.py`        | Mines consumer context from web sources (Google, Reddit, etc.)   |
| `category_builder.py`     | Builds/identifies category and industry information              |
| `query_generator.py`      | Generates, cleans, deduplicates, scores, and selects queries     |
| `gemini_auditor.py`       | Sends final queries to Gemini and collects AI responses          |
| `response_parser.py`      | Parses the raw Gemini responses                                  |
| `brand_matcher.py`        | Detects/matches brand and competitor mentions                    |
| `confidence_engine.py`    | Handles confidence/validation-related processing                 |
| `chroma_memory.py`        | Handles ChromaDB-based memory and storage                        |
| `analytics.py`            | Calculates Share of Voice, mention rates, and visibility metrics |
| `report_generator.py`     | Generates the final interactive HTML dashboard                   |
| `config.py`               | Central configuration and environment-variable settings          |
| `templates/index.html`    | The web interface UI                                             |

## ⚠️ Important Notes & Customization Points

- **Scraping Limitations:** The project utilizes Playwright/browser automation for web scraping. Heavily protected websites (Cloudflare, CAPTCHAs) may block scraping attempts.

- **Modifying Prompts:** If you wish to change how Groq generates queries, edit the `_free_gen_prompt()` function inside `query_generator.py`.

- **Scoring Criteria:** To change how queries are graded for naturalness, edit the `_score_classify_prompt()` function inside `query_generator.py`.

- **Deduplication Sensitivity:** The aggressiveness of the deduplication filter is controlled via the `_deduplicate_raw()` similarity threshold inside `query_generator.py`.
