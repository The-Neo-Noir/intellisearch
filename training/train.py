from transformers import GPT2Tokenizer, GPT2LMHeadModel, Trainer, TrainingArguments, DataCollatorForLanguageModeling
from datasets import load_dataset
import os

# 1. Load and preprocess dataset
dataset = load_dataset("text", data_files={"train": "data/bond_search_queries.txt"})

tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
tokenizer.pad_token = tokenizer.eos_token  # to avoid padding warnings

def tokenize(batch):
    return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=64)

tokenized_dataset = dataset.map(tokenize, batched=True)

# 2. Load base model
model = GPT2LMHeadModel.from_pretrained("gpt2")
data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

# 3. Set up training arguments
training_args = TrainingArguments(
    output_dir="./bond-gpt2-finetuned",
    overwrite_output_dir=True,
    num_train_epochs=5,
    per_device_train_batch_size=4,
    save_steps=500,
    save_total_limit=2,
    logging_steps=100,
    weight_decay=0.01,
    fp16=False,
    push_to_hub=False,
)

# 4. Create and run Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    tokenizer=tokenizer,
    data_collator=data_collator,
)

trainer.train()

# 5. Save final model + tokenizer for export/conversion
model.save_pretrained("./model/bonds")
tokenizer.save_pretrained("./model/bonds")
