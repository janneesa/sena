import unittest

from pydantic import BaseModel, Field

from sena.agent.tools.base import Tool
from sena.agent.tools.toolbox import Toolbox


class EchoArgs(BaseModel):
    value: int = Field(...)


class EchoTool(Tool):
    name = "echo"
    description = "Echo a value back."
    user_message = "running"
    ArgsModel = EchoArgs

    def run(self, args: EchoArgs) -> dict[str, object]:
        return {"value": args.value}


class FailTool(Tool):
    name = "fail"
    description = "A tool that always fails."
    user_message = "running"
    ArgsModel = EchoArgs

    def run(self, args: EchoArgs) -> dict[str, object]:
        raise RuntimeError("boom")


class TestToolbox(unittest.TestCase):
    def test_register_duplicate_raises(self):
        # Verifies duplicate tool names are rejected.
        toolbox = Toolbox()
        toolbox.register(EchoTool())
        with self.assertRaises(ValueError):
            toolbox.register(EchoTool())

    def test_get_ollama_tool_functions_contains_wrapper(self):
        # Verifies toolbox exports callable wrappers with expected behavior.
        toolbox = Toolbox([EchoTool()])
        functions = toolbox.get_ollama_tool_functions()

        self.assertEqual(len(functions), 1)
        wrapped = functions[0]
        self.assertEqual(wrapped.__name__, "echo")
        self.assertEqual(wrapped(value=7), {"value": 7})

    def test_run_tool_not_found(self):
        # Verifies unknown tool lookup returns an error payload.
        toolbox = Toolbox()
        result = toolbox.run_tool("missing", {})
        self.assertIn("error", result)

    def test_run_tool_validation_error(self):
        # Verifies argument validation errors are surfaced cleanly.
        toolbox = Toolbox([EchoTool()])
        result = toolbox.run_tool("echo", {"bad": 1})
        self.assertEqual(result["error"], "Invalid arguments")

    def test_run_tool_exception_wrapped(self):
        # Verifies runtime tool exceptions are returned as error strings.
        toolbox = Toolbox([FailTool()])
        result = toolbox.run_tool("fail", {"value": 1})
        self.assertEqual(result["error"], "boom")
