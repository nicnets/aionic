"""
~200 pre-seeded canonical AI topics with aliases and categories.
Run once on startup if topics table is empty.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.db.models import Topic
import re


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


SEED_TOPICS: list[dict] = [
    # ---- Large Language Models ----
    {"name": "Large Language Models", "category": "research",
     "aliases": ["llm", "llms", "large language model", "foundation models", "foundation model"]},
    {"name": "GPT-4", "category": "tools",
     "aliases": ["gpt4", "gpt 4", "openai gpt-4", "chatgpt-4"]},
    {"name": "Claude", "category": "tools",
     "aliases": ["claude ai", "claude 3", "claude 4", "anthropic claude"]},
    {"name": "Gemini", "category": "tools",
     "aliases": ["google gemini", "gemini pro", "gemini ultra", "bard"]},
    {"name": "Llama", "category": "tools",
     "aliases": ["llama 2", "llama 3", "llama3", "meta llama", "llama model"]},
    {"name": "Mistral", "category": "tools",
     "aliases": ["mistral ai", "mistral 7b", "mixtral", "mistral model"]},
    {"name": "Qwen", "category": "tools",
     "aliases": ["qwen2", "alibaba qwen", "qwen model"]},
    {"name": "DeepSeek", "category": "tools",
     "aliases": ["deepseek ai", "deepseek r1", "deepseek v3"]},

    # ---- AI Agents ----
    {"name": "AI Agents", "category": "research",
     "aliases": ["ai agent", "autonomous agent", "autonomous agents", "agentic ai",
                 "ai agent framework", "ai agent system", "ai agents system",
                 "ai agents for workflow", "intelligent agent"]},
    {"name": "Multi-Agent Systems", "category": "research",
     "aliases": ["multi agent", "multi-agent", "agent collaboration", "agent swarm",
                 "swarm intelligence"]},
    {"name": "AutoGPT", "category": "tools",
     "aliases": ["auto gpt", "auto-gpt"]},
    {"name": "LangChain", "category": "tools",
     "aliases": ["lang chain", "langchain framework"]},
    {"name": "LangGraph", "category": "tools",
     "aliases": ["lang graph"]},
    {"name": "CrewAI", "category": "tools",
     "aliases": ["crew ai", "crewai framework"]},
    {"name": "AutoGen", "category": "tools",
     "aliases": ["microsoft autogen", "auto gen"]},

    # ---- Retrieval & Memory ----
    {"name": "RAG", "category": "research",
     "aliases": ["retrieval augmented generation", "retrieval-augmented generation",
                 "rag pipeline", "rag system"]},
    {"name": "Vector Databases", "category": "tools",
     "aliases": ["vector db", "vector store", "vector search", "embedding database",
                 "pinecone", "chroma", "weaviate", "qdrant", "milvus", "faiss"]},
    {"name": "Knowledge Graphs", "category": "research",
     "aliases": ["knowledge graph", "graph rag", "graphrag"]},

    # ---- Fine-tuning & Training ----
    {"name": "Fine-tuning", "category": "research",
     "aliases": ["finetuning", "fine tuning", "model fine-tuning", "llm fine-tuning",
                 "instruction tuning", "rlhf fine-tuning"]},
    {"name": "RLHF", "category": "research",
     "aliases": ["reinforcement learning from human feedback",
                 "reinforcement learning human feedback", "rlaif"]},
    {"name": "LoRA", "category": "research",
     "aliases": ["lora fine-tuning", "low-rank adaptation", "qlora", "peft"]},
    {"name": "Synthetic Data", "category": "research",
     "aliases": ["synthetic data generation", "data synthesis", "ai generated data"]},

    # ---- Inference & Efficiency ----
    {"name": "Model Quantization", "category": "research",
     "aliases": ["quantization", "int4", "int8", "gguf", "ggml", "awq", "gptq"]},
    {"name": "Model Distillation", "category": "research",
     "aliases": ["knowledge distillation", "model compression", "distillation"]},
    {"name": "Inference Optimization", "category": "research",
     "aliases": ["llm inference", "inference speed", "speculative decoding",
                 "flash attention", "kv cache"]},
    {"name": "Local LLMs", "category": "tools",
     "aliases": ["local llm", "on-device llm", "edge llm", "ollama", "lm studio",
                 "run llm locally", "offline llm"]},

    # ---- Multimodal ----
    {"name": "Multimodal AI", "category": "research",
     "aliases": ["multimodal", "vision language model", "vlm", "image language model",
                 "multimodal llm", "mllm"]},
    {"name": "Text-to-Image", "category": "tools",
     "aliases": ["text to image", "image generation", "stable diffusion", "midjourney",
                 "dall-e", "dalle", "flux model", "image synthesis"]},
    {"name": "Text-to-Video", "category": "tools",
     "aliases": ["text to video", "video generation", "sora", "runway ml", "video synthesis"]},
    {"name": "Text-to-Speech", "category": "tools",
     "aliases": ["text to speech", "tts", "voice synthesis", "speech synthesis",
                 "elevenlabs", "voice cloning"]},
    {"name": "Speech Recognition", "category": "tools",
     "aliases": ["asr", "speech to text", "whisper", "automatic speech recognition"]},

    # ---- Code & Developer Tools ----
    {"name": "AI Coding Assistants", "category": "tools",
     "aliases": ["github copilot", "copilot", "cursor ai", "ai code completion",
                 "ai pair programming", "devin", "code llm", "code generation"]},
    {"name": "AI Code Review", "category": "tools",
     "aliases": ["automated code review", "ai pr review"]},

    # ---- Prompting ----
    {"name": "Prompt Engineering", "category": "research",
     "aliases": ["prompt design", "prompting", "chain of thought", "cot",
                 "few-shot prompting", "zero-shot", "system prompt"]},
    {"name": "Prompt Injection", "category": "research",
     "aliases": ["prompt injection attack", "jailbreak", "jailbreaking"]},

    # ---- AI Safety & Alignment ----
    {"name": "AI Safety", "category": "research",
     "aliases": ["ai alignment", "model alignment", "ai risk", "safe ai",
                 "ai existential risk", "superalignment"]},
    {"name": "AI Hallucinations", "category": "research",
     "aliases": ["hallucination", "llm hallucination", "model hallucination",
                 "confabulation", "factual accuracy"]},
    {"name": "AI Bias", "category": "research",
     "aliases": ["model bias", "algorithmic bias", "ai fairness", "llm bias"]},
    {"name": "Explainable AI", "category": "research",
     "aliases": ["xai", "interpretability", "model interpretability",
                 "ai transparency", "explainability"]},

    # ---- Infrastructure & MLOps ----
    {"name": "MLOps", "category": "tools",
     "aliases": ["ml ops", "machine learning operations", "llmops", "llm ops"]},
    {"name": "AI Infrastructure", "category": "tools",
     "aliases": ["gpu infrastructure", "ai compute", "tpu", "ai hardware"]},
    {"name": "Model Serving", "category": "tools",
     "aliases": ["model deployment", "inference serving", "triton", "vllm", "tgi"]},
    {"name": "AI APIs", "category": "tools",
     "aliases": ["llm api", "ai api", "openai api", "anthropic api"]},

    # ---- Enterprise AI ----
    {"name": "Enterprise AI", "category": "industry",
     "aliases": ["enterprise llm", "ai in enterprise", "corporate ai", "business ai"]},
    {"name": "AI Automation", "category": "industry",
     "aliases": ["workflow automation", "ai workflow", "rpa ai", "hyperautomation",
                 "process automation"]},
    {"name": "Copilots", "category": "tools",
     "aliases": ["ai copilot", "microsoft copilot", "digital assistant",
                 "ai assistant", "virtual assistant"]},

    # ---- Startups & Funding ----
    {"name": "AI Startups", "category": "startups",
     "aliases": ["ai startup", "ai company", "ai unicorn", "ai seed funding"]},
    {"name": "AI Investment", "category": "startups",
     "aliases": ["ai funding", "ai venture capital", "ai series a", "ai series b",
                 "ai ipo", "ai valuation"]},

    # ---- AI in Industries ----
    {"name": "AI in Healthcare", "category": "industry",
     "aliases": ["medical ai", "healthcare ai", "clinical ai", "ai diagnosis",
                 "ai drug discovery", "ai radiology"]},
    {"name": "AI in Finance", "category": "industry",
     "aliases": ["fintech ai", "ai trading", "ai fraud detection", "financial ai"]},
    {"name": "AI in Education", "category": "industry",
     "aliases": ["edtech ai", "ai tutoring", "ai in schools", "personalized learning"]},
    {"name": "AI in Legal", "category": "industry",
     "aliases": ["legal ai", "ai lawyer", "contract ai", "legaltech ai"]},
    {"name": "AI in Marketing", "category": "industry",
     "aliases": ["marketing ai", "ai content marketing", "ai copywriting",
                 "ai seo", "personalization ai"]},
    {"name": "AI in Manufacturing", "category": "industry",
     "aliases": ["manufacturing ai", "industrial ai", "ai quality control",
                 "predictive maintenance"]},
    {"name": "AI in Robotics", "category": "industry",
     "aliases": ["robotics ai", "robot learning", "embodied ai", "humanoid robot",
                 "boston dynamics", "figure ai"]},

    # ---- Regulation & Ethics ----
    {"name": "AI Regulation", "category": "policy",
     "aliases": ["ai law", "ai policy", "eu ai act", "ai governance",
                 "ai legislation", "ai compliance"]},
    {"name": "AI Ethics", "category": "policy",
     "aliases": ["responsible ai", "ai accountability", "ai principles"]},
    {"name": "AI Copyright", "category": "policy",
     "aliases": ["ai ip", "ai intellectual property", "training data copyright",
                 "ai generated content copyright"]},

    # ---- Open Source ----
    {"name": "Open Source AI", "category": "research",
     "aliases": ["open source llm", "open weight", "open weights model",
                 "hugging face open source", "open model"]},

    # ---- Specific techniques ----
    {"name": "Mixture of Experts", "category": "research",
     "aliases": ["moe", "mixture-of-experts", "sparse moe", "moe model"]},
    {"name": "Context Window", "category": "research",
     "aliases": ["context length", "long context", "long context window",
                 "1m context", "128k context"]},
    {"name": "Reasoning Models", "category": "research",
     "aliases": ["chain of thought reasoning", "o1 model", "o3 model",
                 "thinking model", "slow thinking"]},
    {"name": "Embedding Models", "category": "research",
     "aliases": ["text embeddings", "sentence embeddings", "embedding model",
                 "semantic search"]},

    # ---- Tools & Platforms ----
    {"name": "Hugging Face", "category": "tools",
     "aliases": ["huggingface", "hf hub", "hugging face hub"]},
    {"name": "OpenAI", "category": "startups",
     "aliases": ["open ai", "chatgpt company", "openai company"]},
    {"name": "Anthropic", "category": "startups",
     "aliases": ["anthropic ai", "claude company"]},
    {"name": "Google DeepMind", "category": "startups",
     "aliases": ["deepmind", "google ai", "google brain"]},
    {"name": "Microsoft AI", "category": "startups",
     "aliases": ["microsoft ai", "azure ai", "azure openai"]},

    # ---- Gadgets & Hardware ----
    {"name": "AI Hardware", "category": "gadgets",
     "aliases": ["ai chip", "neural processing unit", "npu", "ai accelerator",
                 "gpu for ai"]},
    {"name": "AI Wearables", "category": "gadgets",
     "aliases": ["ai glasses", "smart glasses", "ai wearable", "rabbit r1",
                 "humane ai pin", "ai pin"]},
    {"name": "NVIDIA", "category": "tools",
     "aliases": ["nvidia gpu", "nvidia ai", "h100", "h200", "blackwell gpu"]},

    # ---- Education & Learning ----
    {"name": "AI Courses", "category": "courses",
     "aliases": ["ai certification", "machine learning course", "deep learning course",
                 "ai bootcamp", "prompt engineering course"]},

    # ---- Benchmarks ----
    {"name": "AI Benchmarks", "category": "research",
     "aliases": ["llm benchmark", "mmlu", "humaneval", "hellaswag", "arc",
                 "gsm8k", "model evaluation", "evals"]},
]


async def seed_topics(session: AsyncSession) -> None:
    count = await session.scalar(select(func.count()).select_from(Topic))
    if count and count > 0:
        return

    for item in SEED_TOPICS:
        topic = Topic(
            name=item["name"],
            slug=_slug(item["name"]),
            aliases=item.get("aliases", []),
            category=item.get("category"),
            is_approved=True,
        )
        session.add(topic)

    await session.commit()
