# Migrator


## Installation

```
$ pip install -e git+git@github.com:EduardoThums/migrator.git@main#egg=migrator
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
