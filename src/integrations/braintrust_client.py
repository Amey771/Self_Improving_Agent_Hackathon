import os
import braintrust

class BraintrustClient:
    def __init__(self):
        api_key = os.getenv("BRAINTRUST_API_KEY")
        project = os.getenv("BRAINTRUST_PROJECT", "voiceops")
        experiment = os.getenv("BRAINTRUST_EXPERIMENT", "llm-patch-evals")

        if not api_key:
            raise RuntimeError("BRAINTRUST_API_KEY not set")

        self.exp = braintrust.init(
            project=project,
            experiment=experiment,
            api_key=api_key,
            update=True,
            set_current=False
        )

    def log_eval(self, *, input: dict, output: dict, scores: dict, metadata: dict):
        self.exp.log(input=input, output=output, scores=scores, metadata=metadata)
        self.exp.flush()