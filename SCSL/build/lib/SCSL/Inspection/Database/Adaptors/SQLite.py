"""
Module that implements database logic for SQLite.
"""
import sqlite3


class Adaptor:

    def __init__(self, filename):
        # store the database filename
        self._filename = filename
        # initialise a connection
        self._connection = sqlite3.connect(self._filename)
        # get cursor
        self._cursor = self._connection.cursor()

    def query(self, query_string, *args):
        # execute query
        query = self._cursor.execute(query_string, args)
        # get result
        result = query.fetchall()
        return result

    def commit(self):
        self._connection.commit()