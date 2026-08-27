from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


from domain.schema import BondQueryResponse

# Define output model using Pydantic

class BondFilters(BaseModel):
    isin: str | None = Field(None, description='isin number is the name of the bond id')
    currency: str| None=Field(None, description='Currency of the bond')
    issuer: str | None = Field(None, description="Name of issuer")
    segment: str | None = Field(None, description="PSU, Corporate, etc.")
    coupon: str | None = Field(None, description="Coupon % or range")
    maturityYear: int | None = Field(None, description="Year of maturity and current year is 2026")
    yieldType: str | None = Field(None, description="Fixed, Floating are valid values of yield type")
    issuer_location: str | None = Field(None, description="Location of the bond issued by . like Singapore , HongKong , US,UK,AU")


parser = JsonOutputParser(pydantic_object=BondQueryResponse)

prompt = ChatPromptTemplate.from_messages([(
            "system",
            "You are a bond search assistant.just return parsed mapping into dsl "
            "Extract bond filters. for example PSU is a segment, Singapore,HongKong, US,UK,AU etc is a issuer location etc "
            "isin is the bond identification number Structure: First 2 letters (country code), next 9 alphanumeric characters (identifier), final 1 digit (check digit).Usage: Used for trading, clearing, and settling securities worldwide, reducing forgery risks.Coverage: Covers various instruments including equities, derivatives, debt securities, and bonds."
            "Note that current year is 2026"
            "Return only valid JSON matching this schema: "
            "get the issuer locations in short form like United States as US,Netherlands as NL,United Kingdom as UK etc"
            "{{isin,currency,issuer,segment, coupon, maturityYear,yieldType, rating,segment,issuer_location}}. "
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
