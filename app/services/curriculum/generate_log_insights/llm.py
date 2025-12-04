from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel

from app.core.mongodb import CurriculumConfig, CurriculumInsights
from .prompts import build_taxonomy_prompt, taxonomy_parser, build_classification_prompt, ai_insights_parser

llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0.0,
)


# -----------------------
# Stage 1: Taxonomy Chain
# -----------------------

taxonomy_chain = (
    RunnableLambda(
        lambda d: build_taxonomy_prompt(
            logs=d["logs"],
            curriculum_config=d.get("curriculum_config"),
        )
    )
    | llm
    | taxonomy_parser
)


# --------------------------
# Stage 2: Classification Chain
# --------------------------

insights_chain = (
    RunnablePassthrough.assign(
        taxonomy=taxonomy_chain,
    )
    | RunnableLambda(
        lambda d: build_classification_prompt(
            logs=d["logs"],
            taxonomy=d["taxonomy"],
        )
    )
    | llm
    | ai_insights_parser
)
