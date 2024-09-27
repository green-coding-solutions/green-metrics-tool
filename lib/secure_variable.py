import json

class SecureVariable:
    def __init__(self, value):
        self._value = value

    def __repr__(self):
        return '****OBFUSCATED****'

    def __str__(self):
        return self.__repr__()

    def get_value(self):
        return self._value

class SecureVariableEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, SecureVariable):
            return repr(o)
        return super().default(o)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('variable', help='Please supply a variable')

    args = parser.parse_args()  # script will exit if arguments not present

    variable = SecureVariable(args.variable)
    print("Variable print output looks like this:", variable)
