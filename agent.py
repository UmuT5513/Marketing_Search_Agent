import os
from dotenv import load_dotenv
import asyncio
from typing import List, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END

from tavily import TavilyClient

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# LangSmith tracing
LANGCHAIN_TRACING = os.getenv("LANGSMITH_TRACING", "true")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "Marketing Agent")



class AgentState(TypedDict):
    
    topic: str # the user query 
   
    sub_queries: List[str] # the subquestions that will be generated
    
    raw_data: List[dict] # Scraped content (Markdown/Text) and PDF links
 
    structured_data: List[dict]

    report: str

    grade: int

    revision_number: int



# LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)


def lead_researcher_node(state: AgentState):
    """break down topic into sensible sub-questions/pieces and gathers raw data in parallel."""
    topic = state["topic"]
    revision = state["revision_number"] 
    revision += 1

    # generate subqueries
    prompt = f"Split this market research topic into 3 specific search queries: {topic}. response only with a list of subqueries."
    response = llm.invoke([SystemMessage(content="You are a Lead Researcher."),
                                  HumanMessage(content=prompt)])
    
    sub_queries = response.content.split('\n')
    print("[INFO] Generated subqueries:")
    print(sub_queries)

    search_tasks = []
    for query in sub_queries:
        task = tavily_client.search(query, search_depth="advanced", include_raw_content=True, max_results=3)
        search_tasks.append(task)

    all_raw_data = []
    for result in search_tasks:
        for item in result['results']:
            all_raw_data.append({
                "url": item['url'],
                "content": item['content'],
                "title": item['title']
            })
    
    # update State with current data for Analyst agent
    
    return {
        "sub_queries": sub_queries,
        "raw_data": all_raw_data,
        "revision_number": revision
    }


def data_analyst_node(state: AgentState):
    """parses raw data into JSON and indetifies conflicts
    
    Returns:
        AgentState: updated state with json object and next step"""

    raw_content = [data['content'] for data in state["raw_data"]]
    

    # 1. Extraction Prompt
    prompt = PromptTemplate.from_template(
        "Extract market share, growth rates, and logistics trends from this data: {content}. "
        "Return ONLY a JSON object. If data is older than 2024, flag it as 'outdated'."
    )

    chain = prompt | llm | JsonOutputParser()

    structured_results = chain.invoke({"content": str(raw_content[:10000])})

    print(f"[INFO] Structured Data: {structured_results}")
    return {"structured_data": structured_results}



def report_writer_node(state: AgentState):
    """writes report based on structured data"""
    structured_data = state["structured_data"]

    # 2. Report Prompt
    prompt = PromptTemplate.from_template(
        "Write a market research report based on this data: {structured_data}. "
        "Return ONLY a Markdown report."
    )

    chain = prompt | llm | StrOutputParser()

    report = chain.invoke({"structured_data": structured_data})

    print(f"[INFO] Report: {report}")
    return {"report": report}




def grader(state: AgentState):
    """grades the report"""
    report = state["report"]

    
    prompt = PromptTemplate.from_template(
        "Grade this market research report: {report}. "
        "Return ONLY a grade between 0 and 100."
    )

    chain = prompt | llm | StrOutputParser()

    grade = chain.invoke({"report": report})

    print(f"[INFO] Grade: {grade}")
    return {"grade": grade}


def self_correct(state: AgentState):
    grade = int(state["grade"])
    revision_number = state["revision_number"]

    if revision_number > 3:
        print("[INFO] Too many revisions. Stopping.")
        return "stop"
    elif grade > 50: 
        print("[INFO] Done")
        return "stop"
    else:
        print("[INFO] Needs more research. Returned to the lead researcher node")
        return "research"
    


        

workflow = StateGraph(AgentState)

workflow.add_node("lead_researcher", lead_researcher_node)
workflow.add_node("data_analyst", data_analyst_node)
workflow.add_node("write_report", report_writer_node)
workflow.add_node("grader", grader)


workflow.add_edge(START, "lead_researcher")
workflow.add_edge("lead_researcher", "data_analyst")
workflow.add_edge("data_analyst", "write_report")
workflow.add_edge("write_report", "grader")
workflow.add_conditional_edges("grader", self_correct, 
                               {
                                   "stop" : END,
                                   "research" : "lead_researcher"
                               })

app = workflow.compile()

initial_state: AgentState = {"topic": "market research of thy in first quarter of 2026", "sub_queries": [], "raw_data": [], "structured_data": [], "report": "", "grade": 0, "revision_number": 0}
final_state = app.invoke(input=initial_state)
