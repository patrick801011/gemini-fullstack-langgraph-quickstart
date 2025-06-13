import os
import re

from agent.tools_and_schemas import SearchQueryList, Reflection
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.types import Send
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_core.runnables import RunnableConfig
from google.genai import Client
from agent.traffic_regulations_tool import TrafficRegulationsRAG, REGULATIONS_TEXT

from agent.state import (
    OverallState,
    QueryGenerationState,
    ReflectionState,
    WebSearchState,
)
from agent.configuration import Configuration
from agent.prompts import (
    get_current_date,
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from agent.utils import (
    get_citations,
    get_research_topic,
    insert_citation_markers,
    resolve_urls,
)

load_dotenv()

if os.getenv("GEMINI_API_KEY") is None:
    raise ValueError("GEMINI_API_KEY is not set")

# Used for Google Search API
genai_client = Client(api_key=os.getenv("GEMINI_API_KEY"))

# Instantiate the RAG tool globally
traffic_rag_tool = TrafficRegulationsRAG(REGULATIONS_TEXT)


# Nodes
def generate_query(state: OverallState, config: RunnableConfig) -> QueryGenerationState:
    """LangGraph node that generates a search queries based on the User's question.

    Uses Gemini 2.0 Flash to create an optimized search query for web research based on
    the User's question.

    Args:
        state: Current graph state containing the User's question
        config: Configuration for the runnable, including LLM provider settings

    Returns:
        Dictionary with state update, including search_query key containing the generated query
    """
    configurable = Configuration.from_runnable_config(config)

    # check for custom initial search query count
    if state.get("initial_search_query_count") is None:
        state["initial_search_query_count"] = configurable.number_of_initial_queries

    # init Gemini 2.0 Flash
    llm = ChatGoogleGenerativeAI(
        model=configurable.query_generator_model,
        temperature=1.0,
        max_retries=2,
        api_key=os.getenv("GEMINI_API_KEY"),
    )
    structured_llm = llm.with_structured_output(SearchQueryList)

    # Format the prompt
    current_date = get_current_date()
    formatted_prompt = query_writer_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        number_queries=state["initial_search_query_count"],
    )
    # Generate the search queries
    result = structured_llm.invoke(formatted_prompt)
    #return {"query_list": result.query} # Original return

    # Heuristic Implementation Detail for traffic query detection
    research_topic_str = get_research_topic(state["messages"]).lower()
    is_traffic_query = False
    traffic_keywords = ["交通", "法規", "條例", "罰鍰", "罰款", "道路交通管理處罰條例"]

    for keyword in traffic_keywords:
        if keyword in research_topic_str:
            is_traffic_query = True
            break

    match = re.search(r"第\s*\d+\s*條", research_topic_str)
    if match:
        is_traffic_query = True
        # Normalize the matched group: remove spaces and ensure it's a list
        final_query_list = [match.group(0).replace(" ", "")]
    elif is_traffic_query: # It was a keyword match but not a specific article number
        if result.query:
                final_query_list = [result.query[0]] # Use the first generated query
        else: # Fallback if LLM produced no queries
            final_query_list = [research_topic_str] # Use the original topic
    else: # Not a traffic query
        final_query_list = result.query

    print(f">>> generate_query: is_traffic_query={is_traffic_query}, final_query_list={final_query_list}")
    # Ensure query_list is always a list
    if isinstance(final_query_list, str): # Should not happen with current logic but as a safeguard
        final_query_list = [final_query_list]

    # Ensure all elements in final_query_list are strings if they are SearchQuery objects
    # The RAG tool expects a list of strings, but the web_research node might expect SearchQuery objects or strings.
    # For now, let's assume string queries are fine for both paths.
    # If result.query contains objects, extract the query string.
    # The provided heuristic implies final_query_list will contain strings.
    # query_list in OverallState is Annotated[list, operator.add], typically of strings based on SearchQueryList.
    # The original `result.query` from `SearchQueryList` would be a list of `SearchQuery` objects (which are Pydantic models with a 'query' field).
    # The heuristic needs to ensure it returns a list of strings if that's what downstream nodes expect or handle SearchQuery objects.
    # Given `final_query_list = [result.query[0]]` and `final_query_list = result.query`,
    # we need to ensure these are lists of strings.

    processed_query_list = []
    if final_query_list: # Ensure final_query_list is not None or empty
        for item in final_query_list:
            if hasattr(item, 'query'): # If item is a SearchQuery object
                processed_query_list.append(item.query)
            else: # If item is already a string
                processed_query_list.append(item)

    # Preserve initial_search_query_count if it was part of the original state update logic
    # The original return was just `{"query_list": result.query}`.
    # QueryGenerationState is `query_list: list[Query]`. Query is `query: str, rationale: str`.
    # The heuristic's `final_query_list` is a list of strings. This is a change in type for query_list.
    # For now, we pass it as list of strings. This might need adjustment if other parts of the graph
    # strictly expect `list[Query]` objects. However, `continue_to_web_research` iterates it
    # and passes `search_query` which is then used by `web_research`.
    # `query_traffic_regulations` also expects `state["search_query"][0]` to be a string.
    # So, list of strings seems to be the desired format here.

    return {"query_list": processed_query_list, "is_traffic_query": is_traffic_query, "initial_search_query_count": state.get("initial_search_query_count")}


