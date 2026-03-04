"""
Region detection with voting/consensus system.
Checks multiple database sources and picks the region with most votes.
"""

import os
from datetime import datetime

LOG_FILE = "region_debug.log"

def get_region_from_votes(db_entry):
    """
    Get the winning region based on database voting.
    Returns the region with the most votes (votes from multiple regional DBs).
    """
    if not db_entry:
        return ""
    
    votes = db_entry.get("_region_votes", {})
    if not votes:
        # Fallback to old _region field if votes not available
        return db_entry.get("_region", "")
    
    # Titles present in 3+ distinct regional databases are global releases
    if len(votes) >= 3:
        return "GLB"

    # Find region(s) with max votes
    max_votes = max(votes.values())
    winning_regions = [r for r, v in votes.items() if v == max_votes]

    # A tie means the title is equally present in multiple regional databases
    # → treat it as a global release rather than arbitrarily picking one region
    if len(winning_regions) > 1:
        return "GLB"

    return winning_regions[0]

def log_region_lookup(filename, tid, base_tid, db_entry, region_base, region_final):
    """Log detailed region lookup with voting information."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {filename}\n")
            f.write(f"  Title ID: {tid}\n")
            f.write(f"  Base TID: {base_tid}\n")
            f.write(f"  DB has entry: {bool(db_entry)}\n")
            
            if db_entry:
                votes = db_entry.get("_region_votes", {})
                regions = db_entry.get("_regions", [])
                if votes:
                    f.write(f"  Region votes: {votes}\n")
                    f.write(f"  Regions available: {', '.join(regions)}\n")
                else:
                    f.write(f"  DB region (no votes): '{db_entry.get('_region', '')}'\n")
            
            f.write(f"  FINAL REGION: '{region_final}'\n")
    except Exception as e:
        print(f"Failed to write region debug log: {e}")

def clear_log():
    """Clear old log on startup."""
    try:
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
    except Exception:
        pass
