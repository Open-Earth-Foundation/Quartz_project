#!/usr/bin/env python3
"""
Agent Graph Visualization Generator

This script creates a visual graph showing the agents in the automatic research system
and their workflow relationships.
"""

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import FancyBboxPatch
import matplotlib.patches as mpatches

def create_agent_graph():
    """Create and display a graph of the agents and their workflow."""
    
    # Create directed graph
    G = nx.DiGraph()
    
    # Define agents and their roles with improved positioning
    agents = {
        'Planner': {
            'description': 'Query Formulation &\nStrategic Planner',
            'color': '#FF6B6B',
            'position': (2, 6)
        },
        'Researcher': {
            'description': 'Data Collection &\nWeb Scraping',
            'color': '#4ECDC4', 
            'position': (6, 6)
        },
        'Raw Content\nReviewer': {
            'description': 'Content Quality\nAssessment',
            'color': '#45B7D1',
            'position': (10, 6)
        },
        'Extractor': {
            'description': 'Data Extraction &\nStructuring',
            'color': '#96CEB4',
            'position': (10, 2)
        },
        'Structured\nReviewer': {
            'description': 'Structured Data\nValidation',
            'color': '#FFEAA7',
            'position': (6, 2)
        },
        'Deep Diver': {
            'description': 'Focused Research\n& Analysis',
            'color': '#DDA0DD',
            'position': (2, 2)
        }
    }
    
    # Add nodes to graph
    for agent, info in agents.items():
        G.add_node(agent, **info)
    
    # Define workflow edges with simplified labels
    edges = [
        ('Planner', 'Researcher', 'search plan'),
        ('Researcher', 'Raw Content\nReviewer', 'scraped content'),
        ('Raw Content\nReviewer', 'Extractor', 'approved content'),
        ('Raw Content\nReviewer', 'Planner', 'refine plan'),
        ('Extractor', 'Structured\nReviewer', 'structured data'),
        ('Structured\nReviewer', 'Deep Diver', 'deep dive request'),
        ('Structured\nReviewer', 'Planner', 'plan update'),
        ('Deep Diver', 'Researcher', 'new URLs')
    ]
    
    # Add edges to graph
    for source, target, label in edges:
        G.add_edge(source, target, label=label)
    
    # Create the plot with larger figure
    plt.figure(figsize=(16, 12))
    
    # Get positions
    pos = {agent: info['position'] for agent, info in agents.items()}
    
    # Draw nodes with larger boxes
    for agent, info in agents.items():
        x, y = pos[agent]
        
        # Draw fancy box for each agent (larger boxes)
        bbox = FancyBboxPatch(
            (x-0.8, y-0.6), 1.6, 1.2,
            boxstyle="round,pad=0.15",
            facecolor=info['color'],
            edgecolor='black',
            linewidth=2,
            alpha=0.9
        )
        plt.gca().add_patch(bbox)
        
        # Add agent name (larger font)
        plt.text(x, y+0.2, agent, ha='center', va='center', 
                fontsize=13, fontweight='bold')
        
        # Add description (larger font)
        plt.text(x, y-0.25, info['description'], ha='center', va='center', 
                fontsize=10, style='italic')
    
    # Draw edges with better positioned labels
    edge_offsets = {
        ('Planner', 'Researcher'): (0, 0.4),
        ('Researcher', 'Raw Content\nReviewer'): (0, 0.4),
        ('Raw Content\nReviewer', 'Extractor'): (0.5, 0),
        ('Raw Content\nReviewer', 'Planner'): (0, -0.8),
        ('Extractor', 'Structured\nReviewer'): (0, -0.4),
        ('Structured\nReviewer', 'Deep Diver'): (0, -0.4),
        ('Structured\nReviewer', 'Planner'): (0, 0.8),
        ('Deep Diver', 'Researcher'): (0, 0.8)
    }
    
    for source, target, label in edges:
        x1, y1 = pos[source]
        x2, y2 = pos[target]
        
        # Calculate arrow position
        dx = x2 - x1
        dy = y2 - y1
        
        # Adjust start and end points to not overlap with larger boxes
        if dx != 0:
            start_x = x1 + (0.8 if dx > 0 else -0.8)
            end_x = x2 + (-0.8 if dx > 0 else 0.8)
        else:
            start_x = x1
            end_x = x2
            
        if dy != 0:
            start_y = y1 + (0.6 if dy > 0 else -0.6)
            end_y = y2 + (-0.6 if dy > 0 else 0.6)
        else:
            start_y = y1
            end_y = y2
        
        # Draw arrow
        plt.annotate('', xy=(end_x, end_y), xytext=(start_x, start_y),
                    arrowprops=dict(arrowstyle='->', lw=2, color='darkblue'))
        
        # Add edge label with custom positioning
        offset = edge_offsets.get((source, target), (0, 0))
        mid_x = (start_x + end_x) / 2 + offset[0]
        mid_y = (start_y + end_y) / 2 + offset[1]
            
        plt.text(mid_x, mid_y, label, ha='center', va='center',
                fontsize=9, fontweight='bold',
                bbox=dict(boxstyle="round,pad=0.4", 
                facecolor='white', alpha=0.9, edgecolor='darkblue'))
    
    # Add title and formatting
    plt.title('Automatic Research System - Agent Workflow', 
              fontsize=20, fontweight='bold', pad=30)
    
    # Add legend with better positioning
    legend_elements = [
        mpatches.Patch(color='#FF6B6B', label='Planning & Strategy'),
        mpatches.Patch(color='#4ECDC4', label='Data Collection'),
        mpatches.Patch(color='#45B7D1', label='Content Review'),
        mpatches.Patch(color='#96CEB4', label='Data Processing'),
        mpatches.Patch(color='#FFEAA7', label='Quality Control'),
        mpatches.Patch(color='#DDA0DD', label='Deep Analysis')
    ]
    
    plt.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0.02, 0.98), 
              fontsize=11)
    
    # Set axis limits and remove axes (adjusted for larger layout)
    plt.xlim(-1, 13)
    plt.ylim(0, 8)
    plt.axis('off')
    
    # Add workflow description in a better position
    workflow_text = """Workflow Summary:
1. Planner creates research strategy
2. Researcher executes searches
3. Raw Content Reviewer evaluates quality
4. Extractor structures data
5. Structured Reviewer validates results
6. Deep Diver performs focused analysis"""
    
    plt.text(13.5, 4, workflow_text, fontsize=11, 
             bbox=dict(boxstyle="round,pad=0.6", facecolor='lightgray', alpha=0.9),
             verticalalignment='center')
    
    plt.tight_layout()
    return plt

def save_graph():
    """Create and save the agent graph as an image."""
    plt = create_agent_graph()
    
    # Save as PNG
    plt.savefig('agent_workflow_graph.png', dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    
    # Save as SVG for vector graphics
    plt.savefig('agent_workflow_graph.svg', bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    
    print("Agent workflow graph saved as:")
    print("- agent_workflow_graph.png (high-resolution image)")
    print("- agent_workflow_graph.svg (vector graphics)")
    
    # Display the graph
    plt.show()

if __name__ == "__main__":
    save_graph() 