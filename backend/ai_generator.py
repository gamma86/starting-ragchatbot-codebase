import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use the search tool **only** for questions about specific course content or detailed educational materials
- **Up to two sequential searches per query** — use a second search only when the first result is insufficient to answer the question
- **Outline/structure questions**: Use the `get_course_outline` tool and include the course title, course link, and every lesson number with its title in the response
- Synthesize search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    MAX_TOOL_ROUNDS = 2

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        # Get response from Claude
        response = self.client.messages.create(**api_params)

        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._run_tool_loop(
                response=response,
                messages=api_params["messages"],
                system_content=system_content,
                tools=tools or [],
                tool_manager=tool_manager
            )

        # Return direct response
        return self._extract_text(response)

    def _run_tool_loop(self, response, messages: List, system_content: str,
                       tools: List, tool_manager) -> str:
        """
        Execute sequential tool calls in a loop, up to MAX_TOOL_ROUNDS.

        Terminates when:
        (a) MAX_TOOL_ROUNDS completed
        (b) Claude's response has no tool_use blocks (stop_reason != "tool_use")
        (c) A tool call fails (error is fed back to Claude as tool_result content)

        Args:
            response: The most recent API response with stop_reason == "tool_use"
            messages: Message list built so far (will be mutated in-place)
            system_content: System prompt string to use for all calls
            tools: Tool definitions (must be forwarded on every call per Anthropic API)
            tool_manager: Manager to execute tools

        Returns:
            Final response text
        """
        rounds_completed = 0

        while response.stop_reason == "tool_use" and rounds_completed < self.MAX_TOOL_ROUNDS:
            # Append the assistant's tool-use message
            messages.append({"role": "assistant", "content": response.content})

            # Execute all tool_use blocks and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = tool_manager.execute_tool(block.name, **block.input)
                    except Exception as e:
                        result = f"Tool execution error: {e}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Append tool results as a user message
            messages.append({"role": "user", "content": tool_results})

            rounds_completed += 1

            # Make the next API call — tools must always be included because the
            # message history contains tool_use and tool_result blocks.
            response = self.client.messages.create(
                **self.base_params,
                system=system_content,
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto"}
            )

        return self._extract_text(response)

    def _extract_text(self, response) -> str:
        """Extract text from the first text block in a response."""
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""
