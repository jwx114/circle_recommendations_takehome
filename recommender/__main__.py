import argparse
import json
import sys

from recommender import recommend
from recommender.config import DEFAULT_K

def main (argv=None):
    parser = argparse.ArgumentParser(prog="python -m recommender", description="Recommend Circles for a user.")
    parser.add_argument("user_id", type=int, help="id of user to recommend for")
    parser.add_argument("-k", type=int, default=DEFAULT_K, help=f"number of results (default {DEFAULT_K})")
    parser.add_argument("--json", action="store_true", help="output results in JSON format")
    args = parser.parse_args(argv)

    if args.k < 1:
        parser.error("-k must be at least 1")
    try:
        results = recommend(args.user_id, k=args.k)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(results))
        return 0

    if not results:
        print(f"No eligible circles found for user {args.user_id}")
        return 0

    print(f"Top {len(results)} circles for user {args.user_id}:\n")
    for rank, circle in enumerate(results, start=1):
        print(f"{rank}. {circle['name']} (#{circle['circle_id']}, {circle['topic'] or 'no topic'}) score {circle['score']:.3f}")
        print(f" {', '.join(circle['reasons']) or '-'}")
    return 0

if __name__ == "__main__":
      sys.exit(main())