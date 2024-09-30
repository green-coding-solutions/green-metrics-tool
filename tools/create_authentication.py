## A user in the GMT is used to restrict access to certain routes, data-retentions, optimizations, machines etc.
## In order to deliver this functionality a capability dictionary is created by this script that is then filled
## into the `users` table
## By default a "DEFAULT" user is created which has unlimited access to all machines and routes.
##
## However since you will be adding machines and optimizations etc. to the GMT you need a dynamic mechanism to update
## the capabilities dictionary and also add new users with restricted capabilities.
##
## This is the default dictionary created:
# {
#     "api": {
#         "quotas": { # An empty dictionary here means that no quotas apply
#         },
#         "routes": [ # This will be dynamically loaded from the current main.py
#             "/v1/carbondb/add",
#             "/v1/ci/measurement/add",
#             "/v1/software/add",
#             "/v1/hog/add"
#         ]
#     },
#     "measurement": {
#         "flow-process-duration": 3600,
#         "total-duration": 3600
#     },
#     "data": {
#         "runs": {
#             "retention": 3600,
#         },
#         "measurements": {
#             "retention": 3600,
#         },
#         "ci_measurements": {
#             "retention": 3600,
#         },
#         "hog_measurements": {
#             "retention": 3600,
#         },
#         "hog_coalitions": {
#             "retention": 3600,
#         },
#         "hog_tasks": {
#             "retention": 3600,
#         },
#     },
#     "machines": [ # This will be dynamically loaded from the current database
#         1,
#     ],
#     "optimizations": [ # This will be dynamically loaded from the current filesystem
#         "container_memory_utilization",
#         "container_cpu_utilization",
#         "message_optimization",
#         "container_build_time",
#         "container_boot_time",
#         "container_image_size",
#     ],
# }

import ast

def parse_fastapi_routes(file_path):
    with open(file_path, 'r') as file:
        content = file.read()

    # Parse the content into an AST
    tree = ast.parse(content)

    routes = []

    # Function to extract the path from a decorator
    def extract_path(decorator):
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
            if decorator.func.attr in ['post']:
                # Check if there's at least one argument
                if decorator.args:
                    # The first argument should be the path
                    path_arg = decorator.args[0]
                    if isinstance(path_arg, ast.Constant):
                        return decorator.func.attr.upper(), path_arg.value
        return None

    # Traverse the AST
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            for decorator in node.decorator_list:
                result = extract_path(decorator)
                if result:
                    method, path = result
                    routes.append((method, path))

    return routes



if __name__ == '__main__':

    # parser = argparse.ArgumentParser()
    # parser.add_argument('filename', type=str)

    # parser.add_argument('run_id', type=str)
    # parser.add_argument('db_host', type=str)
    # parser.add_argument('db_pw', type=str)


    # Example usage
    file_path = '/Users/arne/Sites/green-coding/green-metrics-tool/api/main.py'
    routes = parse_fastapi_routes(file_path)

    # Print the routes
    for method, path in routes:
        print(f"{method}: {path}")

## TODO
#    - Set quotas for routes
#    - Set restrictions to machines
#    - Update a user maybe when a new machine gets added?
#    - Insert a new machine script? Then also add this machine to every user?

