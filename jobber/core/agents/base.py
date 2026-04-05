import json
from typing import Any, Callable, Dict, List, Optional, Tuple

import anthropic
from dotenv import load_dotenv

from jobber.core.skills.get_screenshot import get_screenshot
from jobber.utils.extract_json import extract_json
from jobber.utils.function_utils import get_function_schema
from jobber.utils.logger import logger


class BaseAgent:
    def __init__(
        self,
        system_prompt: str = "You are a helpful assistant",
        tools: Optional[List[Tuple[Callable, str]]] = None,
    ):
        load_dotenv()
        self.name = self.__class__.__name__
        self.system_prompt = system_prompt
        self.messages = []
        self.tools_list = []
        self.executable_functions_list = {}
        if tools:
            self._initialize_tools(tools)

    def _initialize_tools(self, tools: List[Tuple[Callable, str]]):
        for function, description in tools:
            self.tools_list.append(
                get_function_schema(function, description=description)
            )
            self.executable_functions_list[function.__name__] = function

    async def generate_reply(
        self, messages: List[Dict[str, Any]], sender
    ) -> Dict[str, Any]:
        self.messages.extend(messages)
        processed_messages = self._process_messages(self.messages)
        self.messages = processed_messages

        client = anthropic.Anthropic()

        while True:
            kwargs = {
                "model": "claude-opus-4-6",
                "max_tokens": 4096,
                "system": self.system_prompt,
                "messages": self.messages,
            }
            if self.tools_list:
                kwargs["tools"] = self.tools_list
                kwargs["tool_choice"] = {"type": "auto"}

            response = client.messages.create(**kwargs)

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if tool_use_blocks:
                # Append assistant turn
                self.messages.append({
                    "role": "assistant",
                    "content": [b.model_dump() for b in response.content],
                })

                tool_results = []
                for tool_use in tool_use_blocks:
                    function_name = tool_use.name
                    function_to_call = self.executable_functions_list.get(function_name)
                    try:
                        function_response = await function_to_call(**tool_use.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": str(function_response),
                        })
                    except Exception as e:
                        logger.info(f"***** Error occurred: {str(e)}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": "The tool responded with an error, please try again with a different tool or modify the parameters of the tool",
                        })

                self.messages.append({"role": "user", "content": tool_results})
                continue

            # Text response
            text_blocks = [b for b in response.content if b.type == "text"]
            content = text_blocks[0].text if text_blocks else ""

            if "##TERMINATE TASK##" in content or "## TERMINATE TASK ##" in content:
                return {
                    "terminate": True,
                    "content": content.replace("##TERMINATE TASK##", "").strip(),
                }
            else:
                try:
                    extracted_response = extract_json(content)
                    if extracted_response.get("terminate") == "yes":
                        return {
                            "terminate": True,
                            "content": extracted_response.get("final_response"),
                        }
                    else:
                        return {
                            "terminate": False,
                            "content": extracted_response.get("next_step"),
                        }
                except Exception as e:
                    logger.info(
                        f"navigator did not send ##Terminate task## error - {e} & content - {content}"
                    )
                    return {
                        "terminate": True,
                        "content": content,
                    }

    def send(self, message: str, recipient):
        return recipient.receive(message, self)

    async def receive(self, message: str, sender):
        reply = await self.generate_reply(
            [{"role": "assistant", "content": message}], sender
        )
        return self.send(reply["content"], sender)

    async def process_query(self, query: str) -> Dict[str, Any]:
        try:
            screenshot = await get_screenshot()
            # Claude image format
            image_data = screenshot
            if screenshot.startswith("data:image/"):
                image_data = screenshot.split(",", 1)[1]

            return await self.generate_reply(
                [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"{query} \nHere is a screenshot of the current browser page",
                            },
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
                ],
                None,
            )
        except Exception as e:
            print(f"Error occurred: {e}")
            return {"terminate": True, "content": f"Error: {str(e)}"}

    def reset_messages(self):
        self.messages = []

    def _process_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed_messages = []

        last_user_message_index = next(
            (
                i
                for i in reversed(range(len(messages)))
                if messages[i]["role"] == "user"
            ),
            -1,
        )

        for i, message in enumerate(messages):
            if message["role"] == "user":
                if isinstance(message.get("content"), list):
                    new_content = []
                    for item in message["content"]:
                        if item["type"] == "text":
                            if i != last_user_message_index:
                                item["text"] = (
                                    item["text"]
                                    .replace(
                                        "Here is a screenshot of the current browser page",
                                        "",
                                    )
                                    .strip()
                                )
                            new_content.append(item)
                        elif item["type"] == "image" and i == last_user_message_index:
                            new_content.append(item)
                    message["content"] = new_content
            processed_messages.append(message)

        return processed_messages
