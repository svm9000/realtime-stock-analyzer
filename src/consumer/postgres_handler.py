import psycopg2
from psycopg2.extras import execute_values
from typing import List, Dict
import os
import json
from src.logger import get_logger  # Use centralized logger


class PostgresHandler:
    def __init__(self, host: str = "postgres", port: int = 5432, user: str = "postgres", password: str = "postgres", dbname: str = "stock_data") -> None:
        """
        Initialize the PostgreSQL connection and cursor.
        """
        self.logger = get_logger(self.__class__.__name__)  # Use centralized logger
        try:
            self.connection = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=dbname
            )
            self.cursor = self.connection.cursor()
            self.logger.info(f"Connected to PostgreSQL at {host}:{port}, Database: {dbname}")
        except psycopg2.Error as e:
            self.logger.error(f"Failed to connect to PostgreSQL at {host}:{port}, Database: {dbname}. Error: {e}")
            raise

    def create_table(self, schema_file: str = "src/consumer/sql/schema.sql") -> None:
        """
        Create a table for storing stock data if it doesn't exist.
        Reads the SQL schema from an external file.
        """
        try:
            if not os.path.exists(schema_file):
                raise FileNotFoundError(f"Schema file '{schema_file}' not found.")

            with open(schema_file, "r") as file:
                schema = file.read()

            self.cursor.execute(schema)
            self.connection.commit()
            self.logger.info(f"Table created or already exists using schema file: {schema_file}")
        except Exception as e:
            self.logger.error(f"Failed to create table using schema file '{schema_file}'. Error: {e}")
            raise

    def insert_messages(self, messages: List[Dict[str, Dict]], query_file: str = "src/consumer/sql/insert_messages.sql") -> None:
        """
        Insert multiple messages into the database.
        Reads the SQL query from an external file.
        """
        try:
            if not os.path.exists(query_file):
                raise FileNotFoundError(f"Query file '{query_file}' not found.")

            with open(query_file, "r") as file:
                query = file.read()

            # Adjust the values to match the actual message structure
            values = [(msg['symbol'], json.dumps(msg)) for msg in messages]
            execute_values(self.cursor, query, values)
            self.connection.commit()
            self.logger.info(f"Inserted {len(messages)} messages into the database.")
        except Exception as e:
            self.logger.error(f"Failed to insert messages into the database. Error: {e}")
            raise

    def close(self) -> None:
        """
        Close the database connection.
        """
        try:
            self.cursor.close()
            self.connection.close()
            self.logger.info("Closed the PostgreSQL connection.")
        except Exception as e:
            self.logger.error(f"Failed to close the PostgreSQL connection. Error: {e}")