def decide_next_step_after_query_gen(state: OverallState):
    print(f">>> In decide_next_step_after_query_gen, is_traffic_query: {state.get('is_traffic_query')}")
    if state.get("is_traffic_query"):
        # Send the first query from query_list to the traffic tool.
        # query_traffic_regulations expects search_query to be a list.
        return [Send("query_traffic_regulations", {"search_query": state["query_list"], "id": 0})]
    else:
        # This is the original logic from continue_to_web_research
        return [
            Send("web_research", {"search_query": search_query, "id": int(idx)})
            for idx, search_query in enumerate(state["query_list"])
        ]

# This function might be unused now if generate_query directly calls decide_next_step_after_query_gen
# or if the conditional edge directly uses decide_next_step_after_query_gen.
# For now, keeping it as the subtask did not ask to remove it explicitly.
def continue_to_web_research(state: QueryGenerationState): # state here is OverallState now if called from generate_query's new signature.
    """LangGraph node that sends the search queries to the web research node.

    This is used to spawn n number of web research nodes, one for each search query.
    """
    return [
        Send("web_research", {"search_query": search_query, "id": int(idx)})
        for idx, search_query in enumerate(state["query_list"])
    ]


def web_research(state: WebSearchState, config: RunnableConfig) -> OverallState:
    """LangGraph node that performs web research using the native Google Search API tool.

    Executes a web search using the native Google Search API tool in combination with Gemini 2.0 Flash.

    Args:
        state: Current graph state containing the search query and research loop count
        config: Configuration for the runnable, including search API settings

    Returns:
        Dictionary with state update, including sources_gathered, research_loop_count, and web_research_results
    """
    # Configure
    configurable = Configuration.from_runnable_config(config)
    formatted_prompt = web_searcher_instructions.format(
        current_date=get_current_date(),
        research_topic=state["search_query"],
    )

    # Uses the google genai client as the langchain client doesn't return grounding metadata
    response = genai_client.models.generate_content(
        model=configurable.query_generator_model,
        contents=formatted_prompt,
        config={
            "tools": [{"google_search": {}}],
            "temperature": 0,
        },
    )
    # resolve the urls to short urls for saving tokens and time
    resolved_urls = resolve_urls(
        response.candidates[0].grounding_metadata.grounding_chunks, state["id"]
    )
    # Gets the citations and adds them to the generated text
    citations = get_citations(response, resolved_urls)
    modified_text = insert_citation_markers(response.text, citations)
    sources_gathered = [item for citation in citations for item in citation["segments"]]

    return {
        "sources_gathered": sources_gathered,
        "search_query": [state["search_query"]],
        "web_research_result": [modified_text],
    }


def reflection(state: OverallState, config: RunnableConfig) -> ReflectionState:
    """LangGraph node that identifies knowledge gaps and generates potential follow-up queries.

    Analyzes the current summary to identify areas for further research and generates
    potential follow-up queries. Uses structured output to extract
    the follow-up query in JSON format.

    Args:
        state: Current graph state containing the running summary and research topic
        config: Configuration for the runnable, including LLM provider settings

    Returns:
        Dictionary with state update, including search_query key containing the generated follow-up query
    """
    configurable = Configuration.from_runnable_config(config)
    # Increment the research loop count and get the reasoning model
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    reasoning_model = state.get("reasoning_model") or configurable.reasoning_model

    # Format the prompt
    current_date = get_current_date()
    formatted_prompt = reflection_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        summaries="\n\n---\n\n".join(state["web_research_result"]),
    )
    # init Reasoning Model
    llm = ChatGoogleGenerativeAI(
        model=reasoning_model,
        temperature=1.0,
        max_retries=2,
        api_key=os.getenv("GEMINI_API_KEY"),
    )
    result = llm.with_structured_output(Reflection).invoke(formatted_prompt)

    return {
        "is_sufficient": result.is_sufficient,
        "knowledge_gap": result.knowledge_gap,
        "follow_up_queries": result.follow_up_queries,
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
    }


