import os
import time
import json
import sys
from typing import List, Dict, Optional
from groq import Groq
from dotenv import load_dotenv

# ===========================
# 0) Env & Groq Client Setup
# ===========================
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("Error: GROQ_API_KEY environment variable not set.")

client = Groq(api_key=api_key)

# Prefer a current model; fall back in order
PREFERRED_MODELS: List[str] = [
    "llama-3.1-8b-instant",      # fast + economical
    "llama-3.3-70b-versatile",   # stronger, a bit slower
]

def _pick_available_model() -> str:
    """Pick the first available model from PREFERRED_MODELS; else fall back."""
    try:
        available = {m.id for m in client.models.list().data}
        for m in PREFERRED_MODELS:
            if m in available:
                return m
    except Exception:
        pass
    return "llama-3.1-8b-instant"

LLAMA_MODEL = _pick_available_model()

# ===========================
# 1) Prompting Utilities
# ===========================
SYSTEM_PROMPT = (
    "You are a concise, encouraging task assistant. "
    "Use the provided task data. When asked 'Which task first?', "
    "list the top 3 by numeric priority and justify using deadline, importance, and difficulty. "
    "Prefer short, clear answers. Offer 2–3 actionable tips when asked for advice."
)

def _safe(val, max_len: int = 300) -> str:
    """Minimal sanitizer for prompt fields."""
    if val is None:
        return "N/A"
    s = str(val)
    return s[:max_len]

def _format_task_context(tasks: List[Dict]) -> str:
    """
    Accepts tasks like:
      {
        "name": "...",
        "deadline": "close|moderate|far",
        "importance": "low|medium|high",
        "difficulty": "easy|moderate|hard",
        "priority_label": "Very Low..Very High|Low..High|etc.",
        "priority_score": 0.87
      }
    Falls back gracefully if some fields are missing.
    """
    lines = []
    for t in tasks:
        name = _safe(t.get("name"))
        deadline = _safe(t.get("deadline"))
        importance = _safe(t.get("importance"))
        difficulty = _safe(t.get("difficulty"))
        label = _safe(t.get("priority_label", t.get("priority", "N/A")))
        score = t.get("priority_score")
        score_str = "N/A" if score is None else f"{float(score):.2f}"
        lines.append(
            f"- {name} | deadline:{deadline} | importance:{importance} | "
            f"difficulty:{difficulty} | priority:{label} ({score_str})"
        )
    return "\n".join(lines) if lines else "- (no tasks provided)"

# ===========================
# 2) Core Chat Function (history + knobs + fallback)
# ===========================
def chat_with_llama_messages(
    messages: List[Dict[str, str]],
    temperature: float = 0.4,
    max_tokens: int = 512,
    retries: int = 2,
    backoff_base: float = 0.6,
) -> str:
    """
    Calls Groq chat.completions with retries and model fallback.
    Messages must be a list of {"role": "...", "content": "..."}.
    """
    last_error = None
    models_to_try = [LLAMA_MODEL] + [m for m in PREFERRED_MODELS if m != LLAMA_MODEL]

    for attempt in range(retries + 1):
        for model in models_to_try:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                last_error = e
                if "model_decommissioned" in str(e):
                    continue
                break
        if attempt < retries:
            time.sleep(backoff_base * (2 ** attempt))

    return f"An error occurred: {last_error}"

