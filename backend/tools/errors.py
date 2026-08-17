class PipelineError(Exception):
    def __init__(self, agent_name: str, reason: str):
        self.agent_name = agent_name
        self.reason = reason
        super().__init__(f'[{agent_name}] {reason}')
