import pickle
import io
import types

# List of types that typically cannot be pickled
_UNPICKLABLE_TYPES = (
    io.IOBase,  # File handles and I/O objects
    types.ModuleType,  # Modules
    types.FunctionType,  # Functions (already covered by callable())
    types.BuiltinFunctionType,  # Built-in functions
    type,  # Classes
)

def _is_picklable(obj):
    """Check if an object is picklable."""
    try:
        pickle.dumps(obj)
        return True
    except (TypeError, pickle.PicklingError, AttributeError):
        return False

# Save state (exclude private variables, modules, and non-picklable objects)
# Create a copy of globals to avoid "dictionary changed size during iteration" error
_globals_snapshot = dict(globals())
_state_to_save = {}

for k, v in _globals_snapshot.items():
    # Skip private variables, callables, types, and module imports
    if (k.startswith('_') or
        callable(v) or
        isinstance(v, _UNPICKLABLE_TYPES) or
        k in ['pickle', 'io', 'types', 'os', 'json']):
        continue

    # Try to verify it's picklable before adding
    if _is_picklable(v):
        _state_to_save[k] = v

with open('/tmp/sandbox_state/globals.pkl', 'wb') as f:
    pickle.dump(_state_to_save, f)
