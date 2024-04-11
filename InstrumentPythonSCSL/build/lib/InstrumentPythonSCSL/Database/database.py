"""
Module holding logic for writing test/monitoring results to a database.

All of this is done through an adapter that implements a specific interface, but contains
logic specific to individual database types (SQLite, Postgres, etc.)
"""
import json
import os

import InstrumentPythonSCSL.Database.Adaptors as Adaptors

def initialise_database(connection):
    """
    Given a connection to a database, set up the tables defined by our schema.
    """
    # read in schema
    schema_queries = [
"""
create table test_suite_execution (
    id INTEGER PRIMARY KEY ASC,
    test_suite_name TEXT,
    start_time DATETIME
);""",
"""create table test_execution (
    id INTEGER PRIMARY KEY ASC,
    test_name TEXT,
    start_time DATETIME,
    test_suite_execution INTEGER,
    FOREIGN KEY (test_suite_execution) REFERENCES test_suite_execution(id)
);""",
"""create table monitoring_result (
    id INTEGER PRIMARY KEY ASC,
    specification INTEGER,
    truth_value TEXT,
    test_execution INTEGER,
    FOREIGN KEY (specification) REFERENCES specification(id),
    FOREIGN KEY (test_execution) REFERENCES test_execution(id)
);""",
"""create table specification (
    id INTEGER PRIMARY KEY ASC,
    dsl_type TEXT,
    dsl_text TEXT
);""",
"""create table atomic_constraint_check (
    id INTEGER PRIMARY KEY ASC,
    truth_value TEXT,
    atomic_constraint_index INTEGER,
    binding TEXT,
    monitoring_result INTEGER,
    FOREIGN KEY (monitoring_result) REFERENCES monitoring_result(id)
);""",
"""create table measurement (
    id INTEGER PRIMARY KEY ASC,
    measurement_value TEXT,
    expression_index INTEGER,
    module_name TEXT,
    line_number INTEGER,
    atomic_constraint_check INTEGER,
    FOREIGN KEY (atomic_constraint_check) REFERENCES atomic_constraint_check(id)
);"""
]
    # execute queries
    for query in schema_queries:
        connection.query(query)

def check_database(connection_data):
    """
    If the connection data given points to a local SQLite file, check for the file's existence.
    If it exists, ensure it contains all the tables we need.
    If it doesn't exist, create it with all the tables we need.
    """
    # check type of connection
    if connection_data["type"] == "sqlite":
        # check if file exists
        if os.path.exists(connection_data["filename"]):
            # check for tables being present
            # to do this, first initialise a connection, and query the table master of the db
            connection = Connection(connection_data).get_connection()
            tables = [
                "test_suite_execution",
                "test_execution",
                "monitoring_result",
                "specification",
                "atomic_constraint_check",
                "measurement"
            ]
            # initialise flag to indicate a table not being found
            table_not_found = False
            # check for the existence of each table in the database
            for table in tables:
                results = connection.query("select name from sqlite_master where type = 'table' and name = ?", table)
                if len(results) == 0:
                    table_not_found = True
                    break
            # if a table wasn't found, remove the database and start again
            if table_not_found:
                os.remove(connection_data["filename"])
                initialise_database(connection)
        else:
            print("No database file found - initialising a new one in 'results.db'.")
            # create database file
            with open(connection_data["filename"], "w") as h:
                pass
            # setup connection
            connection = Connection(connection_data).get_connection()
            # initialise the database
            initialise_database(connection)

