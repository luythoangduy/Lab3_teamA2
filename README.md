# Lab 3: Chatbot vs ReAct Agent (Industry Edition)

Welcome to Phase 3 of the Agentic AI course! This lab focuses on moving from a simple LLM Chatbot to a sophisticated **ReAct Agent** with industry-standard monitoring.

## 🚀 Getting Started

### 1. Setup Environment
Copy the `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Directory Structure
- `src/tools/`: Product catalog tools (dummyjson.com).
- `src/chatbot/`: Baseline + tool-aware chatbot (no real tool execution).
- `src/agent/`: ReAct agent with Thought-Action-Observation loop.
- `demo_compare.py`: Run chatbot vs agent scenarios side-by-side.

### 4. Quick Demo (Product Catalog)

**Web UI (recommended for presentation):**
```bash
pip install -r requirements.txt
python web_demo.py
# Open http://127.0.0.1:5000 — Simulate mode works without API keys
python web_demo.py --live   # uses real LLM from .env
```

**Terminal:**
```bash
python demo_compare.py --refresh-cache   # optional: cache 30 products offline
python demo_compare.py                   # runs 4 scenarios (hallucination, multi-step, ...)
python demo_compare.py --scenario 1      # single scenario
```

## 🏠 Running with Local Models (CPU)

If you don't want to use OpenAI or Gemini, you can run open-source models (like Phi-3) directly on your CPU using `llama-cpp-python`.

### 1. Download the Model
Download the **Phi-3-mini-4k-instruct-q4.gguf** (approx 2.2GB) from Hugging Face:
- [Phi-3-mini-4k-instruct-GGUF](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf)
- Direct Download: [phi-3-mini-4k-instruct-q4.gguf](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf)

### 2. Place Model in Project
Create a `models/` folder in the root and move the downloaded `.gguf` file there.

### 3. Update `.env`
Change your `DEFAULT_PROVIDER` and set the path:
```env
DEFAULT_PROVIDER=local
LOCAL_MODEL_PATH=./models/Phi-3-mini-4k-instruct-q4.gguf
```

## 🎯 Lab Objectives

1.  **Baseline Chatbot**: Observe the limitations of a standard LLM when faced with multi-step reasoning.
2.  **ReAct Loop**: Implement the `Thought-Action-Observation` cycle in `src/agent/agent.py`.
3.  **Provider Switching**: Swap between OpenAI and Gemini seamlessly using the `LLMProvider` interface.
4.  **Failure Analysis**: Use the structured logs in `logs/` to identify why the agent fails (hallucinations, parsing errors).
5.  **Grading & Bonus**: Follow the [SCORING.md](file:///Users/tindt/personal/ai-thuc-chien/day03-lab-agent/SCORING.md) to maximize your points and explore bonus metrics.

## 🛠️ How to Use This Baseline
The code is designed as a **Production Prototype**. It includes:
- **Telemetry**: Every action is logged in JSON format for later analysis.
- **Robust Provider Pattern**: Easily extendable to any LLM API.
- **Clean Skeletons**: Focus on the logic that matters—the agent's reasoning process.

---

## Product Shopping Agent

This branch includes a retail product agent powered by the public DummyJSON Products API:

- Chat naturally with the user.
- Fetch product data from `https://dummyjson.com/products`.
- Store the catalog in local SQLite at `data/products.sqlite3`.
- Use read-only SQL for product queries.
- Map heuristic requests like `looks young` to bright colors and `garment for woman` to women's fashion terms.
- Return at most 5 products with Markdown images inside the chat response.

Run it:

```bash
python -m src.product_chat
```

Example prompts:

```text
Show me garment for woman that looks young
Select all products in womens-dresses
Find cheap beauty products and show images
```

*Happy Coding! Let's build agents that actually work.*
