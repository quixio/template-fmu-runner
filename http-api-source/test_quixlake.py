"""
QuixLake SDK Test Application
Tests connection and basic operations with the QuixLake data lake API.
"""
import os
from quixlake import QuixLakeClient

# Configuration - set these via environment variables or replace directly
QUIXLAKE_API_URL = os.environ.get("QUIXLAKE_API_URL", "https://quixlake-quixers-quixlakev2timeseries-prod.az-france-0.app.quix.io")
QUIXLAKE_TOKEN = os.environ.get("QUIXLAKE_TOKEN", "")


def test_connection():
    """Test basic connection and list available tables."""
    print("=" * 60)
    print("QuixLake SDK Test Application")
    print("=" * 60)

    print(f"\nConnecting to: {QUIXLAKE_API_URL}")

    with QuixLakeClient(base_url=QUIXLAKE_API_URL, token=QUIXLAKE_TOKEN) as client:
        # Test 1: List tables
        print("\n[1] Listing available tables...")
        try:
            tables = client.get_tables()
            print(f"    Found {len(tables)} table(s):")
            for table in tables:
                print(f"      - {table}")
        except Exception as e:
            print(f"    Error listing tables: {e}")
            return

        if not tables:
            print("    No tables found. Exiting.")
            return

        # Test 2: Get partition info for first table
        first_table = tables[0]
        print(f"\n[2] Getting partition info for '{first_table}'...")
        try:
            partition_info = client.get_partition_info(first_table)
            print(f"    Partition structure: {partition_info}")
        except Exception as e:
            print(f"    Error getting partition info: {e}")

        # Test 3: Query sample data from first table
        print(f"\n[3] Querying sample data from '{first_table}'...")
        try:
            df = client.query(f"SELECT * FROM {first_table} LIMIT 10")
            print(f"    Retrieved {len(df)} row(s)")
            if not df.empty:
                print(f"    Columns: {list(df.columns)}")
                print("\n    Sample data:")
                print(df.to_string(index=False, max_colwidth=50))
        except Exception as e:
            print(f"    Error querying data: {e}")

        # Test 4: Count rows in first table
        print(f"\n[4] Counting rows in '{first_table}'...")
        try:
            count_df = client.query(f"SELECT COUNT(*) as total FROM {first_table}")
            total = count_df['total'].iloc[0] if not count_df.empty else 0
            print(f"    Total rows: {total}")
        except Exception as e:
            print(f"    Error counting rows: {e}")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


def interactive_query():
    """Interactive query mode for exploration."""
    print("\nInteractive Query Mode")
    print("Type 'exit' to quit, 'tables' to list tables\n")

    with QuixLakeClient(base_url=QUIXLAKE_API_URL, token=QUIXLAKE_TOKEN) as client:
        while True:
            try:
                query = input("SQL> ").strip()

                if not query:
                    continue
                if query.lower() == 'exit':
                    break
                if query.lower() == 'tables':
                    tables = client.get_tables()
                    print(f"Tables: {tables}\n")
                    continue

                df = client.query(query)
                print(df.to_string(index=False))
                print(f"\n({len(df)} rows)\n")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}\n")


if __name__ == "__main__":
    import sys

    # Validate configuration
    if "<YOUR_" in QUIXLAKE_API_URL or "<YOUR_" in QUIXLAKE_TOKEN:
        print("Error: Please configure QUIXLAKE_API_URL and QUIXLAKE_TOKEN")
        print("Either set environment variables or edit this script directly.")
        sys.exit(1)

    # Run tests or interactive mode
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_query()
    else:
        test_connection()
