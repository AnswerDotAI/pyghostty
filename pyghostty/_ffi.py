"Layer 0: the complete libghostty-vt ABI -- generated declarations, loaded library, raw `ffi`/`lib`."
import os
from pathlib import Path
from cffi import FFI
from ._cdef import CDEF

ffi = FFI()
ffi.cdef(CDEF)

def _libpath():
    p = os.environ.get('PYGHOSTTY_LIB')
    if p: return p
    d = Path(__file__).parent/'_lib'
    for ext in ('.dylib','.so','.dll'):
        c = d/f'libghostty-vt{ext}'
        if c.exists(): return str(c)
    raise OSError(f"libghostty-vt not found in {d}; run build_lib.py or set PYGHOSTTY_LIB")

lib = ffi.dlopen(_libpath())

class GhosttyError(RuntimeError): pass

def check(res, what):
    "Raise `GhosttyError` unless `res` is GHOSTTY_SUCCESS."
    if res: raise GhosttyError(f'{what} failed: {res}')

# ABI-mode cffi cannot pass unions by value (libffi limitation). Ghostty's
# tagged-union parameters (GhosttyPoint; later GhosttyTerminalScrollViewport) are
# >16-byte composites, which arm64 AAPCS64 passes indirectly and x86-64 SysV
# passes in stack memory -- so a layout-identical struct twin has the same call
# ABI as the real union-bearing type. We declare twins here and `union_fn`
# casts a symbol's address to a twin-typed signature.
ffi.cdef('''
typedef struct { uint16_t x; uint32_t y; uint64_t _pad; } GhosttyPointValueS;
typedef struct { GhosttyPointTag tag; GhosttyPointValueS value; } GhosttyPointS;
''')
for _twin,_real in (('GhosttyPointS','GhosttyPoint'),):
    assert (ffi.sizeof(_twin),ffi.alignof(_twin)) == (ffi.sizeof(_real),ffi.alignof(_real)), _twin

_union_fns = {}
def union_fn(name, sig):
    "The function `name` cast to twin-typed signature `sig`, for calls passing tagged unions by value."
    if name not in _union_fns: _union_fns[name] = ffi.cast(sig, ffi.addressof(lib, name))
    return _union_fns[name]
