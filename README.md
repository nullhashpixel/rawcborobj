# rawcborobj

experimental CBOR library which does not change encoding after re-serializing parts of de-serialized objects

````
from rawcborobj import rawcborobj
c = rawcborobj(bytes.fromhex("d8799fa144746573749f830707079f070707ffff8101820102ff"))
print(c)
````

```
> INDEFINITE_LIST<3> [121]
```

````
# encode back to hex encoded CBOR
print(c.encoded())
            
# tag is None if no tag is specified
print(c.tag)
            
# value returns a python list
# !!! this will lose some information on CBOR structure for some types, but is useful for human readable output!!!
print(c.value)
````

```
> d8799fa144746573749f830707079f070707ffff8101820102ff
> 121
> [{b'test': [[7, 7, 7], [7, 7, 7]]}, [1], [1, 2]]
```

````
# length available for lists and maps
print(len(c))
print(len(c[0]))
````

````
> 3
> 1
````

````
# element access
print(c[0])
    
# map keys
print(c[0].keys())
print(c[0].keys_bytes())
print(c[0].keys_encoded())
                
# objects as map keys   
print(c[0][rawcborobj(bytes.fromhex("4474657374"))])
                    
# byte sequence as map key
print(c[0][b'Dtest'])
                
# encoded hex string as map key
print(c[0]['4474657374'])
````

````
> MAP<1>
> [b'test']
> [b'Dtest']
> ['4474657374']
> INDEFINITE_LIST<2>
> INDEFINITE_LIST<2>
> INDEFINITE_LIST<2>
````

````
# deeper access
keys = c[0].keys()  
print(c[0][keys[0]])
print(c[0, keys[0]])
print(c[0][keys[0]][0][0])
print(c[0, keys[0], 0, 0])
````

````
> INDEFINITE_LIST<2>
> INDEFINITE_LIST<2>
> 7
> 7
````

````
# encode sub parts
print(c[0, keys[0]].encoded())  
print(c[0, keys[0]].bytes().hex())

# encoding of sub parts is not changed, indefinite lists stay indefinite
print(c[0, keys[0], 0])
print(c[0, keys[0], 1])
````

````
> 9f830707079f070707ffff
> 9f830707079f070707ffff
> LIST<3>
> INDEFINITE_LIST<3>
````
