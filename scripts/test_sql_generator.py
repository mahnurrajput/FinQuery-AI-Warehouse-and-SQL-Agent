"""
test_sql_generator.py — Runs the SQL generator on test questions and prints
the SQL. It does NOT run the SQL against the database.

Run from the project root:
    python -m scripts.test_sql_generator
"""

import time

from app.sql_generator import generate_sql

QUESTIONS = [
    "What is the total number of transactions?",
    "What are the 5 highest transactions in July 2019 in Houston?",
    "How many transactions had an insufficient balance error?",
    "Which card brand has the highest fraud rate?",
    "Show the transactions for merchant 59935.",
    "What is the total spending in grocery stores?",
    "How many transactions happened in July 2024?",
]

# Pause between questions so the Groq per-minute token limit is not hit
PAUSE_SECONDS = 5


def main() -> None:
    for index, question in enumerate(QUESTIONS):
        if index:
            time.sleep(PAUSE_SECONDS)
        print("=" * 80)
        print("QUESTION:", question)
        result = generate_sql(question)
        if result.error:
            print("ERROR (no model answered):", result.error)
        elif result.cannot_answer:
            print("CANNOT ANSWER:", result.cannot_answer)
        else:
            print(result.sql)
        print()


if __name__ == "__main__":
    main()