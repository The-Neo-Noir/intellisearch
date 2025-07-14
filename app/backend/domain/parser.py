from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


from backend.domain.schema import BondQueryResponse

# Define output model using Pydantic

class BondFilters(BaseModel):
    issuer: str | None = Field(None, description="Name of issuer")
    segment: str | None = Field(None, description="PSU, Corporate, etc.")
    coupon: str | None = Field(None, description="Coupon % or range")
    maturityYear: int | None = Field(None, description="Year of maturity")
    yieldType: str | None = Field(None, description="High, low, etc.")
    location: str | None = Field(None, description="Location of the bond.")


parser = JsonOutputParser(pydantic_object=BondQueryResponse)

prompt = ChatPromptTemplate.from_messages([(
            "system",
            "You are a bond search assistant. "
            "Extract bond filters. for example PSU is a segment, India is a location etc "
            "Return only valid JSON matching this schema: "
            "{{issuer, coupon, maturityYear, rating,segment,location}}. "
            "No explanation, no extra text."
        ),
        ("human", "{query}")
    ]
)
load_dotenv()
model = ChatOpenAI(model="gpt-4.1", temperature=0.7)

# Chain: prompt → model → parser
chain = (
        {"query": lambda x: x["query"]}
        | prompt
        | model
        | parser
)

# Invokes openAi with the query passed, and returns the parsed results


def parse_bond_query(query: str) -> dict:
    return chain.invoke({"query": query})
