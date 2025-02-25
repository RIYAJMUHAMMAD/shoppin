from main import graph
import gradio as gr
import os

def chat_with_gpt(query, history):
    config = {"configurable": {"thread_id": "1"}}
    inputs = {"messages": [("user",f"Provide users with link of the product with detailed report for each of the top 5 products found based on the query:{query}")]}

    response = graph.invoke(inputs, config=config)
    return str(response['messages'][-1].content)


iface = gr.ChatInterface(fn=chat_with_gpt, fill_width= True, description="Hi, How may I help you" ,title = "DocBot", css = 'styles.css')
iface.launch(server_name= "0.0.0.0", server_port= 8003)
