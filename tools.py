from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from typing import Union, Literal
import json, os
from amazon_scrapper.scrapper import scrape_amazon_india


def extract_content(query: str):
    # Initialize variables to track the position of the first '{' and the last '}'
    start_index = None
    end_index = None
    brace_count = 0

    # Iterate through the string to find the positions
    for i, char in enumerate(query):
        if char == '{':
            if start_index is None:
                start_index = i  # Mark the position of the first '{'
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end_index = i +1 # Mark the position of the last '}'
                break

    # Extract and return the content between the first '{' and the last '}'
    if start_index is not None and end_index is not None:
        return query[start_index:end_index]
    else:
        return None

class QueryDetails(BaseModel):
    rephrased_query: str = Field(description="The rephrased version of the original query.")
    category: str = Field(description="The category inferred from the query.")
    maximum_price: Union[int, None] = Field(default=None, description="The maximum price inferred from the query.")
    minimum_price: Union[int, None] = Field(default=None, description="The minimum price inferred from the query.")


prompt = PromptTemplate(
    input_variables=["query"],
    template="Return True if it could be a query for regarding a product on ecommerce platform else False.: {query}"
)

prompt_v2= PromptTemplate(
    input_variables=["query"],
    template=(
       "Given the following query for indian context, extract and return the following information in JSON format:\n"
        "- rephrased_query: A rephrased version of the optimal query to be used on shopping platform.\n"
        "- category: The category inferred from the query.\n"
        "- maximum_price: The maximum price inferred from the query.\n"
        "- minimum_price: The minimum price inferred from the query.\n\n"
        "Query: {query}\n\n"
        "Response:"
    )
)

llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=os["OPENAI_API_KEY"])
#chain = LLMChain(prompt=prompt, llm=llm)
def is_online_shopping(query: str) -> bool:
    chain = LLMChain(prompt=prompt, llm=llm)
    result = chain.invoke(query)
    
    if result.strip().lower() == "true":
      return True
    else:
      return False

def process_query(query: str) -> Union[dict, bool]:
    """Use this tool extract an evaluate the if the query is related to shopping of a product. And check if it complete or further information is required."""
  
    if not is_online_shopping:
      raise AssertionError("Query Not related to onlline shopping. Appologies to user")
    #prompt= prompt_v2
    chain = LLMChain(prompt=prompt_v2, llm=llm)
    response = chain.invoke(query)
    data = extract_content(response["text"])
    #print(response.startswith("{"))
    try:
        # If the response is a JSON string, use model_validate_json
        details = json.loads(data)
        #print(details)
        # Check if price information is present
        if details["maximum_price"] is not None:
            return details
        elif details["minimum_price"] is not None:
            return details
        else:
            raise AssertionError("Ask from the user for the price.")
    except Exception as e:
        raise AssertionError("Please provide the correct query")

# Initialize OpenAI client
client = OpenAI(api_key=os["OPENAI_API_KEY"])


@tool
def get_top_5_products(query:str)->list:
    """Use this tool extract an evaluate if the query is related to shopping of a product. And check if it complete or further information is required. Then return top 5 products available on amazon according to the query."""

    
    details = process_query(query)
    print(details)
    max_price = details["maximum_price"]
    min_price = details["minimum_price"]
    products = scrape_amazon_india(
        search_query=details["rephrased_query"],
        min_price=min_price,
        max_price=max_price,
        n=5
    )


    # Price filtering
    filtered = []
    for product in products:
        price = product['price']
        if (min_price is None or price >= min_price) and (max_price is None or price <= max_price):
            filtered.append(product)
        elif min_price is None or price >= min_price:
            filtered.append(product) 
        elif max_price is None or price <= max_price:
            filtered.append(product)
    
    # Exit early if no products found
    if not filtered:
        return []
    
    # Prepare product texts for embedding
    product_texts = [
        f"{p['title']} | {p['price']} | Rating: {p['rating']} | Reviews: {p['reviews']}"
        for p in filtered
    ]
    
    # Generate embeddings
    product_embeddings = client.embeddings.create(
        input=product_texts,
        model="text-embedding-3-small"
    ).data
    
    query_embedding = client.embeddings.create(
        input=[query],
        model="text-embedding-3-small"
    ).data[0].embedding
    
    # Calculate similarities
    similarities = []
    for emb in product_embeddings:
        similarities.append(cosine_similarity(
            [query_embedding],
            [emb.embedding]
        )[0][0])
    
    # Get top 5 indicess
    top_indices = np.argsort(similarities)[-5:][::-1]
    
    return [filtered[i] for i in top_indices[:5]]  # Strict top 5

#Example usage
#top_5 = get_top_5_products(
#    "best macbook  under 90000",
#)
#sprint(top_5)

#for idx, product in enumerate(top_5, 1):
#    print(f"{idx}. {product['title'][:55]}...")
#    print(f"   Link: {product['link']}")
#    print(f"   Price: {product['currency']}{product['price']}")
#    print(f"   Rating: {product['rating']}/5 ({product['reviews']} reviews)")
#   print("-" * 60)