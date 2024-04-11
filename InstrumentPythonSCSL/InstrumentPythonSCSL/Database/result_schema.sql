create table test_suite_execution (
    id INTEGER PRIMARY KEY ASC,
    test_suite_name TEXT,
    start_time DATETIME
);

create table test_execution (
    id INTEGER PRIMARY KEY ASC,
    test_name TEXT,
    start_time DATETIME,
    test_suite_execution INTEGER,
    FOREIGN KEY (test_suite_execution) REFERENCES test_suite_execution(id)
);

create table monitoring_result (
    id INTEGER PRIMARY KEY ASC,
    specification INTEGER,
    truth_value TEXT,
    test_execution INTEGER,
    FOREIGN KEY (specification) REFERENCES specification(id),
    FOREIGN KEY (test_execution) REFERENCES test_execution(id)
);

create table specification (
    id INTEGER PRIMARY KEY ASC,
    dsl_type TEXT,
    dsl_text TEXT
);

create table atomic_constraint_check (
    id INTEGER PRIMARY KEY ASC,
    truth_value TEXT,
    atomic_constraint_index INTEGER,
    binding TEXT,
    monitoring_result INTEGER,
    FOREIGN KEY (monitoring_result) REFERENCES monitoring_result(id)
);

create table measurement (
    id INTEGER PRIMARY KEY ASC,
    measurement_value TEXT,
    expression_index INTEGER,
    module_name TEXT,
    line_number INTEGER,
    atomic_constraint_check INTEGER,
    FOREIGN KEY (atomic_constraint_check) REFERENCES atomic_constraint_check(id)
);