# Base Migrator

[![PyPI](https://img.shields.io/pypi/v/basemigrator)](https://pypi.python.org/pypi/basemigrator)

Liquibase's almost compatible tool that works very similary, but just using only Python code.



## Installation

```
$ pip install basemigrator
```

## Usage

There's basicly two rules to use this tool:

1. The changelog file MUST in the same folder as the migrations
2. The changelog file MUST follow the expected format specified in the documentation

About the first rule, it's simple, follow this folder structure and you will be fine:

```
migrations/
├── changelog.xml
├── Table1
│   └── Table1-createtable.sql
└── Table2
    └── Table2-createtable.sql
```

The second rule applies for the changelog file format, which depending on her extension, MUST be one of these two:

### XML

```
<?xml version="1.0" encoding="UTF-8"?>

<databaseChangeLog>
  <include file="Table1/Table1-createtable.sql" relativeToChangelogFile="true" />
  <include file="Table2/Table2-createtable.sql" relativeToChangelogFile="dev, prod" />
</databaseChangeLog>
```

### YAML

```
- file: Table1/Table1-createtable.sql
- file: Table2/Table2-createtable.sql
  context: dev, prod
```

## TODO

- Improve documentation
- CI/CD to code linting
- Support different sql clients(postgres, sqlite3, etc)
- Contributing section
- tests/
