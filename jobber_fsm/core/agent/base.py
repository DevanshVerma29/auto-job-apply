import json
from typing import Callable, List, Optional, Tuple, Type

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from jobber_fsm.utils.function_utils import get_function_schema
from jobber_fsm.utils.logger import logger

load_dotenv()


class BaseAgent:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        input_format: Type[BaseModel],
        output_format: Type[BaseModel],
        tools: Optional[List[Tuple[Callable, str]]] = None,
        keep_message_history: bool = True,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self._initialize_messages()
        self.keep_message_history = keep_message_history

        self.input_format = input_format
        self.output_format = output_format

        self.client = anthropic.Anthropic()

        self.tools_list = []
        self.executable_functions_list = {}
        if tools:
            self._initialize_tools(tools)

    def _initialize_tools(self, tools: List[Tuple[Callable, str]]):
        for func, func_desc in tools:
            self.tools_list.append(get_function_schema(func, description=func_desc))
            self.executable_functions_list[func.__name__] = func

    def _initialize_messages(self):
        self.messages = []

    def _build_output_tool(self) -> dict:
        """Build a Claude tool definition for structured output from the output_format pydantic model."""
        schema = self.output_format.model_json_schema()
        # Remove title from top-level and nested definitions
        schema.pop("title", None)
        return {
            "name": "structured_output",
            "description": f"Return the final structured response as {self.output_format.__name__}",
            "input_schema": schema,
        }

    def _convert_messages_for_claude(self, messages: list) -> list:
        """Convert messages to Claude format (no system role in messages array)."""
        return [m for m in messages if m.get("role") != "system"]

    async def run(self, input_data: BaseModel, screenshot: str = None) -> BaseModel:
        if not isinstance(input_data, self.input_format):
            raise ValueError(f"Input data must be of type {self.input_format.__name__}")

        if not self.keep_message_history:
            self._initialize_messages()

        if screenshot is None:
            self.messages.append(
                {"role": "user", "content": input_data.model_dump_json()}
            )
        else:
            # Claude image format: strip the data URL prefix
            image_data = screenshot
            if screenshot.startswith("data:image/"):
                image_data = screenshot.split(",", 1)[1]

            self.messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": input_data.model_dump_json()},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                    ],
                }
            )

        output_tool = self._build_output_tool()
        all_tools = self.tools_list + [output_tool]

        while True:
            if len(self.tools_list) == 0:
                # Force structured output via the output tool
                tool_choice = {"type": "tool", "name": "structured_output"}
            else:
                tool_choice = {"type": "auto"}

            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                system=self.system_prompt,
                messages=self._convert_messages_for_claude(self.messages),
                tools=all_tools,
                tool_choice=tool_choice,
            )

            # Check for tool use blocks
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                # No tool calls — shouldn't happen with tool_choice forced, but handle gracefully
                text_blocks = [b for b in response.content if b.type == "text"]
                text = text_blocks[0].text if text_blocks else ""
                return self.output_format.model_validate_json(text)

            # Append assistant message with all content blocks
            self.messages.append({
                "role": "assistant",
                "content": [b.model_dump() for b in response.content],
            })

            # Process each tool use block
            tool_results = []
            hit_structured_output = False
            parsed_response = None

            for tool_use in tool_use_blocks:
                if tool_use.name == "structured_output":
                    parsed_response = self.output_format(**tool_use.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": "Output accepted.",
                    })
                    hit_structured_output = True
                else:
                    # Execute browser/other tool
                    result = await self._call_tool(tool_use)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": str(result),
                    })

            self.messages.append({"role": "user", "content": tool_results})

            if hit_structured_output:
                return parsed_response

    async def _call_tool(self, tool_use) -> str:
        function_name = tool_use.name
        function_to_call = self.executable_functions_list.get(function_name)
        if not function_to_call:
            return f"Unknown tool: {function_name}"
        try:
            result = await function_to_call(**tool_use.input)
            return result
        except Exception as e:
            logger.info(f"Error calling tool {function_name}: {str(e)}")
            return f"Tool error: {str(e)}"
