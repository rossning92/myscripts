from dataclasses import dataclass


@dataclass
class UsageMetadata:
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def reset(self):
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = 0

    def __str__(self):
        def format_tokens(n):
            if n >= 1000:
                return f"{n // 1000}k"
            return str(n)

        s = format_tokens(max(self.total_tokens, self.input_tokens + self.output_tokens))
        if self.cache_read_input_tokens:
            s += f" (cached={format_tokens(self.cache_read_input_tokens)})"
        return s
