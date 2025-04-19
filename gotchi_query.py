from gotchi_vector import search_memory
import sys

if len(sys.argv) < 2:
    print("Usage: python gotchi_query.py 'query'")
    exit()

query = " ".join(sys.argv[1:])
results = search_memory(query)
print("🔍 Gotchi Memory Matches:")
for i, r in enumerate(results, 1):
    print(f"{i}. {r}")