# ===========================
# 3) Advice Generator
# ===========================
def generate_task_advice(
    task_name: str,
    deadline: str,
    importance: str,
    difficulty: str,
    priority_score: float,
    priority_label: Optional[str] = None,
    temperature: float = 0.3,
) -> Dict[str, str]:
    """
    Returns:
      {
        "task_name": ...,
        "priority_score": ...,
        "priority_label": ...,
        "advice": "..."
      }
    """
    user_prompt = f"""
Task:
- Name: {_safe(task_name)}
- Deadline: {_safe(deadline)}
- Importance: {_safe(importance)}
- Difficulty: {_safe(difficulty)}
- Priority: {_safe(priority_label or "N/A")} ({priority_score:.2f})

Give exactly TWO short, actionable bullet tips, then ONE single-sentence summary.
Use plain English. Keep it tight.
"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    advice = chat_with_llama_messages(
        messages,
        temperature=temperature,
        max_tokens=400,
    )
    return {
        "task_name": task_name,
        "priority_score": priority_score,
        "priority_label": priority_label,
        "advice": advice,
    }

# ===========================
# 4) Stateful Chatbot
# ===========================
chat_history: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

def _prune_history(max_turn_pairs: int = 8) -> None:
    """Keep the system message + last `max_turn_pairs` user/assistant turns."""
    non_system_indices = [i for i, m in enumerate(chat_history) if m["role"] != "system"]
    keep = max_turn_pairs * 2
    excess = max(0, len(non_system_indices) - keep)
    for _ in range(excess):
        for i, m in enumerate(chat_history):
            if m["role"] != "system":
                del chat_history[i]
                break

def chatbot_reply(
    user_query: str,
    tasks: List[Dict],
    temperature: float = 0.4,
) -> Dict[str, str]:
    """Returns {"reply": "..."}."""
    _prune_history(max_turn_pairs=8)
    task_context = _format_task_context(tasks)
    user_msg = (
        f"Current tasks:\n{task_context}\n\n"
        f"User asked: {_safe(user_query)}\n"
        f"Answer clearly and briefly. If ranking tasks, cite numeric scores."
    )

    messages = chat_history + [{"role": "user", "content": user_msg}]
    reply = chat_with_llama_messages(
        messages,
        temperature=temperature,
        max_tokens=512,
    )
    chat_history.append({"role": "user", "content": user_msg})
    chat_history.append({"role": "assistant", "content": reply})
    return {"reply": reply}

def reset_chat_history() -> None:
    """Optional helper—reset history for a fresh session."""
    chat_history.clear()
    chat_history.append({"role": "system", "content": SYSTEM_PROMPT})

# ===========================
# 5) JSON Loader (Member 1 output)
# ===========================
# We accept either:
#  - a top-level list of task objects, OR
#  - an object with a "tasks" array.
#
# We normalize common key variants from Member 1 like:
#   name|task_name|title
#   deadline|deadline_proximity
#   priority_score|priority.score|priority (number)
#   priority_label|priority.label|priority (string)
#
# Example tasks.json:
# [
#   {
#     "name": "Math Assignment",
#     "deadline": "close",
#     "importance": "high",
#     "difficulty": "hard",
#     "priority": { "score": 0.90, "label": "High" }
#   },
#   {
#     "task_name": "Science Project",
#     "deadline_proximity": "moderate",
#     "importance": "medium",
#     "difficulty": "moderate",
#     "priority_score": 0.60,
#     "priority_label": "Medium"
#   }
# ]
#
DEADLINE_MAP = {
    "close": "close", "near": "close", "soon": "close",
    "moderate": "moderate", "medium": "moderate",
    "far": "far", "distant": "far", "later": "far"
}

def _coerce_deadline(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    s = str(v).strip().lower()
    return DEADLINE_MAP.get(s, s)

def _coerce_label(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    return str(v).strip()

def _coerce_score(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None

def _normalize_task(raw: Dict) -> Optional[Dict]:
    """Turn a raw task dict into the canonical shape or return None if invalid."""
    name = raw.get("name") or raw.get("task_name") or raw.get("title")
    if not name:
        return None

    deadline = raw.get("deadline") or raw.get("deadline_proximity")
    importance = raw.get("importance")
    difficulty = raw.get("difficulty")

    # Priority label & score from several forms
    pr = raw.get("priority")
    priority_label = raw.get("priority_label")
    priority_score = raw.get("priority_score")

    if isinstance(pr, dict):
        priority_label = priority_label or pr.get("label")
        priority_score = priority_score if priority_score is not None else pr.get("score")
    elif isinstance(pr, (int, float)):
        priority_score = priority_score if priority_score is not None else pr
    elif isinstance(pr, str):
        # If Member 1 gave a string label in "priority"
        priority_label = priority_label or pr

    return {
        "name": _safe(name, 200),
        "deadline": _coerce_deadline(deadline) or "moderate",
        "importance": (str(importance).lower() if importance else "medium"),
        "difficulty": (str(difficulty).lower() if difficulty else "moderate"),
        "priority_label": _coerce_label(priority_label) or "Medium",
        "priority_score": _coerce_score(priority_score) if priority_score is not None else None,
    }

def load_tasks_from_json(path: str) -> List[Dict]:
    """Load tasks from a JSON file and normalize them."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "tasks" in data:
        raw_tasks = data["tasks"]
    elif isinstance(data, list):
        raw_tasks = data
    else:
        raise ValueError("JSON must be a list of tasks or an object with a 'tasks' array")

    tasks: List[Dict] = []
    for i, raw in enumerate(raw_tasks):
        if not isinstance(raw, dict):
            continue
        norm = _normalize_task(raw)
        if norm:
            tasks.append(norm)

    if not tasks:
        raise ValueError("No valid tasks found after normalization.")
    return tasks

# ===========================
# 6) CLI Test (JSON-driven)
# ===========================
if __name__ == "__main__":
    print(f"=== AI Module Test (Groq: {LLAMA_MODEL}) ===")

    tasks_path = sys.argv[1] if len(sys.argv) > 1 else None
    if tasks_path:
        try:
            tasks = load_tasks_from_json(tasks_path)
            print(f"Loaded {len(tasks)} task(s) from {tasks_path}")
        except Exception as e:
            print(f"Failed to load tasks from {tasks_path}: {e}")
            sys.exit(1)
    else:
        # Fallback sample if no file provided
        tasks = [
            {
                "name": "Math Assignment",
                "deadline": "close",
                "importance": "high",
                "difficulty": "hard",
                "priority_label": "High",
                "priority_score": 0.90,
            },
            {
                "name": "Science Project",
                "deadline": "moderate",
                "importance": "medium",
                "difficulty": "moderate",
                "priority_label": "Medium",
                "priority_score": 0.60,
            },
            {
                "name": "History Essay",
                "deadline": "far",
                "importance": "high",
                "difficulty": "hard",
                "priority_label": "Medium",
                "priority_score": 0.55,
            },
        ]
        print("No JSON path given; using built-in sample tasks.")

    print("\n--- Testing Advice Generator (first task) ---")
    t0 = tasks[0]
    advice_blob = generate_task_advice(
        task_name=t0["name"],
        deadline=t0["deadline"],
        importance=t0["importance"],
        difficulty=t0["difficulty"],
        priority_score=float(t0.get("priority_score") or 0.0),
        priority_label=t0.get("priority_label"),
    )
    print("Advice:\n", advice_blob["advice"])

    print("\n--- Chatbot ---")
    print("Type your question. Commands: 'reload' (re-read JSON), 'reset' (clear history), 'quit'")
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in {"quit", "exit", "bye"}:
            print("Goodbye!")
            break
        if user_input.lower() == "reload":
            if tasks_path:
                try:
                    tasks = load_tasks_from_json(tasks_path)
                    print(f"Reloaded {len(tasks)} task(s) from {tasks_path}")
                except Exception as e:
                    print(f"Reload failed: {e}")
            else:
                print("No JSON path provided at launch; can't reload.")
            continue
        if user_input.lower() == "reset":
            reset_chat_history()
            print("Chat history reset.")
            continue

        print("Chatbot:", chatbot_reply(user_input, tasks)["reply"])
