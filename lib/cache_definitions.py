from cachetools import TTLCache, Cache

class NoNoneOrNegativeValuesCache(TTLCache):
    def __setitem__(self, key, value, cache_setitem=Cache.__setitem__):
        if value and value != -1 and value != (None, None):  # Only cache valid values
            super().__setitem__(key, value, cache_setitem)
