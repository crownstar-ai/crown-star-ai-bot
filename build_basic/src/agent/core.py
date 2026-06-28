# agent/core.py – CrownStar ReAct / AutoGPT Agent Orchestration Engine
import os, json, time, hashlib, re, threading, traceback
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import deque
import logging
import requests

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Tool Definitions
# --------------------------------------------------------------------
@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict  # JSON schema
    function: Callable

class ToolRegistry:
    """Registry of tools that agents can use."""
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        # Search tool
        self.register(Tool(
            name="web_search",
            description="Search the web for current information. Input: query string.",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
            function=self._web_search
        ))
        # Code executor
        self.register(Tool(
            name="execute_python",
            description="Execute Python code and return output. Input: code string.",
            parameters={"type": "object", "properties": {"code": {"type": "string"}}},
            function=self._execute_python
        ))
        # Data query (federated)
        self.register(Tool(
            name="query_data",
            description="Run SQL query across CrownStar data mesh. Input: SQL statement.",
            parameters={"type": "object", "properties": {"sql": {"type": "string"}}},
            function=self._query_data
        ))
        # File operations
        self.register(Tool(
            name="read_file",
            description="Read file from local disk. Input: file path.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            function=self._read_file
        ))
        self.register(Tool(
            name="write_file",
            description="Write content to file. Input: path and content.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
            function=self._write_file
        ))
        # CrownStar native tools
        self.register(Tool(
            name="crownstar_chat",
            description="Ask CrownStar AI a question. Input: question string.",
            parameters={"type": "object", "properties": {"question": {"type": "string"}}},
            function=self._crownstar_chat
        ))
        self.register(Tool(
            name="generate_image",
            description="Generate image from text prompt. Input: prompt.",
            parameters={"type": "object", "properties": {"prompt": {"type": "string"}}},
            function=self._generate_image
        ))

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict]:
        return [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in self._tools.values()]

    # Tool implementations (simplified)
    def _web_search(self, query: str) -> str:
        try:
            # Use a simple search API (simulated)
            resp = requests.get(f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("AbstractText", f"No results for {query}")
            return f"Search failed for {query}"
        except Exception as e:
            return f"Search error: {e}"

    def _execute_python(self, code: str) -> str:
        # Security sandbox would be required in production
        try:
            local_globals = {}
            exec(code, {"__builtins__": __builtins__}, local_globals)
            # Capture output (simplified)
            return "Code executed successfully (output capture not implemented)"
        except Exception as e:
            return f"Execution error: {e}"

    def _query_data(self, sql: str) -> str:
        # Call data mesh API
        try:
            resp = requests.post("http://localhost:8080/v1/data/query", json={"sql": sql, "limit": 10}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return f"Query returned {data.get('row_count', 0)} rows. Sample: {data.get('rows', [])[:3]}"
            return f"Query failed: {resp.text}"
        except Exception as e:
            return f"Data query error: {e}"

    def _read_file(self, path: str) -> str:
        try:
            with open(path, 'r') as f:
                return f.read(5000)  # limit size
        except Exception as e:
            return f"Error reading file: {e}"

    def _write_file(self, path: str, content: str) -> str:
        try:
            with open(path, 'w') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Write error: {e}"

    def _crownstar_chat(self, question: str) -> str:
        try:
            resp = requests.post("http://localhost:8080/v1/chat/completions", json={"query": question, "tier": "enterprise"}, timeout=60)
            if resp.status_code == 200:
                return resp.json().get("response", "")
            return "CrownStar chat unavailable"
        except Exception as e:
            return f"Chat error: {e}"

    def _generate_image(self, prompt: str) -> str:
        # Placeholder – would call Stable Diffusion API
        return f"[Generated image for '{prompt}'] (simulated)"

# --------------------------------------------------------------------
# ReAct Agent (Reasoning + Acting)
# --------------------------------------------------------------------
class ReActAgent:
    """
    ReAct agent: Thought -> Action -> Observation loop.
    Uses CrownStar model for reasoning and tool calling.
    """
    def __init__(self, name: str, tools: ToolRegistry, max_iterations: int = 10, verbose: bool = True):
        self.name = name
        self.tools = tools
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.memory = deque(maxlen=50)  # short‑term memory
        self.history: List[Dict] = []

    def _reason(self, prompt: str) -> Dict:
        """
        Call CrownStar model to produce Thought and Action.
        Returns dict with "thought" and "action" (tool name and input).
        """
        system_prompt = """You are a ReAct agent. You have access to these tools:
{}

Given a user query, respond with:
Thought: <your reasoning>
Action: <tool_name>
Action Input: <json input for the tool>

If you have enough information to answer, respond with:
Final Answer: <answer>
"""
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools.list_tools()])
        prompt = system_prompt.format(tool_descriptions) + "\n\nUser query: " + prompt
        # Call CrownStar API
        try:
            resp = requests.post("http://localhost:8080/v1/chat/completions", json={"query": prompt, "tier": "enterprise", "temperature": 0.2}, timeout=60)
            if resp.status_code == 200:
                response = resp.json().get("response", "")
                return self._parse_response(response)
            return {"thought": "Failed to call model", "action": None}
        except Exception as e:
            return {"thought": f"Model error: {e}", "action": None}

    def _parse_response(self, text: str) -> Dict:
        """Extract Thought, Action, Action Input, or Final Answer from model output."""
        lines = text.split("\n")
        thought = ""
        action = None
        action_input = None
        final_answer = None
        for line in lines:
            if line.startswith("Thought:"):
                thought = line[8:].strip()
            elif line.startswith("Action:"):
                action = line[7:].strip()
            elif line.startswith("Action Input:"):
                input_str = line[13:].strip()
                # try to parse JSON
                try:
                    action_input = json.loads(input_str)
                except:
                    action_input = {"input": input_str}
            elif line.startswith("Final Answer:"):
                final_answer = line[13:].strip()
        if final_answer:
            return {"thought": thought, "final_answer": final_answer, "action": None}
        return {"thought": thought, "action": action, "action_input": action_input}

    def run(self, task: str) -> str:
        """Execute agent loop."""
        current_prompt = task
        for i in range(self.max_iterations):
            if self.verbose:
                logger.info(f"Agent {self.name} iteration {i+1}")
            # Reason
            reasoning = self._reason(current_prompt)
            self.history.append({"iteration": i, "type": "reasoning", "content": reasoning})
            if "final_answer" in reasoning:
                return reasoning["final_answer"]
            # Execute action
            action_name = reasoning.get("action")
            action_input = reasoning.get("action_input", {})
            if not action_name:
                # Fallback: assume model wants to respond directly
                return reasoning.get("thought", "No action determined")
            tool = self.tools.get_tool(action_name)
            if not tool:
                observation = f"Error: Tool '{action_name}' not found"
            else:
                try:
                    # Call tool function
                    if isinstance(action_input, dict):
                        result = tool.function(**action_input)
                    else:
                        result = tool.function(action_input)
                    observation = str(result)
                except Exception as e:
                    observation = f"Tool execution error: {e}"
            self.history.append({"iteration": i, "type": "observation", "content": observation})
            # Update prompt with observation
            current_prompt += f"\n\nObservation: {observation}\nContinue."
            if self.verbose:
                logger.debug(f"Observation: {observation[:200]}")
        return "Max iterations reached without final answer."

