import os
from psycopg import Connection
from langgraph.checkpoint.postgres import PostgresSaver

def setup_langgraph_tables():
    """Создание таблиц checkpoints и writes для LangGraph"""
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    print("🔧 Connecting to PostgreSQL...")
    
    with Connection.connect(db_url, autocommit=True) as conn:
        print("🔧 Creating LangGraph tables...")
        
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
        
        print("✅ LangGraph tables (checkpoints, writes) created successfully!")

if __name__ == "__main__":
    setup_langgraph_tables()
