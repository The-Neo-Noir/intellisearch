import json
import os

import database.db
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from transformers import GPT2LMHeadModel, GPT2Tokenizer, pipeline

from database.models import Bond
from domain.parser import parse_bond_query
from domain.schema import BondQueryResponse, QueryRequest, BondOut

print("Loaded API key?", os.getenv("OPENAI_API_KEY") is not None)
llm = ChatOpenAI(model="gpt-4.1")  # or "gpt-4o" or "gpt-4.5"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Load fine-tuned model and tokenizer
model_path = "../../training/model/bonds"
model = GPT2LMHeadModel.from_pretrained(model_path)
tokenizer = GPT2Tokenizer.from_pretrained(model_path)
generator = pipeline("text-generation", model=model, tokenizer=tokenizer)


# WebSocket endpoint to get the suggestions from the trained model


@app.websocket("/ws/generate")
async def websocket_generate(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Wait for prompt
            prompt = await websocket.receive_text()

            # Generate predictions
            outputs = generator(
                prompt,
                max_new_tokens=5,
                num_return_sequences=5,
                do_sample=True,
                temperature=0.7
            )

            # Clean and collect suggestions
            suggestions = set()
            for o in outputs:
                next_token = o['generated_text'][len(prompt):].strip()
                clean = next_token.strip('.,;:()[]').lower()
                if clean:
                    suggestions.add(clean)

            # Send response
            await websocket.send_json({"suggestions": list(suggestions)})

    except WebSocketDisconnect:
        print("Client disconnected")


# POST endpoint to retrieve the requests.

@app.post("/bond-query")
async def bond_query(request: QueryRequest):
    result = parse_bond_query(request.query)
    print('results from query:',result)
    parsed_response = BondQueryResponse(**result)

    print('Parsed response:', parsed_response)

    # Construct MongoEngine query filter
    filters = {}
    if parsed_response.isin:
        filters['isin'] = parsed_response.isin

    if parsed_response.issuer:
        filters["issuer__icontains"] = parsed_response.issuer
    if parsed_response.currency:
        filters["currency__icontains"] = parsed_response.currency
    if parsed_response.segment:
        filters["segment__iexact"] = parsed_response.segment
    if parsed_response.coupon:
        try:
            filters["coupon__gte"] = float(parsed_response.coupon)
        except:
            pass
    if parsed_response.maturityYear:
        filters["maturity_year"] = parsed_response.maturityYear
    if parsed_response.yieldType:
        filters["yieldType__icontains"] = parsed_response.yieldType
    if parsed_response.rating:
        filters["rating__icontains"] = parsed_response.rating
    if parsed_response.issuer_location:
        filters["issuer_location__icontains"] = parsed_response.issuer_location

    bonds = Bond.objects(**filters)
   # print('bond filted object', bonds)
    bond_data = [
        BondOut(
            isin= b.isin,
            currency= b.currency,
            issuer=b.issuer,
            segment=b.segment,
            coupon=b.coupon,
            maturityYear=b.maturity_year,
            rating=b.rating,
            yieldType= b.yieldType,
            issuer_location=b.issuer_location,
        )
        for b in bonds
    ]

    return {
        "dsl": json.dumps(result,indent=2),
        "data": bond_data
    }


# For dev run
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
