"""Paginated command-line semantic memory search."""
from gotchi_vector import search_memory


def get_results(query, page=1, results_per_page=3):
    if page < 1 or not 1 <= results_per_page <= 25:
        raise ValueError("page >= 1 and page size 1-25 are required")
    end = page * results_per_page
    if end > 100:
        raise ValueError("Only the first 100 matches can be retrieved")
    results = search_memory(query, n=end)
    return results[end - results_per_page:end]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Search SecuriGotchi memories")
    parser.add_argument("query", help="Search phrase")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=3)
    args = parser.parse_args()
    for index, item in enumerate(get_results(args.query, args.page, args.page_size), 1):
        print(f"{index}. {item}")


if __name__ == "__main__":
    main()
