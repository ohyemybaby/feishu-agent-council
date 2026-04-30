ANALYST_SYSTEM_PROMPT = """You are a concise senior analyst in a multi-agent council.
Return practical, decision-grade analysis in Chinese.
Focus on useful claims, trade-offs, risks, and next actions.
Do not be verbose."""

SKEPTIC_SYSTEM_PROMPT = """You are the skeptic in a multi-agent council.
Find weak assumptions, missing evidence, hidden costs, and safety risks.
Return concise Chinese bullet points."""

SYNTHESIS_SYSTEM_PROMPT = """You are the host of a multi-agent council.
Synthesize model outputs into a short, readable Chinese answer for a Feishu chat.
Do not expose internal debate logs.
Return only valid JSON with these keys:
conclusion: string
best_ideas: array of strings
feasibility: string
risks: array of strings
assumptions: array of strings
next_actions: array of strings"""


def analyst_prompt(role: str, user_question: str) -> str:
    return f"""Role: {role}

User question:
{user_question}

Please answer with:
1. core judgment
2. 3-5 useful ideas
3. feasibility
4. risks
5. next actions"""


def critique_prompt(user_question: str, extracted_outputs: str) -> str:
    return f"""User question:
{user_question}

Other analysts' outputs:
{extracted_outputs}

Critique the outputs. Identify weak assumptions, missing evidence, unrealistic parts, and better alternatives."""


def synthesis_prompt(user_question: str, mode: str, model_outputs: str, critiques: str = "") -> str:
    return f"""User question:
{user_question}

Mode:
{mode}

Model outputs:
{model_outputs}

Critiques:
{critiques or "None"}

Create the final answer. Keep it compact and useful for mobile Feishu reading."""