def evaluate_research(
    state: ReflectionState,
    config: RunnableConfig,
) -> OverallState:
    """LangGraph routing function that determines the next step in the research flow.

    Controls the research loop by deciding whether to continue gathering information
    or to finalize the summary based on the configured maximum number of research loops.

    Args:
        state: Current graph state containing the research loop count
        config: Configuration for the runnable, including max_research_loops setting

    Returns:
        String literal indicating the next node to visit ("web_research" or "finalize_summary")
    """
    configurable = Configuration.from_runnable_config(config)
    max_research_loops = (
        state.get("max_research_loops")
        if state.get("max_research_loops") is not None
        else configurable.max_research_loops
    )
    if state["is_sufficient"] or state["research_loop_count"] >= max_research_loops:
        return "finalize_answer"
    else:
        return [
            Send(
                "web_research",
                {
                    "search_query": follow_up_query,
                    "id": state["number_of_ran_queries"] + int(idx),
                },
            )
            for idx, follow_up_query in enumerate(state["follow_up_queries"])
        ]


def query_traffic_regulations(state: OverallState, config: RunnableConfig) -> OverallState:
    """LangGraph node that queries the local traffic regulations RAG tool."""
    print(">>> In query_traffic_regulations node")
    query = ""
    if isinstance(state["search_query"], list) and state["search_query"]:
        query = state["search_query"][0]
    elif isinstance(state["search_query"], str):
        query = state["search_query"]
    else:
        # Fallback or error if query is not in expected format
        return {
            "web_research_result": ["Error: No valid query found for traffic regulations."],
            "messages": []
        }

    if not query:
        return {
            "web_research_result": ["Error: Empty query for traffic regulations."],
            "messages": []
        }

    print(f"Querying traffic RAG tool with: {query}")
    rag_result = traffic_rag_tool.query(query)
    print(f"RAG tool result: {rag_result}")

    # Ensure web_research_result is a list of strings
    return {
        "web_research_result": [rag_result if isinstance(rag_result, str) else str(rag_result)],
        "messages": [], # Clear previous messages or set as needed for finalize_answer
        "sources_gathered": [] # No external sources for RAG tool
    }


def finalize_answer(state: OverallState, config: RunnableConfig):
    """LangGraph node that finalizes the research summary.

    Prepares the final output by deduplicating and formatting sources, then
    combining them with the running summary to create a well-structured
    research report with proper citations.

    Args:
        state: Current graph state containing the running summary and sources gathered

    Returns:
        Dictionary with state update, including running_summary key containing the formatted final summary with sources
    """
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.reasoning_model

    # Format the prompt
    current_date = get_current_date()
    formatted_prompt = answer_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        summaries="\n---\n\n".join(state["web_research_result"]),
    )

    # init Reasoning Model, default to Gemini 2.5 Flash
    llm = ChatGoogleGenerativeAI(
        model=reasoning_model,
        temperature=0,
        max_retries=2,
        api_key=os.getenv("GEMINI_API_KEY"),
    )
    system_message_content = "請一律使用繁體中文來回答問題，除非使用者明確指定了其他語言。"
    messages = [
        SystemMessage(content=system_message_content),
        HumanMessage(content=formatted_prompt)
    ]
    result = llm.invoke(messages)

    # Replace the short urls with the original urls and add all used urls to the sources_gathered
    unique_sources = []
    for source in state["sources_gathered"]:
        if source["short_url"] in result.content:
            result.content = result.content.replace(
                source["short_url"], source["value"]
            )
            unique_sources.append(source)

    return {
        "messages": [AIMessage(content=result.content)],
        "sources_gathered": unique_sources,
    }


# Create our Agent Graph
builder = StateGraph(OverallState, config_schema=Configuration)

# Define the nodes we will cycle between
builder.add_node("generate_query", generate_query)
builder.add_node("web_research", web_research)
builder.add_node("reflection", reflection)
builder.add_node("query_traffic_regulations", query_traffic_regulations) # Ensure this node is added
builder.add_node("finalize_answer", finalize_answer)

# Set the entrypoint as `generate_query`
# This means that this node is the first one called
builder.add_edge(START, "generate_query")
# Add conditional edge to continue with search queries in a parallel branch
# builder.add_conditional_edges(
#    "generate_query", continue_to_web_research, ["web_research"]
# ) # Old edge
builder.add_conditional_edges(
    "generate_query", decide_next_step_after_query_gen, ["web_research", "query_traffic_regulations"]
)
# Reflect on the web research (if web_research path is taken)
builder.add_edge("web_research", "reflection")
# Route from traffic regulations query directly to finalize_answer
builder.add_edge("query_traffic_regulations", "finalize_answer")
# Evaluate the research
builder.add_conditional_edges(
    "reflection", evaluate_research, ["web_research", "finalize_answer"]
)
# Finalize the answer
builder.add_edge("finalize_answer", END)

graph = builder.compile(name="pro-search-agent")