# --------------------------------------------------------------------
# AutoGPT‑style autonomous agent
# --------------------------------------------------------------------
class AutonomousAgent(ReActAgent):
    """
    AutoGPT style: plans subgoals, executes tools, evaluates progress.
    """
    def __init__(self, name: str, tools: ToolRegistry, max_iterations: int = 20, verbose: bool = True):
        super().__init__(name, tools, max_iterations, verbose)
        self.goals = deque()

    def plan(self, objective: str) -> List[str]:
        """Use CrownStar to break objective into subgoals."""
        plan_prompt = f"Break down the following objective into 3-5 clear subgoals:\n{objective}"
        resp = requests.post("http://localhost:8080/v1/chat/completions", json={"query": plan_prompt, "temperature": 0.3}, timeout=60)
        if resp.status_code == 200:
            plan_text = resp.json().get("response", "")
            # Parse subgoals (one per line starting with number or dash)
            goals = re.findall(r'^\s*[\d\-*]+\s*(.*)$', plan_text, re.MULTILINE)
            return goals if goals else [objective]
        return [objective]

    def run_autonomous(self, objective: str) -> str:
        """Autonomous execution with planning and subgoal management."""
        self.goals = deque(self.plan(objective))
        overall_result = []
        while self.goals and len(self.history) < self.max_iterations:
            current_goal = self.goals.popleft()
            result = self.run(current_goal)
            overall_result.append(f"Goal: {current_goal}\nResult: {result}")
            # Optional: evaluate if objective is achieved
        return "\n\n".join(overall_result)

# --------------------------------------------------------------------
# Agent Manager (singleton)
# --------------------------------------------------------------------
class AgentManager:
    def __init__(self):
        self.tool_registry = ToolRegistry()
        self.agents: Dict[str, ReActAgent] = {}
        self.active_agent = None

    def create_agent(self, name: str, agent_type: str = "react", max_iterations: int = 10) -> str:
        if agent_type == "autogpt":
            agent = AutonomousAgent(name, self.tool_registry, max_iterations)
        else:
            agent = ReActAgent(name, self.tool_registry, max_iterations)
        self.agents[name] = agent
        return name

    def run_agent(self, name: str, task: str) -> Dict:
        agent = self.agents.get(name)
        if not agent:
            return {"error": f"Agent {name} not found"}
        start = time.time()
        result = agent.run(task)
        duration = time.time() - start
        return {
            "agent": name,
            "result": result,
            "duration_seconds": duration,
            "iterations": len(agent.history),
            "history": agent.history
        }

    def stop_agent(self, name: str):
        if name in self.agents:
            # In a real implementation, would cancel running thread
            pass

    def list_agents(self) -> List[str]:
        return list(self.agents.keys())

_manager = None
def get_agent_manager():
    global _manager
    if _manager is None:
        _manager = AgentManager()
    return _manager
