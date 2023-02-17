#pylint: disable=no-member
import random
import string

from db import DB

def randomword(length):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

## Is there a better place for this function to live?
def get_pid(project_name):
    query = """
            SELECT
                id
            FROM
                projects
            WHERE name = %s
            """
    data = DB().fetch_one(query, (project_name, ))
    if (data is None or data == []):
        return None

    return data[0]

## Parse a string so that the first letter, and any letter after a _, is capitalized
## E.g. 'foo_bar' -> 'FooBar'
def get_pascal_case(in_string):
    return ''.join([s.capitalize() for s in in_string.split('_')])

def get_metric_providers(config):
    metric_providers_keys = config['measurement']['metric-providers'].keys()
    return [(m.split('.')[-1]) for m in metric_providers_keys]
