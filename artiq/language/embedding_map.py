class EmbeddingMap:
    def __init__(self):
        self.object_inverse_map = {}
        self.object_map = {}
        self.string_map = {}
        self.string_reverse_map = {}
        self.function_map = {}
        self.attributes_writeback = []
        self.subkernel_map = {}
        self.subkernels = []
        self._sid_counter = 1

    def store_function(self, key, fun):
        self.function_map[key] = fun
        return key

    def store_object(self, obj):
        obj_id = id(obj)
        if obj_id in self.object_inverse_map:
            return self.object_inverse_map[obj_id]
        key = len(self.object_map) + 1
        self.object_map[key] = obj
        self.object_inverse_map[obj_id] = key
        return key

    def store_subkernel(self, destination, fun):
        sid = self._sid_counter
        self._sid_counter += 1
        self.subkernel_map[fun] = (destination, sid)
        return sid

    def store_str(self, s):
        if s in self.string_reverse_map:
            return self.string_reverse_map[s]
        key = len(self.string_map)
        self.string_map[key] = s
        self.string_reverse_map[s] = key
        return key

    def retrieve_function(self, key):
        return self.function_map[key]

    def retrieve_object(self, key):
        return self.object_map[key]

    def retrieve_str(self, key):
        return self.string_map[key]

    def retrieve_subkernel(self, fun):
        if fun not in self.subkernel_map:
            if hasattr(fun, "__self__"):
                dest, sid = self.subkernel_map.pop(fun.__func__)
                self.subkernel_map[fun] = dest, sid
        return self.subkernel_map[fun]
