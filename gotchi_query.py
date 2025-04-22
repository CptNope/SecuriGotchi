from gotchi_vector import search_memory
import sys

if len(sys.argv) < 2:
    print("Usage: python gotchi_query.py 'query'")
    exit()

def get_results(query, top_k=3, page=1, results_per_page=3):
    all_results = vector_store.query(query, top_k=top_k*page)
    start_idx = (page-1) * results_per_page
    end_idx = start_idx + results_per_page
    return all_results[start_idx:end_idx]

query = " ".join(sys.argv[1:])
results = search_memory(query)
print("🔍 Gotchi Memory Matches:")
for i, r in enumerate(results, 1):
    print(f"{i}. {r}")