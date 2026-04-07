"""
Database Setup Script for Customer Success FTE

Usage:
    python setup_database.py --host localhost --port 5432 --user postgres --dbname fte_db

Requirements:
    - PostgreSQL 14+ installed and running
    - pgvector extension available
    - asyncpg installed: pip install asyncpg
"""

import asyncio
import asyncpg
import argparse
import os
from pathlib import Path


async def setup_database(host: str, port: int, user: str, password: str, dbname: str):
    """Set up the database with schema."""
    
    print(f"Connecting to PostgreSQL at {host}:{port}...")
    
    try:
        # First, connect to default database to create our database
        print("Connecting to PostgreSQL server...")
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database='postgres'  # Connect to default database first
        )
        
        # Check if database exists
        db_exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            dbname
        )
        
        if not db_exists:
            print(f"Creating database: {dbname}...")
            await conn.execute(f'CREATE DATABASE {dbname}')
            print(f"Database '{dbname}' created successfully.")
        else:
            print(f"Database '{dbname}' already exists.")
        
        await conn.close()
        
        # Now connect to our database
        print(f"Connecting to database '{dbname}'...")
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname
        )
        
        # Enable extensions
        print("Enabling extensions...")
        await conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
        print("Extensions enabled: vector, pgcrypto")
        
        # Read schema file
        schema_path = Path(__file__).parent / 'schema.sql'
        print(f"Reading schema from: {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Execute schema
        print("Applying schema...")
        await conn.execute(schema_sql)
        print("Schema applied successfully!")
        
        # Verify tables
        print("\nVerifying tables...")
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        print(f"\nCreated {len(tables)} tables:")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        # Verify views
        views = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.views 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        print(f"\nCreated {len(views)} views:")
        for view in views:
            print(f"  - {view['table_name']}")
        
        # Verify functions
        functions = await conn.fetch("""
            SELECT routine_name 
            FROM information_schema.routines 
            WHERE routine_schema = 'public' 
            AND routine_type = 'FUNCTION'
            ORDER BY routine_name
        """)
        
        print(f"\nCreated {len(functions)} functions:")
        for func in functions:
            print(f"  - {func['routine_name']}")
        
        # Verify knowledge base entries
        kb_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_base")
        print(f"\nKnowledge base entries: {kb_count}")
        
        # Verify channel configs
        channel_count = await conn.fetchval("SELECT COUNT(*) FROM channel_configs")
        print(f"Channel configurations: {channel_count}")
        
        await conn.close()
        
        print("\n" + "="*60)
        print("✅ Database setup completed successfully!")
        print("="*60)
        print(f"\nConnection string for application:")
        print(f"  postgresql://{user}:****@{host}:{port}/{dbname}")
        print("\nNext steps:")
        print("  1. Update connection string in your application config")
        print("  2. Insert knowledge base articles with embeddings")
        print("  3. Configure channel credentials in channel_configs")
        
    except asyncpg.exceptions.PostgresError as e:
        print(f"\n❌ PostgreSQL error: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure PostgreSQL is running: pg_ctl status")
        print("  2. Check pgvector is installed: psql -c \"SELECT * FROM pg_extension WHERE extname = 'vector'\"")
        print("  3. Verify credentials are correct")
        raise
    except FileNotFoundError as e:
        print(f"\n❌ Schema file not found: {e}")
        print(f"Expected schema at: {schema_path}")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description='Set up Customer Success FTE database')
    parser.add_argument('--host', default='localhost', help='PostgreSQL host')
    parser.add_argument('--port', type=int, default=5432, help='PostgreSQL port')
    parser.add_argument('--user', default='postgres', help='PostgreSQL user')
    parser.add_argument('--password', default=os.environ.get('POSTGRES_PASSWORD', ''), 
                        help='PostgreSQL password (or set POSTGRES_PASSWORD env var)')
    parser.add_argument('--dbname', default='fte_db', help='Database name to create')
    
    args = parser.parse_args()
    
    if not args.password:
        print("Warning: No password provided. Set POSTGRES_PASSWORD env var or use --password.")
    
    asyncio.run(setup_database(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        dbname=args.dbname
    ))


if __name__ == '__main__':
    main()
