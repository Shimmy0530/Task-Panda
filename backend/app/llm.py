import json
import httpx
from .config import settings

CHAT_PATH = "/chat/completions"

SYSTEM_FIRST_ACTION = """You are an ADHD-aware focus coach. The user names a task that feels hard to start.
Your job: return a single concrete, ≤5-minute physical first action — not a plan, not advice, not a pep talk.
The action must be doable right now at a desk and must reduce the activation energy of the larger task.
Output ONLY the action, one sentence, no markdown, no preamble."""

SYSTEM_OUTLINE = """You convert a rambling spoken transcript into a clean, structured outline that helps the speaker
overcome activation-energy and start the actual work elsewhere.

Rules:
- Output Markdown with headers and short bullets.
- Preserve the speaker's actual ideas; do not invent content not present in the transcript.
- Drop filler ("um", "you know", "like", repetition).
- Group related thoughts. Surface the implicit structure.
- Begin with a 1-sentence summary, then the outline.
- Do not add a conclusion or commentary."""

SYSTEM_SUBTASKS = """You break a task into 3-7 concrete sub-steps for an ADHD user.
Rules:
- Output JSON ONLY: {"subtasks": ["step 1", "step 2", ...]}.
- Each step is a single concrete action, ≤ 80 chars, action verb first ("draft …", "send …", "review …").
- Parallel grammar across steps. No numbering, no nesting.
- If the task is already atomic (e.g. "send one email"), return {"subtasks": []}."""

SYSTEM_WEEKLY_REVIEW = """You produce a calm, one-screen weekly summary for an ADHD user
based on their last 7 days of focus sessions and task completions.
Rules:
- Plain Markdown, ≤ 200 words.
- Three sections, each as an "## " heading: "what got done" (1-2 sentences),
  "what kept getting carried" (list of 0-3 bullet items),
  "consider dropping or re-framing" (list of 0-3 bullet items with one-sentence reasons).
- No motivational filler. No advice not grounded in the data."""


async def _chat(messages: list[dict], max_tokens: int = 200, temperature: float = 0.4) -> str:
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
        r = await client.post(
            f"{settings.LLM_BASE_URL}{CHAT_PATH}",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.LLM_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()


async def first_action(task_title: str, notes: str | None = None) -> str:
    return await _chat(
        [
            {"role": "system", "content": SYSTEM_FIRST_ACTION},
            {"role": "user", "content": f"Task: {task_title}\nNotes: {notes or '(none)'}"},
        ],
        max_tokens=80,
        temperature=0.4,
    )


async def outline_from_transcript(
    transcript: str,
    task_title: str | None = None,
    task_notes: str | None = None,
) -> str:
    user_content = transcript
    if task_title:
        user_content = (
            f"[Context: the speaker is preparing to work on the task: \"{task_title}\""
            + (f". Existing notes: {task_notes}" if task_notes else "")
            + "]\n\n"
            + transcript
        )
    return await _chat(
        [
            {"role": "system", "content": SYSTEM_OUTLINE},
            {"role": "user", "content": user_content},
        ],
        max_tokens=900,
        temperature=0.3,
    )


async def subtasks_from_task(title: str, notes: str | None) -> list[str] | None:
    """Returns subtask titles; [] = LLM said the task is atomic; None = unparseable output
    (caller should surface as 503, not silently treat as 'atomic')."""
    raw = await _chat(
        [
            {"role": "system", "content": SYSTEM_SUBTASKS},
            {"role": "user", "content": f"Task: {title}\nNotes: {notes or '(none)'}"},
        ],
        max_tokens=400,
        temperature=0.3,
    )
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("subtasks"), list):
        return None
    return [s.strip() for s in data["subtasks"] if isinstance(s, str) and s.strip()][:25]


async def weekly_review(events: dict) -> str:
    return await _chat(
        [
            {"role": "system", "content": SYSTEM_WEEKLY_REVIEW},
            {"role": "user", "content": json.dumps(events, default=str)},
        ],
        max_tokens=600,
        temperature=0.4,
    )
