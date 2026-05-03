import os
from dotenv import load_dotenv

load_dotenv(override=True)

# --- LLM provider keys (set whichever you have; unset keys are skipped) ---
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
MISTRAL_API_KEY    = os.getenv("MISTRAL_API_KEY")
TOGETHER_API_KEY   = os.getenv("TOGETHER_API_KEY")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")

# Comma-separated provider priority order. Only providers with API keys set are active.
# Valid names: groq, anthropic, mistral, together, openai
# Example: LLM_PROVIDER_ORDER=anthropic,groq
LLM_PROVIDER_ORDER = [
    p.strip().lower()
    for p in os.getenv("LLM_PROVIDER_ORDER", "groq,anthropic,mistral,together,openai").split(",")
    if p.strip()
]

# --- Model names per provider ---
GROQ_MODEL       = "llama-3.3-70b-versatile"
ANTHROPIC_MODEL  = "claude-haiku-4-5-20251001"   # $0.80/1M in · $4.00/1M out
MISTRAL_MODEL    = "mistral-small-latest"        # $0.10/1M in · $0.30/1M out
TOGETHER_MODEL   = "meta-llama/Llama-3.3-70B-Instruct-Turbo"  # $0.88/1M
OPENAI_MODEL     = "gpt-4o-mini"                # $0.15/1M in · $0.60/1M out

# --- Pipeline constants ---
WINDOW_SIZE_SEC  = 90
WINDOW_STRIDE_SEC = 30
NUM_CLIPS        = 3
CLIP_MIN_SEC     = 25
CLIP_MAX_SEC     = 35

# Canonical demo: "Inside the Mind of a Master Procrastinator" - Tim Urban TED Talk
DEMO_URL = "https://www.youtube.com/watch?v=arj7oStGLkU"
