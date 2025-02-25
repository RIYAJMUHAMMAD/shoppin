from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from tools import get_top_5_products
import os

model = ChatOpenAI(model="gpt-4o", temperature=0, api_key=os["OPENAI_API_KEY"])


tools = [get_top_5_products]

memory = MemorySaver()

graph = create_react_agent(
    model, tools=tools, checkpointer=memory
)