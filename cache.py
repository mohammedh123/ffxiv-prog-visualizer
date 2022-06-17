import json
import jsonpickle

from abc import ABC, abstractmethod
from pathlib import Path


class Cache(ABC):
    @abstractmethod
    def get(self, key):
        raise NotImplementedError

    @abstractmethod
    def set(self, key, val):
        raise NotImplementedError

    @abstractmethod
    def commit(self):
        raise NotImplementedError
        
        
class JsonFileCache(Cache):
    def __init__(self, filename):
        self.filename = filename
        
        try:
            with open(filename) as f:
                self.cache = json.load(f)
        except ValueError:
            self.cache = {}
        except FileNotFoundError:
            with open(filename, 'w+') as f:
                f.write('{}')
            self.cache = {}
            
    def get(self, key):
        val = self.cache.get(key, None)
        if val:
            val = jsonpickle.decode(val)
        return val
        
    def set(self, key, val):
        self.cache[key] = jsonpickle.encode(val)
    
    def commit(self):
        with open(self.filename, 'w') as f:
            json.dump(self.cache, f)