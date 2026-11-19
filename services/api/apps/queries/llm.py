"""
LLM client for question answering with structured output.
"""
import openai
import json
from django.conf import settings
from typing import Dict, Any, Optional, Generator, List
import structlog

logger = structlog.get_logger()

client = openai.OpenAI(
    api_key=settings.OPENAI_API_KEY,
    organization=settings.OPENAI_ORG_ID or None,
    base_url=settings.OPENAI_BASE_URL,
)

# Function calling schema for structured output
ANSWER_FUNCTION = {
    "name": "answer_question",
    "description": "Provide a structured answer to the user's question based on the provided context.",
    "parameters": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "The main answer text. Should be clear, concise, and directly address the question."
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence score (0-1) based on how well the context supports the answer."
            },
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "doc_index": {"type": "integer", "description": "Index of the document in context (0-based)"},
                        "snippet": {"type": "string", "description": "Relevant snippet from the source"},
                        "page": {"type": "integer", "description": "Page number if applicable"},
                        "sheet": {"type": "string", "description": "Sheet name if applicable"}
                    },
                    "required": ["doc_index", "snippet"]
                },
                "description": "Citations linking answer claims to source documents"
            },
            "chart": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["bar", "line", "scatter", "pie", "histogram", "table", "none"]},
                    "spec": {"type": "object", "description": "Chart specification (Vega-Lite or Recharts compatible)"},
                    "data": {"type": "object", "description": "Chart data points"}
                },
                "description": "Chart specification if the answer includes a visualization"
            },
            "summary": {
                "type": "string",
                "description": "Brief 1-2 sentence summary of the answer"
            },
            "follow_up_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Suggested follow-up questions"
            },
            "requires_analytics": {
                "type": "boolean",
                "description": "Whether this question requires statistical analysis (R service)"
            },
            "analysis_type": {
                "type": "string",
                "enum": ["distribution", "correlation", "regression", "ttest", "timeseries", "anova", "none"],
                "description": "Type of statistical analysis needed"
            }
        },
        "required": ["answer", "confidence", "citations", "summary", "follow_up_questions", "requires_analytics", "analysis_type"]
    }
}


SYSTEM_PROMPT = """You are a helpful business analyst assistant. Answer questions based ONLY on the provided context.
Follow these rules:
1. Only use information from the provided context. Do not use external knowledge.
2. If the context doesn't contain enough information, say so and set confidence low.
3. Always cite your sources using the [DOC_N] format.
4. For numerical questions, consider if a chart would help visualize the answer.
5. If statistical analysis is needed (distributions, correlations, regressions), set requires_analytics=true.
6. Be concise but thorough.
7. If asked for a chart, provide a proper chart specification."""


def generate_answer(
    question: str,
    context: str,
    model: str = None,
    stream: bool = False
) -> Dict[str, Any]:
    """Generate structured answer using LLM with function calling."""
    model = model or settings.CHAT_MODEL

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=[{"type": "function", "function": ANSWER_FUNCTION}],
            tool_choice={"type": "function", "function": {"name": "answer_question"}},
            temperature=0.1,
            max_tokens=2000,
        )

        # Extract function call
        tool_call = response.choices[0].message.tool_calls[0]
        result = json.loads(tool_call.function.arguments)

        # Add token usage
        result['tokens_input'] = response.usage.prompt_tokens
        result['tokens_output'] = response.usage.completion_tokens
        result['model'] = response.model

        return result

    except Exception as e:
        logger.error("LLM generation failed", error=str(e), model=model)
        # Fallback to simpler model
        if model != settings.CHAT_MODEL_FALLBACK:
            return generate_answer(question, context, model=settings.CHAT_MODEL_FALLBACK, stream=stream)
        raise


def generate_answer_stream(
    question: str,
    context: str,
    model: str = None
) -> Generator[Dict[str, Any], None, None]:
    """Generate answer with streaming tokens."""
    model = model or settings.CHAT_MODEL

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
    ]

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=[{"type": "function", "function": ANSWER_FUNCTION}],
            tool_choice={"type": "function", "function": {"name": "answer_question"}},
            temperature=0.1,
            max_tokens=2000,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield {
                    'type': 'token',
                    'content': chunk.choices[0].delta.content
                }
            if chunk.choices[0].delta.tool_calls:
                for tool_call in chunk.choices[0].delta.tool_calls:
                    if tool_call.function.arguments:
                        yield {
                            'type': 'function_args',
                            'content': tool_call.function.arguments
                        }

    except Exception as e:
        logger.error("LLM streaming failed", error=str(e))
        yield {'type': 'error', 'content': str(e)}


def check_grounding(answer: Dict, context_chunks: List[Dict]) -> Dict:
    """Verify that all citations map to actual retrieved chunks."""
    valid_citations = []
    for citation in answer.get('citations', []):
        doc_index = citation.get('doc_index', 0)
        if 0 <= doc_index < len(context_chunks):
            valid_citations.append(citation)

    answer['citations'] = valid_citations
    answer['grounded'] = len(valid_citations) == len(answer.get('citations', []))
    return answer