#!/usr/bin/env python3
"""
CCRA Prompt Cleanup Script

This script helps organize the prompts directory by:
1. Moving old GHGI prompts to a backup folder
2. Listing current CCRA prompts
3. Identifying missing CCRA prompt templates
"""

import os
import shutil
from pathlib import Path

def main():
    prompts_dir = Path("agents/prompts")
    backup_dir = Path("agents/backup_old_prompts")
    
    print("CCRA Prompt Cleanup Script")
    print("=" * 50)
    
    # Create backup directory
    backup_dir.mkdir(exist_ok=True)
    print(f"Created backup directory: {backup_dir}")
    
    # Define old GHGI prompts to move
    old_ghgi_prompts = [
        "afolu.md", "afolu_city.md",
        "ippu.md", "ippu_city.md", 
        "waste.md", "waste_city.md",
        "transportation.md", "transportation_city.md",
        "stationary_energy.md", "stationary_energy_city.md",
        "agent1_planner.md", "agent1_planner_english.md",
        "agent4_reviewer.md"
    ]
    
    # Move old prompts to backup
    moved_count = 0
    for prompt_file in old_ghgi_prompts:
        source = prompts_dir / prompt_file
        if source.exists():
            destination = backup_dir / prompt_file
            shutil.move(str(source), str(destination))
            print(f"Moved: {prompt_file} -> backup/")
            moved_count += 1
    
    print(f"\nMoved {moved_count} old GHGI prompts to backup")
    
    # List current CCRA prompts
    print("\nCurrent CCRA Prompts:")
    print("-" * 30)
    
    ccra_prompts = []
    for prompt_file in prompts_dir.glob("*.md"):
        if prompt_file.name not in old_ghgi_prompts:
            ccra_prompts.append(prompt_file.name)
            print(f"+ {prompt_file.name}")
    
    # Define all possible CCRA combinations
    hazards = ["heatwave", "drought", "flood", "landslide"]
    exposure = ["people", "buildings", "infrastructure", "agriculture", "economy"]
    vulnerability = ["socioeconomic", "health", "access_to_services", 
                    "environmental_buffers", "governance"]
    
    # Check for missing specific prompts
    print("\nMissing Specific CCRA Prompts:")
    print("-" * 35)
    
    missing_prompts = []
    
    for hazard in hazards:
        prompt_name = f"hazards_{hazard}.md"
        if prompt_name not in ccra_prompts:
            missing_prompts.append(prompt_name)
            print(f"- {prompt_name}")
    
    for exp in exposure:
        prompt_name = f"exposure_{exp}.md"
        if prompt_name not in ccra_prompts:
            missing_prompts.append(prompt_name)
            print(f"- {prompt_name}")
    
    for vuln in vulnerability:
        prompt_name = f"vulnerability_{vuln}.md"
        if prompt_name not in ccra_prompts:
            missing_prompts.append(prompt_name)
            print(f"- {prompt_name}")
    
    if not missing_prompts:
        print("All specific CCRA prompts are present!")
    
    # Summary
    print(f"\nSummary:")
    print(f"   • CCRA prompts found: {len(ccra_prompts)}")
    print(f"   • Missing specific prompts: {len(missing_prompts)}")
    print(f"   • Old GHGI prompts moved: {moved_count}")
    
    # Recommendations
    print(f"\nRecommendations:")
    if missing_prompts:
        print(f"   - Create high-priority missing prompts:")
        priority_prompts = [p for p in missing_prompts if any(x in p for x in 
                           ["flood", "drought", "people", "infrastructure", "health"])]
        for prompt in priority_prompts[:5]:  # Show top 5
            print(f"     - {prompt}")
    
    print(f"   - System will use ccra_planner.md as fallback for missing prompts")
    print(f"   - Test with: python main.py --mode hazards --which heatwave --country Germany")
    
    print(f"\nCleanup complete!")

if __name__ == "__main__":
    main()