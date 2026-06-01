# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Đạt
- **Student ID**: [Your ID Here]
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

In this lab, my contributions focused on designing, implementing, and documenting the **Tool Design Evolution** and **Trace Quality** sections for the group. I also refined the agentic telemetry logging and structured error-handling frameworks to ensure strict tracking of loops, latencies, and parsing failures.

- **Modules Implemented / Modified**:
  - `src/tools/product_tools.py` ([product_tools.py](file:///Users/nthanhdat/Documents/AI_20K_Vinuni/Assignment/Lab3/Lab3_new/Lab3_teamA2/src/tools/product_tools.py)): Co-developed the specialized identity tools (`get_product_by_id`, `cheapest_in_category`) and built secure safeguards for the read-only relational database tool (`query_products_sql`).
  - `src/telemetry/logger.py` ([logger.py](file:///Users/nthanhdat/Documents/AI_20K_Vinuni/Assignment/Lab3/Lab3_new/Lab3_teamA2/src/telemetry/logger.py)): Integrated events (`HALLUCINATION_ERROR`, `PARSE_ERROR`, `AGENT_TOOL_ERROR`) to track performance metrics and diagnose ReAct agent decisions.
- **Code Highlights**:
  - *SQL Read-Only Security Guardrails*:
    ```python
    def query_sql(self, sql: str, limit: int = 5) -> List[Dict[str, Any]]:
        self.ensure_loaded()
        normalized = sql.strip().rstrip(";")
        if not re.match(r"(?is)^select\b", normalized):
            raise ValueError("Only SELECT queries are allowed.")
        if re.search(r"(?is)\b(insert|update|delete|drop|alter|create|replace|truncate)\b", normalized):
            raise ValueError("Write or schema-changing SQL is not allowed.")
        ...
    ```
    This function intercepts SQL queries constructed by the LLM and blocks any dangerous, state-changing statements before execution.
- **Documentation & Analysis**:
  - Developed the **Tool Design Evolution** progression matrix in the group report, analyzing the structural shift from fuzzy string searching (v1) to deterministic category aggregation and custom read-only SQL querying (v3).
  - Maintained the **Trace Quality** test suite documentation, recording and categorizing active reasoning traces into Factual ID Lookups, Extreme Aggregations, and Error self-recovery flows.

---

## II. Debugging Case Study (10 Points)

- **Problem Description**: 
  During test runs for compound natural language queries (such as *"Show all womens-dresses that look young"*), the LLM attempted to write highly specific SQL statements that assumed non-existent database columns (e.g. `SELECT * FROM products WHERE looks_young = 1` or `category = 'womens-dresses' AND age_group = 'teen'`), resulting in database operational crashes: `sqlite3.OperationalError: no such column: looks_young`.
- **Log Source**:
  Captured in `logs/2026-06-01.log`:
  ```json
  {"timestamp": "2026-06-01T15:30:10.123456", "event": "AGENT_TOOL_ERROR", "data": {"tool": "query_products_sql", "error": "no such column: looks_young"}}
  ```
- **Diagnosis**: 
  The LLM assumed the SQLite structure based on terms present in the user query rather than keeping strictly to the real catalog fields. The tool prompt did not explicitly restrict column names, leaving the database open to structural hallucinations.
- **Solution**: 
  1. I updated the prompt documentation of `query_products_sql` to strictly dictate the permitted schema: `id, title, description, category, price, rating, stock, brand, thumbnail, images, tags`.
  2. I refined the `ReActAgent._execute_tool` logic to catch tool exceptions gracefully and report the operational error message as the `Observation`. This allowed the agent to self-correct in the next step by switching to `search_products({"query": "looks young garment for woman"})` which processes the descriptors using pre-defined python heuristics.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**: 
   The `Thought` scratchpad represents a massive paradigm shift. Instead of immediately writing out a guessed answer as in a standard Chatbot, the `Thought` block gives the agent cognitive space to plan actions step-by-step. This grounding directly prevents hallucinations since the model only outputs the final response once it has validated factual observations in its loop.
2. **Reliability**: 
   A ReAct agent can sometimes be *less* reliable than a Chatbot when faced with loose, casual conversations (e.g., *"Hello! Hope you have a great day!"*). In these cases, the agent might waste cycles trying to figure out what tool to call, occasionally hallucinating action strings, which adds unnecessary runtime cost, higher latency, and risk of formatting crashes.
3. **Observation**: 
   Observations act as the agent's real-world environment feedback. If a database search comes up empty or throws an SQL syntax error, the agent intercepts the observation, adapts its cognitive context, and takes a different action (e.g., trying keyword search instead of SQL) to self-recover.

---

## IV. Future Improvements (5 Points)

To scale this agentic system for enterprise production:
- **Vector DB Semantic Search**: Implement dense vector embeddings (e.g. using ChromaDB or FAISS) to support deep semantic query understanding (e.g., *"comfortable outfit for summer outings"*) without relying on simple text heuristics.
- **Parameterized SQL Builder**: Move away from raw text SELECT queries to parameterized ORMs (like SQLAlchemy) to entirely eliminate potential prompt injection attacks where a user tricks the agent into writing dangerous SQL strings.
- **Multi-Agent state architecture**: Migrate the simple ReAct loop to stateful routing (such as **LangGraph**), splitting tasks between a Search Agent, an SQL Analyst Agent, and a Supervisor Agent to manage long-term conversation states robustly.
