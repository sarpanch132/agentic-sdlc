"""Local-only project profiles; no provider credentials or service startup."""
import json


LOCAL_GUARD = '''import socket
network_attempts = []
def deny_network(*args, **kwargs):
    network_attempts.append(True)
    raise RuntimeError("network is disabled in the local tooling check")
socket.socket.connect = deny_network
socket.create_connection = deny_network
'''

CHECKS = {
    'agno': '''from agno.agent import Agent
from agno.models.message import Message
agent = Agent(name="sdlc-local", telemetry=False)
message = Message(role="user", content="local configuration check")
assert agent.name == "sdlc-local" and not agent.telemetry
assert message.content == "local configuration check"
''',
    'deepeval': '''from deepeval.models import DeepEvalBaseLLM
from deepeval.metrics import ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, ToolCall
class NoModel(DeepEvalBaseLLM):
    def load_model(self): return self
    def generate(self, *args, **kwargs): raise AssertionError("model calls disabled")
    async def a_generate(self, *args, **kwargs): raise AssertionError("model calls disabled")
    def get_model_name(self): return "local-disabled"
metric = ToolCorrectnessMetric(model=NoModel(), include_reason=False,
                              async_mode=False, should_exact_match=True)
call = ToolCall(name="local_tool", input_parameters={"value": 1})
case = LLMTestCase(input="local", actual_output="local", tools_called=[call], expected_tools=[call])
metric.measure(case)
assert metric.score == 1.0
''',
    'bentoml': '''import bentoml
model = bentoml.picklable_model.save_model("sdlc-local-check", {"value": 7})
assert bentoml.picklable_model.load_model(model.tag) == {"value": 7}
assert any(item.tag == model.tag for item in bentoml.models.list())
''',
    'mlflow': '''import os
import mlflow
from mlflow import MlflowClient
mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
mlflow.set_experiment("sdlc-local-checks")
with mlflow.start_run() as run:
    mlflow.log_param("mode", "local-only")
    mlflow.log_metric("configuration_check", 1.0)
    run_id = run.info.run_id
stored = MlflowClient().get_run(run_id)
assert stored.data.params["mode"] == "local-only"
assert stored.data.metrics["configuration_check"] == 1.0
''',
    'openllmetry': '''from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import workflow
from traceloop.sdk.instruments import Instruments
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
exporter = InMemorySpanExporter()
Traceloop.init(app_name="sdlc-local", exporter=exporter, disable_batch=True,
               telemetry_enabled=False, should_enrich_metrics=False,
               instruments=set(), block_instruments=set(Instruments))
@workflow(name="local_configuration_check")
def local_check(value):
    return value + 1
assert local_check(2) == 3
assert len(exporter.get_finished_spans()) >= 1
''',
}


def profile_files(identity):
    settings = {'schema_version': 1, 'tool': identity, 'mode': 'local-only',
                'provider': None, 'application_acceptance': 'not-tested'}
    files = {'config.json': (json.dumps(settings, indent=2) + '\n').encode()}
    if identity in CHECKS:
        files['check.py'] = (LOCAL_GUARD + CHECKS[identity]
                             + '\nassert not network_attempts\nprint("SDLC_LOCAL_CONFIGURATION_OK")\n').encode()
    if identity == 'promptfoo':
        files['promptfooconfig.json'] = (json.dumps({
            'description': 'Local tooling check; replace with approved project evaluations',
            'prompts': ['{{input}}'], 'providers': ['echo'],
            'tests': [{'vars': {'input': 'SDLC_LOCAL_CONFIGURATION_OK'},
                       'assert': [{'type': 'equals', 'value': 'SDLC_LOCAL_CONFIGURATION_OK'}]}]
        }, indent=2) + '\n').encode()
    return files
