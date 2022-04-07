# Base Migrator

[![PyPI](https://img.shields.io/pypi/v/basemigrator)](https://pypi.python.org/pypi/basemigrator)

Liquibase's almost compatible tool that works very similary, but just using only Python code.



## Installation

To use at a MySQL database:

```
$ pip install basemigrator[mysql]
```

To use at a PostgreSQL database:

```
$ pip install basemigrator[postgresql]
```

## Usage

There's basicly two rules to use this tool:

1. The changelog file MUST in the same folder as the migrations
2. The changelog file MUST follow the expected format specified in the documentation
3. The migration SQL file MUST have a set of metadata to be applied properly

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

```xml
<?xml version="1.0" encoding="UTF-8"?>

<databaseChangeLog>
  <include file="Table1/Table1-createtable.sql" relativeToChangelogFile="true" />
  <include file="Table2/Table2-createtable.sql" relativeToChangelogFile="dev, prod" />
</databaseChangeLog>
```

### YAML

```yaml
- file: Table1/Table1-createtable.sql
- file: Table2/Table2-createtable.sql
  context: dev, prod
```

The third rule specifies that the migration must have a set of metadata, which are:

```
--liquibase formatted sql
--changeset <author>:<migration-id>

CREATE TABLE Table1();
```

The configuration object passed as a parameter for the function that will execute the migrations should have a field named `config` that at least 
implements the `__get__()` method and have the following key-values:

```python
class App:

    def __init__(self):
        self.config = {
            'DB_USER': 'user', # the database user
            'DB_PASSWORD': 'password', # the database password
            'DB_HOST': 'localhost', # the database host
            'DB_DATABASE': 'foo' # the database name
        }
```

To call the `migrate()` function, three parameters must be given, they are:

```python
from basemigrator import migrate

migrate(
  app=app, # the app configuration object
  changelog='/path/to/migrations', # the full path of the migrations folder
  context='dev' # the context which the migrations will be applied
)
```


## Supported databases

- MySQL
- PostgreSQL

### PostgreSQL

Currently, procedures create statements are not supported.

## TODO

- CI/CD
  - code linting
  - publish package to pypi
- Contributing section
- tests/
