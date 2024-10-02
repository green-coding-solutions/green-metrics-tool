## What is in here?

The lib folder contains all scripts that are purely used as includes.

For instance `db.py` to connect to the database. It will never be invoked directly.

Some files may include a `__main__` guard clause and can also be directly executed. This is however only
to test the file manually and not the intended production use.