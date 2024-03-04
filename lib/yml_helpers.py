#pylint: disable=too-many-ancestors

import yaml
import os
from lib import utils

class Loader(yaml.SafeLoader):
    def __init__(self, stream):
        # We need to find our own root as the Loader is instantiated in PyYaml
        self._root = os.path.split(stream.name)[0]
        super().__init__(stream)

    def include(self, node):
        # We allow two types of includes
        # !include <filename> => ScalarNode
        # and
        # !include <filename> <selector> => SequenceNode
        if isinstance(node, yaml.nodes.ScalarNode):
            nodes = [self.construct_scalar(node)]
        elif isinstance(node, yaml.nodes.SequenceNode):
            nodes = self.construct_sequence(node)
        else:
            raise ValueError("We don't support Mapping Nodes to date")

        filename = utils.join_paths(self._root, nodes[0], 'file')

        with open(filename, 'r', encoding='utf-8') as f:
            # We want to enable a deep search for keys
            def recursive_lookup(k, d):
                if k in d:
                    return d[k]
                for v in d.values():
                    if isinstance(v, dict):
                        return recursive_lookup(k, v)
                return None

            # We can use load here as the Loader extends SafeLoader
            if len(nodes) == 1:
                # There is no selector specified
                return yaml.load(f, Loader)

            return recursive_lookup(nodes[1], yaml.load(f, Loader))

Loader.add_constructor('!include', Loader.include)
