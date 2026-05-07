"""
remove_draft.py - removes a draft from pending_drafts.json
Usage: python remove_draft.py <app_id>
"""
import sys
import json
from pathlib import Path

def main():
    app_id = int(sys.argv[1])
    drafts_file = Path(__file__).parent / 'pending_drafts.json'
    if not drafts_file.exists():
        print(f"[remove_draft] pending_drafts.json not found")
        return
    with open(drafts_file) as f:
        drafts = json.load(f)
    original_count = len(drafts)
    drafts = [d for d in drafts if d['id'] != app_id]
    with open(drafts_file, 'w') as f:
        json.dump(drafts, f, indent=2)
    print(f"[remove_draft] Removed app {app_id}. {original_count} -> {len(drafts)} drafts remaining")

if __name__ == '__main__':
    main()
