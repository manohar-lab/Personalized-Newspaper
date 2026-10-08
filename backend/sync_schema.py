import asyncio
from sqlalchemy import text, inspect
from app.database.session import engine, AsyncSessionLocal
from app.models.base import Base
import app.models  # load all models into Base.metadata

async def sync_schema():
    async with engine.begin() as conn:
        # Create all tables that don't exist yet
        await conn.run_sync(Base.metadata.create_all)
        
        # Check for missing columns in existing tables and add them
        def inspect_and_add_columns(sync_conn):
            inspector = inspect(sync_conn)
            existing_tables = inspector.get_table_names()
            
            for table_name, table in Base.metadata.tables.items():
                if table_name in existing_tables:
                    existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
                    for col in table.columns:
                        if col.name not in existing_cols:
                            # Generate simple ALTER TABLE statement
                            col_type = col.type.compile(sync_conn.dialect)
                            nullable = "NULL" if col.nullable else "NOT NULL"
                            default_clause = ""
                            if col.server_default is not None:
                                default_clause = f" DEFAULT {col.server_default.arg}"
                            elif col.default is not None and hasattr(col.default, 'arg') and not callable(col.default.arg):
                                default_val = col.default.arg
                                if isinstance(default_val, str):
                                    default_clause = f" DEFAULT '{default_val}'"
                                elif isinstance(default_val, (int, float, bool)):
                                    default_clause = f" DEFAULT {str(default_val).upper()}"
                            
                            stmt = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {col_type} {default_clause};'
                            print(f"Adding missing column: {stmt}")
                            try:
                                sync_conn.execute(text(stmt))
                            except Exception as e:
                                print(f"Error adding column {col.name} to {table_name}: {e}")

        await conn.run_sync(inspect_and_add_columns)

if __name__ == "__main__":
    asyncio.run(sync_schema())
