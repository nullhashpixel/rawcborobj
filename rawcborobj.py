#!/usr/bin/env python3
import copy

class rawcborobj:
    def __init__(self, data, lazy=False, tag=None, cursor=0, debug=False):
        self.data = [data]
        self.lazy = lazy
        self.length = -1
        self.cursor = cursor
        self.tag = tag
        self.next_obj_cache = {}
        self.next_obj_cache_pre = {}
        self.indef_array_length_cache = {}
        self.tag_cache = {}
        self.debug = debug

        self.reset_state()

        if not lazy:
            self.read_header()

    def reset_state(self):
        self.initialized = False
        self.value = None
        self.length = None
        self.array_length = None
        self.remainder = None
        self.stop = False
        self.map = False
        self.undefined = False
        self.eof = False
        self.children = None
        self.indefinite_length = False
        self.pre_tag_cursor=None

    # cache of object end positions for objects starting at cursor
    def _cache_end_pos(self):
        self.next_obj_cache[self.cursor] = self.remainder.cursor
        self.next_obj_cache_pre[self.cursor] = self.remainder.pre_tag_cursor

    # move remainder pointer to end position of object or return False if not in cache
    # if not in cache, object specific transversal code is needed
    def _restore_end_pos(self):
        if self.cursor in self.next_obj_cache:
            self.remainder.pre_tag_cursor = self.next_obj_cache_pre[self.cursor]
            self.remainder.set_cursor(self.next_obj_cache[self.cursor])
            #self.remainder.tag = self.tag_cache.get(self.cursor)
            return True
        return False

    def _cache_indef_array_length(self):
        self.indef_array_length_cache[self.cursor] = self.array_length

    def _restore_indef_array_length(self):
        self.array_length = self.indef_array_length_cache[self.cursor]

    def copy(self):
        return copy.copy(self)

    def copy_at(self, cursor):
        _copy = self.copy().set_cursor(cursor)
        _copy.initialized = False
        return _copy

    def rel_copy_at(self, rel_cursor):
        return self.copy_at(self.cursor + rel_cursor)

    def set_cursor(self, cursor):
        self.cursor = cursor
        return self

    def next(self):
        if self.remainder is not None:
            self.cursor = self.remainder.cursor
            self.read_header()
        else:
            raise Exception("invalid")

    def move(self, n):
        self.cursor += n
        self.read_header()

    def rel_data(self, offset, length):
        return self.data[0][self.cursor+offset:self.cursor+offset+length]

    def read_header(self):
        self.tag = None

        self.reset_state()
        data = self.data[0]
        if len(data) < 1:
            return None

        if self.cursor >= len(data):
            self.eof = True
            return None

        x = data[self.cursor]

        if x >= 0xc0 and x < 0xd8:
            self.length = 1
            tag = x-0xc0
            self.tag = tag
            self.pre_tag_cursor = self.cursor 
            self.cursor += 1
            self.tag_cache[self.cursor] = self.tag
            x = data[self.cursor]
        elif x >= 0xd8 and x <= 0xda:
            self.length = 1 << (x-0xD8)
            tag = int.from_bytes(self.rel_data(1, self.length), "big")
            self.tag = tag
            self.pre_tag_cursor = self.cursor 
            self.cursor += 1 + self.length
            self.tag_cache[self.cursor] = self.tag

            x = data[self.cursor]

        if self.cursor in self.tag_cache:
            self.tag = self.tag_cache[self.cursor]

        if self.debug and self.tag is not None:
            print(f"found TAG: {self.tag} (0x{self.tag:04x})")
        if self.debug:
            print(f"next object is 0x{x:02x}")


        if x >= 0x00 and x <= 0x17:
            self.length = 1
            self.value = x
            self.remainder = self.rel_copy_at(1)
        elif x >= 0x18 and x <= 0x1b:
            self.length = 1 << (x-0x18)
            self.value = int.from_bytes(self.rel_data(1, self.length), "big")
            self.remainder = self.rel_copy_at(1+self.length)
        elif x >= 0x20 and x < 0x37:
            self.length = 1
            self.value = -1-(x-0x20)
            self.remainder = self.rel_copy_at(1)
        elif x >= 0x38 and x <= 0x3b:
            self.length = 1 << (x-0x38)
            self.value = -1-int.from_bytes(self.rel_data(1, self.length), "big")
            self.remainder = self.rel_copy_at(1+self.length)
        elif x >= 0x40 and x <= 0x57:
            self.length = 1
            array_length = x-0x40
            self.value  = self.rel_data(1, array_length)
            self.remainder = self.rel_copy_at(1+array_length)
            if self.debug:
                print("read bytestring ", self.rel_data(1, array_length).hex())
        elif x >= 0x58 and x <= 0x5e:
            self.length = 1 << (x-0x58)
            array_length = int.from_bytes(self.rel_data(1, self.length), "big")
            self.value = self.rel_data(1+self.length, array_length)
            self.remainder = self.rel_copy_at(1+self.length+array_length)
            if self.debug:
                print("read bytestring ", self.rel_data(1+self.length, array_length).hex())
        elif x== 0x5f:
            self.length = 1
            self.array_length = 0
            self.indefinite_length = True
            self.remainder = self.rel_copy_at(1)
            while not self.remainder.stop:
                self.remainder.next()
                self.array_length += 1
            self.remainder.next()
        elif x >= 0x60 and x <= 0x77:
            self.length = 1
            self.array_length = x-0x60
            self.value  = self.rel_data(1, self.array_length).decode('utf-8')
            self.remainder = self.rel_copy_at(1+self.array_length)
        elif x >= 0x78 and x <= 0x7e:
            self.length = 1 << (x-0x78)
            self.array_length = int.from_bytes(self.rel_data(1, self.length), "big")
            self.value = self.rel_data(1+self.length, self.array_length).decode('utf-8')
            self.remainder = self.rel_copy_at(1+self.length+self.array_length)
        elif x== 0x7f:
            self.length = 1
            self.array_length = 0
            self.indefinite_length = True
            self.children = self.rel_copy_at(1)
            self.children.read_header()
            self.remainder = copy.copy(self.children)
            while not self.remainder.stop:
                self.remainder.next()
                self.array_length += 1
            self.remainder.next()
        elif x >= 0x80 and x <= 0x97:
            self.length = 1
            self.array_length = x-0x80
            if self.debug:
                print(f"array found @ {self.cursor}, length = {self.array_length}")
            self.children = self.rel_copy_at(1)
            self.children.read_header()
            self.remainder = copy.copy(self.children)
            if not self._restore_end_pos():
                for i in range(self.array_length):
                    self.remainder.next()
                self._cache_end_pos()
        elif x >= 0x98 and x <= 0x9A:
            self.length = 1 << (x-0x98)
            self.array_length = int.from_bytes(self.rel_data(1, self.length), "big")
            if self.debug:
                print(f"array found @ {self.cursor}, length = {self.array_length}")
            self.children = self.rel_copy_at(1+self.length)
            self.children.read_header()
            self.remainder = copy.copy(self.children)
            if not self._restore_end_pos():
                for i in range(self.array_length):
                    self.remainder.next()
                self._cache_end_pos()
        elif x== 0x9f:
            self.length = 1
            self.array_length = 0
            self.children = self.rel_copy_at(1)
            self.children.read_header()
            self.remainder = copy.copy(self.children)
            self.indefinite_length = True
            if not self._restore_end_pos():
                while not self.remainder.stop:
                    self.remainder.next()
                    self.array_length += 1
                # move 1 object behind the stop marker (0xff), but don't count it towards the array length
                self.remainder.next()
                self._cache_end_pos()
                self._cache_indef_array_length()
            else:
                self._restore_indef_array_length()
        elif x >= 0xA0 and x < 0xB8:
            self.length = 1
            self.array_length = x-0xA0
            self.map = True
            self.children = self.rel_copy_at(1)
            self.children.read_header()
            self.remainder = copy.copy(self.children)
            for i in range(self.array_length*2):
                self.remainder.next()
        elif x >= 0xB8 and x <= 0xBA:
            self.length = 1 << (x-0xB8)
            self.array_length = int.from_bytes(self.rel_data(1, self.length), "big")
            self.map = True
            self.children = self.rel_copy_at(1+self.length)
            self.children.read_header()
            self.remainder = copy.copy(self.children)
            for i in range(self.array_length*2):
                self.remainder.next()
        #elif x >= 0xd8 and x <= 0xda:
        #    self.length = 1 << (x-0xD8)
        #    tag = int.from_bytes(self.rel_data(1, self.length), "big")
        #    pre_tag_cursor = self.cursor
        #    self.move(1+self.length)
        #    self.tag = tag
        #    self.pre_tag_cursor = pre_tag_cursor
        #    self.remainder.read_header()
        #    #print("SET ", self.tag, self.pre_tag_cursor)
        elif x == 0xf4:
            self.length = 1
            self.value = False
            self.remainder = self.rel_copy_at(1)
        elif x == 0xf5:
            self.length = 1
            self.value = True
            self.remainder = self.rel_copy_at(1)
        elif x == 0xf6:
            self.length = 1
            self.value = None
            self.remainder = self.rel_copy_at(1)
        elif x == 0xf7:
            self.length = 1
            self.value = None
            self.undefined = True
            self.remainder = self.rel_copy_at(1)
        elif x == 0xff:
            self.length = 1
            self.stop = True
            self.remainder = self.rel_copy_at(1)
        else:
            surrounding_bytes = "..." + self.data[0][self.cursor-16:self.cursor].hex() + "\x1b[31m" + self.data[0][self.cursor:self.cursor+16].hex() + "\x1b[0m..."
            raise Exception(f"Not implemented: {x} = 0x{x:02x} @ {self.cursor} {surrounding_bytes}")

        self.initialized = True

    def __len__(self):
        if not self.initialized:
            self.read_header()
        return self.array_length

    def __getattribute__(self, name):
        if name == "value":
            if not self.initialized:
                self.read_header()
            if not self.map and self.array_length is not None:
                length = len(self)
                res = []
                for i in range(length):
                    res.append(self[i].value)
                return res
            elif self.map and self.array_length is not None:
                keys = self.keys()
                res = {}
                for key in keys:
                    res[key] = self[key].value
                return res



        return object.__getattribute__(self, name)

    def __getitem__(self, key):

        if not self.initialized:
            self.read_header()

        if type(key) == tuple and len(key) > 1:
            return self[key[0]][key[1:]]
        else:
            if type(key) == tuple:
                key = key[0]

            # --- LIST LOOKUP ---
            if not self.map and self.array_length is not None:
                x = self.children.copy()
                for i in range(key):
                    x.next()
                return x

            # --- MAP LOOKUP ---
            elif self.map and self.array_length is not None:
                x = self.children.copy() 
                for i in range(self.array_length):
                    if type(key) == type(self):
                        if x.bytes() == key.bytes():
                            x.next()
                            return x
                    elif type(key) == bytes:
                        if x.bytes() == key:
                            x.next()
                            return x
                    elif type(key) == str:
                        if x.encoded() == key:
                            x.next()
                            return x
                    elif x.value == key:
                        x.next()
                        return x
                    x.next()
                    x.next()
                raise Exception("KeyError")


    def keys(self):
        if self.map and self.array_length is not None:
            _keys = []
            x = self.children.copy()
            for i in range(self.array_length):
                _keys.append(x.copy())
                x.next()
                x.next()
            return _keys

        else:
            raise Exception("Not a map")

    def keys_bytes(self):
        _keys = self.keys()
        return [x.bytes() for x in _keys] if _keys is not None else None

    def keys_encoded(self):
        _keys = self.keys()
        return [x.encoded() for x in _keys] if _keys is not None else None

    def encode_tag(self, tag):
        if tag < 256:
            return bytes([0xD8, tag])
        else:
            return bytes([0xD8]) + tag.to_bytes((tag.bit_length() + 7) // 8, 'big') or b'\0'

    def bytes(self):
        if self.tag is not None:
            tag_bytes = self.encode_tag(self.tag)
            return tag_bytes + self.data[0][self.cursor:(self.remainder.pre_tag_cursor if self.remainder.pre_tag_cursor is not None else self.remainder.cursor) if self.remainder is not None else None]

        else:
            return self.data[0][self.cursor:self.remainder.cursor if self.remainder is not None else None]

    def encoded(self):
        return self.bytes().hex()

    def __int__(self):
        if not self.initialized:
            self.read_header()

        if type(self.value) is int:
            return self.value

    def __add__(self, other):
        if type(self.value) is int:
            return int(self) + int(other)
        elif type(self.value) is bytes and type(self) == type(other) and type(other.value) is bytes:
            return self.value + other.value
        elif type(self.value) is bytes and type(other) == bytes:
            return self.value + other
        else:
            raise Exception("TypeError")

    def __radd__(self, other):
        if type(self.value) is int:
            return int(self) + int(other)
        elif type(self.value) is bytes and type(other.value) is bytes:
            return other.value + self.value
        else:
            raise Exception("TypeError")

    def __sub__(self, other):
        if not self.initialized:
            self.read_header()
        if type(self.value) is int:
            return int(self) - int(other)
        else:
            raise Exception("TypeError")

    def __rsub__(self, other):
        if not self.initialized:
            self.read_header()
        if type(self.value) is int:
            return int(other) - int(self)
        else:
            raise Exception("TypeError")


    def __mul__(self, other):
        if not self.initialized:
            self.read_header()
        if type(self.value) is int:
            return int(self) * int(other)
        else:
            raise Exception("TypeError")

    def __rmul__(self, other):
        if not self.initialized:
            self.read_header()
        if type(self.value) is int:
            return int(self) * int(other)
        else:
            raise Exception("TypeError")


    def __repr__(self):
        if not self.initialized:
            self.read_header()

        res = ""
        if self.undefined:
            res += "UNDEFINED"
        elif self.eof:
            res += "EOF"
        elif not self.map and self.array_length is not None:
            if self.indefinite_length: 
                res += f"INDEFINITE_LIST<{self.array_length}>"
            else:
                res += f"LIST<{self.array_length}>"
        elif self.map:
            res += f"MAP<{self.array_length}>"
        elif self.value is not None:
            res += f"{self.value}"
        else:
            res += "UNKNOWN_CBOR"

        if self.tag:
            res += f" [{self.tag}]"
        return res
