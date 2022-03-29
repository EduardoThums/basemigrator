# Base Migrator


## Installation

```
$ pip install basemigrator
```

## Example

```
# changelog.yaml

- file: Book/001-create-table-ddl.sql
- file: Author/001-create-table-ddl.sql
  context: dev, prod
```

```
$ python
>>> from migrator import migrate
>>> from flask import Flask
>>> from pathlib import Path
>>> app = Flask(__name__)
>>> changelog = f'Path(__file__).parent.absolute()}/migrations'
>>> migrate(app, changelog)
```

## TODO

- Improve documentation
- CI/CD to code linting
- Support different sql clients(postgres, sqlite3, etc)
- Contributing section
- tests/
