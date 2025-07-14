from transformers import GPT2LMHeadModel, GPT2Tokenizer, pipeline

# Load your fine-tuned model
model = GPT2LMHeadModel.from_pretrained("../../training/model/bonds")
tokenizer = GPT2Tokenizer.from_pretrained("../../training/model/bonds")

# Create pipeline
generator = pipeline("text-generation", model=model, tokenizer=tokenizer)

# Predict next word only (1 token)
prompt = "psu bonds with "
outputs = generator(prompt, max_new_tokens=5, num_return_sequences=5, do_sample=True, temperature=0.4)

# Extract just the next word
suggestions = set()
print(suggestions)

for o in outputs:
    print(o['generated_text'][len(prompt):].strip())
    next_token = o['generated_text'][len(prompt):].strip()
    clean = next_token.strip('.,;:()[]').lower()
    if clean:
        suggestions.add(clean)

print("Next word suggestions:", suggestions)