class Connection:
    """
    Class containing logic for writing specific test/monitoring results to a database.
    """

    def __init__(self, connection_data):
        """
        Given `connection_data`, establish a database connection.
        """
        # store connection data
        self._connection_data = connection_data
        # initialise connection, depending on the type of the database
        if connection_data["type"] == "sqlite":
            self._connection = Adaptors.SQLite(connection_data["filename"])

    def get_connection(self):
        return self._connection

    def insert_specification(self, dsl_type, dsl_text):
        """
        Insert the given DSL text into the results database.
        """
        # check for presence of specification in database
        check = self._connection.query("select * from specification where dsl_text = ?", dsl_text)
        if len(check) == 0:
            query = "insert into specification (dsl_type, dsl_text) values (?, ?)"
            self._connection.query(query, dsl_type, dsl_text)
            self._connection.commit()

        # get id
        new_id = self._connection.query("select id from specification where dsl_text = ?", dsl_text)[0][0]
        return new_id

    def insert_test_suite_execution(self, test_suite_name, test_suite_start_time):
        """
        Insert a new test suite execution with the given name and start time.
        """
        self._connection.query(
            "insert into test_suite_execution (test_suite_name, start_time) values (?, ?)",
            test_suite_name,
            test_suite_start_time
        )
        self._connection.commit()
        # get the id of the new row
        new_id = self._connection.query(
            "select id from test_suite_execution where test_suite_name = ? and start_time = ?",
            test_suite_name,
            test_suite_start_time
        )[0][0]
        return new_id

    def insert_test_execution(self, test_name, test_start_time, test_suite_execution_id):
        """
        Insert a new test execution with the given name, start time and test suite execution id.
        """
        self._connection.query(
            "insert into test_execution (test_name, start_time, test_suite_execution) values (?, ?, ?)",
            test_name,
            test_start_time,
            test_suite_execution_id
        )
        self._connection.commit()
        # get the id of the new row
        new_id = self._connection.query("select id from test_execution where test_name = ? and start_time = ?",
                               test_name, test_start_time)[0][0]
        return new_id

    def insert_monitoring_results(self, monitoring_results, test_execution_id, spec_index_to_db_id):
        """
        Create the rows in the database to hold the monitoring results.

        These rows are in the test_execution, monitoring_result, specification, atomic_constraint_check,
        and measurement tables.
        """
        # iterate through specification indices
        for spec_index in monitoring_results:
            # get the db id of this specification
            spec_db_id = spec_index_to_db_id[spec_index]
            # get monitoring results for this spec
            spec_monitoring_results = monitoring_results[spec_index]
            # insert new monitoring_result row
            self._connection.query(
                "insert into monitoring_result (specification, truth_value, test_execution) values (?, ?, ?)",
                spec_db_id, spec_monitoring_results["verdict"], test_execution_id
            )
            self._connection.commit()

            # get new id of monitoring result
            monitoring_result_id = self._connection.query(
                "select id from monitoring_result where specification = ? and test_execution = ?",
                spec_db_id, test_execution_id
            )[0][0]

            # iterate through atomic constraint checks and insert each one, with its measurements
            # into the database
            for atomic_constraint_check_dict in \
                    spec_monitoring_results["atomic_constraint_checks"]:
                atomic_constraint_index = atomic_constraint_check_dict["atomic_constraint_index"]
                # turn binding into json string
                binding_json_string = json.dumps(atomic_constraint_check_dict["binding"])
                # insert atomic constraint check
                self._connection.query(
                    "insert into atomic_constraint_check "
                    "(truth_value, atomic_constraint_index, binding, monitoring_result) "
                    "values (?, ?, ?, ?)",
                    atomic_constraint_check_dict["truth_value"],
                    atomic_constraint_index,
                    binding_json_string,
                    monitoring_result_id
                )
                self._connection.commit()

                # get new atomic constraint id
                atomic_constraint_id = self._connection.query(
                    "select id from atomic_constraint_check "
                    "where monitoring_result = ? and binding = ? and atomic_constraint_index = ?",
                    monitoring_result_id,
                    binding_json_string,
                    atomic_constraint_index
                )[0][0]

                # insert measurements
                for expression_index, measurement_dict in enumerate(atomic_constraint_check_dict["measurements"]):
                    # insert measurement into dictionary
                    self._connection.query(
                        "insert into measurement "
                        "(measurement_value, expression_index, module_name, line_number, atomic_constraint_check) "
                        "values (?, ?, ?, ?, ?)",
                        str(measurement_dict["measurement_value"]),
                        expression_index,
                        measurement_dict["module_name"],
                        measurement_dict["line_number"],
                        atomic_constraint_id
                    )
                    self._connection.commit()
