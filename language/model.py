from config import load_lock


class NAtlasLLM:
    def __init__(self, model=None, revision=None, quantize=False):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        lock = load_lock()["llm"]
        self.model_id = model or lock["model"]
        self.revision = revision or lock["revision"]
        kwargs = {"revision": self.revision, "device_map": "auto"}
        if quantize:
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
        else:
            kwargs["torch_dtype"] = torch.float16
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, revision=self.revision)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_id, **kwargs)
        self.temperature = 0.1

    def info(self):
        return {"model": self.model_id, "revision": self.revision}

    def count_tokens(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def generate(self, messages, max_new_tokens=600, repetition_penalty=1.0):
        inputs = self.tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
        ).to(self.model.device)
        n = inputs["input_ids"].shape[1]
        out = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=self.temperature,
            repetition_penalty=repetition_penalty,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        return self.tokenizer.decode(out[0][n:], skip_special_tokens=True).strip()