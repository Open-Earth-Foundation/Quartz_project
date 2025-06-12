"""
Tests for LangGraph functionality with a minimal two-node graph.
"""
import pytest
from typing import TypedDict, Annotated, Literal, Any

# Import LangGraph modules
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    # Create dummy variables for type hints
    class DummyStateGraph:
        def __init__(self, state_schema: Any): # Accept an argument
            pass
        # Add dummy methods for add_node, add_edge, etc. if linter complains further
        def add_node(self, name: str, node: Any) -> None: pass
        def add_edge(self, source: str, target: str) -> None: pass
        def add_conditional_edges(self, source: str, router: Any, mapping: Any) -> None: pass
        def set_entry_point(self, name: str) -> None: pass
        def compile(self) -> Any: 
            # Return a dummy compiled graph that has an invoke method
            class DummyCompiledGraph:
                def invoke(self, initial_state: Any) -> Any:
                    return {}
            return DummyCompiledGraph()

    StateGraph = DummyStateGraph # Use the dummy class
    END = "END"

# Define a simple state schema for our ping-pong graph
class PingPongState(TypedDict):
    message: str
    counter: int

# Define the nodes (functions)
def ping_node(state: PingPongState) -> PingPongState:
    """Ping node that receives any message and responds with 'ping'"""
    return {"message": "ping", "counter": state["counter"] + 1}

def pong_node(state: PingPongState) -> PingPongState:
    """Pong node that receives 'ping' and responds with 'pong'"""
    return {"message": "pong", "counter": state["counter"] + 1}

# Define the conditional router for the ping node
def ping_router(state: PingPongState) -> Literal["pong", "end"]:
    """Route to pong if counter < 3, otherwise end the graph"""
    if state["counter"] < 3:
        return "pong"
    else:
        return "end"

@pytest.mark.skipif(
    not LANGGRAPH_AVAILABLE,
    reason="LangGraph is not installed"
)
def test_ping_pong_graph():
    """
    Test a minimal LangGraph with two nodes that pass messages back and forth.
    """
    if not LANGGRAPH_AVAILABLE:
        pytest.skip("LangGraph is not installed")
        return
    
    # Create the graph builder with PingPongState as the state schema
    builder = StateGraph(PingPongState)
    
    # Add nodes
    builder.add_node("ping", ping_node)  # type: ignore
    builder.add_node("pong", pong_node)  # type: ignore
    
    # Add edges - using conditional edges for ping
    builder.add_conditional_edges(  # type: ignore
        "ping",
        ping_router,
        {
            "pong": "pong",
            "end": END
        }
    )
    
    # Add a direct edge from pong back to ping
    builder.add_edge("pong", "ping")  # type: ignore
    
    # Set the entry point
    builder.set_entry_point("ping")  # type: ignore
    
    # Compile the graph
    graph = builder.compile()  # type: ignore
    
    # Run the graph with an initial state
    initial_state = {"message": "start", "counter": 0}
    
    # Execute and collect results
    result = graph.invoke(initial_state)
    
    # Verify the final state
    assert result["counter"] == 3, "Counter should be 3 after execution"
    assert result["message"] == "ping", "Final message should be 'ping'"

def test_langgraph_imported():
    """Test that LangGraph can be imported."""
    assert LANGGRAPH_AVAILABLE, "LangGraph should be available"

if __name__ == "__main__":
    print("Running LangGraph tests directly...")
    pytest.main(["-xvs", __file__]) 