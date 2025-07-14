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
    print(result)
    parsed_response = BondQueryResponse(**result)

    print(parsed_response)

    # Construct MongoEngine query filter
    filters = {}
    if parsed_response.issuer:
        filters["issuer__icontains"] = parsed_response.issuer
    if parsed_response.coupon:
        try:
            filters["coupon__gte"] = float(parsed_response.coupon)
        except:
            pass
    if parsed_response.maturityYear:
        filters["maturity_year"] = parsed_response.maturityYear
    if parsed_response.rating:
        filters["rating__iexact"] = parsed_response.rating
    if parsed_response.segment:
        filters["segment__iexact"] = parsed_response.segment
    if parsed_response.location:
        filters["location__iexact"] = parsed_response.location

    bonds = Bond.objects(**filters)

    return [
        BondOut(
            issuer=b.issuer,
            coupon=b.coupon,
            maturityYear=b.maturity_year,
            rating=b.rating,
            segment=b.segment,
            location=b.location
        )
        for b in bonds
    ]


# For dev run
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
