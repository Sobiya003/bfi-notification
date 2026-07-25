import json, os
os.environ["STATE_FILE"] = "test_state.json"
if os.path.exists("test_state.json"): os.remove("test_state.json")
import bfi_odyssey_monitor as m

def run(items, first_run_alert=False):
    m.FIRST_RUN_ALERT = first_run_alert
    m.fetch_with_requests = lambda: items
    m.fetch_with_playwright = lambda: None
    print("---- run ----")
    m.main()

# Run 1: baseline (all sold out) -> should be silent
run([{"when":"Sunday 19 July 2026 20:20","venue":"BFI IMAX","status":"Sold out"},
     {"when":"Monday 20 July 2026 08:30","venue":"BFI IMAX","status":"Sold out"}])

# Run 2: a NEW screening added in August -> should ALERT
run([{"when":"Sunday 19 July 2026 20:20","venue":"BFI IMAX","status":"Sold out"},
     {"when":"Monday 20 July 2026 08:30","venue":"BFI IMAX","status":"Sold out"},
     {"when":"Saturday 22 August 2026 19:00","venue":"BFI IMAX","status":"Available"}])

# Run 3: no change -> silent
run([{"when":"Sunday 19 July 2026 20:20","venue":"BFI IMAX","status":"Sold out"},
     {"when":"Monday 20 July 2026 08:30","venue":"BFI IMAX","status":"Sold out"},
     {"when":"Saturday 22 August 2026 19:00","venue":"BFI IMAX","status":"Available"}])

# Run 4: a previously sold-out show becomes AVAILABLE -> should ALERT
run([{"when":"Sunday 19 July 2026 20:20","venue":"BFI IMAX","status":"Available"},
     {"when":"Monday 20 July 2026 08:30","venue":"BFI IMAX","status":"Sold out"},
     {"when":"Saturday 22 August 2026 19:00","venue":"BFI IMAX","status":"Available"}])

print("\nFinal state:", json.dumps(json.load(open("test_state.json"))["screenings"], indent=2))
os.remove("test_state.json")
