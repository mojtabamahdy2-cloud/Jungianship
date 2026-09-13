import logging
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types
from src.config import GEMINI_API_KEY, GENERATION_MODEL
from src.engine.retriever import HybridRetriever
from src.engine.prompts import (
    FIRST_PERSON_SYSTEM_PROMPT,
    SCHOLAR_SYSTEM_PROMPT,
    DREAM_SYSTEM_PROMPT,
    CONCEPT_SYSTEM_PROMPT,
    JUNG_SYSTEM_PROMPT,  # backward-compat alias
)

logger = logging.getLogger(__name__)

class DialecticalEngine:
    """Orchestrates persona-grounded retrieval-augmented generation using Google Gemini.

    The persona is fully configurable via PERSONA_* environment variables in .env.
    Supports two voice modes:
      - 'first_person': Bot speaks directly as the historical figure.
      - 'scholar': Bot speaks as an academic expert on the figure.
    """

    def __init__(self, retriever: HybridRetriever, model_name: str = GENERATION_MODEL, api_key: str = GEMINI_API_KEY):
        self.retriever = retriever
        self.model_name = model_name
        self.client = genai.Client(api_key=api_key)

    def generate_response(
        self,
        query: str,
        mode: str = "jung",
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Generate a dialectical philosophical response grounded in Jung's writings."""
        # 1. Retrieve relevant passages
        retrieved_chunks = self.retriever.search(query)
        context_str = self.retriever.format_context_for_llm(retrieved_chunks)

        # 2. Select system prompt based on persona mode
        system_prompt = FIRST_PERSON_SYSTEM_PROMPT if mode in ("first_person", "jung") else SCHOLAR_SYSTEM_PROMPT

        # 3. Build contents list including conversation history
        contents = []

        # Context preamble
        preamble = (
            f"PRIMARY JUNG SOURCE EXCERPTS FOR GROUNDING:\n\n{context_str}\n\n"
            "INSTRUCTION: Address the user's question. Weave insights and citations from the primary source "
            "excerpts above naturally into your response, adhering faithfully to the analytical psychology framework."
        )
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=preamble)]))
        contents.append(types.Content(role="model", parts=[types.Part.from_text(text="Understood. I will consult these primary writings and address the seeker's inquiry with analytical depth and authenticity.")]))

        # Append recent history
        if history:
            for msg in history[-4:]:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))

        # Current query
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=query)]))

        # 4. Generate with Gemini
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
            max_output_tokens=2048
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config
            )
            reply_text = response.text.strip()
        except Exception as e:
            logger.error(f"Generation error: {e}")
            reply_text = "My thoughts are clouded by an inner silence at this moment. Let us pause and reflect again shortly."

        # Extract citation references
        citations = []
        for c in retrieved_chunks:
            source = c.get("cw_volume") or c.get("title") or "Collected Works"
            para = f" {c['para_range']}" if c.get("para_range") else ""
            citations.append(f"{source}{para}")

        return {
            "text": reply_text,
            "citations": list(dict.fromkeys(citations)),  # unique
            "chunks": retrieved_chunks
        }

    def analyze_dream(self, dream_text: str) -> Dict[str, Any]:
        """Perform Jungian dream amplification."""
        retrieved_chunks = self.retriever.search(f"dream symbol analysis {dream_text}", top_k=4)
        context_str = self.retriever.format_context_for_llm(retrieved_chunks)

        prompt = (
            f"PRIMARY JUNG SOURCE EXCERPTS ON DREAMS & SYMBOLS:\n\n{context_str}\n\n"
            f"DREAM REPORT FROM SEEKER:\n\"{dream_text}\"\n\n"
            "Please amplify and analyze this dream using your analytical and archetypal method."
        )

        config = types.GenerateContentConfig(
            system_instruction=DREAM_SYSTEM_PROMPT,
            temperature=0.75,
            max_output_tokens=2048
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            reply_text = response.text.strip()
        except Exception as e:
            logger.error(f"Dream analysis error: {e}")
            reply_text = "The dream remains veiled in the mists of the unconscious. Please share more details or reflect upon your immediate associations."

        return {"text": reply_text, "chunks": retrieved_chunks}

    def define_concept(self, concept: str) -> Dict[str, Any]:
        """Retrieve authoritative definition from CW 6 Psychological Types or core canon."""
        retrieved_chunks = self.retriever.search(f"definition of {concept} in analytical psychology", top_k=4)
        context_str = self.retriever.format_context_for_llm(retrieved_chunks)

        prompt = (
            f"PRIMARY JUNG SOURCE EXCERPTS:\n\n{context_str}\n\n"
            f"CONCEPT TO DEFINE: {concept}\n\n"
            "Provide the authoritative Jungian definition, psychological function, and relevant citations."
        )

        config = types.GenerateContentConfig(
            system_instruction=CONCEPT_SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=1500
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            reply_text = response.text.strip()
        except Exception as e:
            logger.error(f"Concept definition error: {e}")
            reply_text = f"Could not retrieve definition for '{concept}' at this time."

        return {"text": reply_text, "chunks": retrieved_chunks}
