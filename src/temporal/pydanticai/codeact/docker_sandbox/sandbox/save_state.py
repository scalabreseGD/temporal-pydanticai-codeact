"""
Save current Python globals to persistent state.

This script is injected after user code execution to persist variables
for future executions. It filters and saves all picklable, non-private
variables from the global namespace.

Filtering rules:
- Excludes variables starting with _ (private)
- Excludes callables (functions, methods)
- Excludes modules and types
- Excludes imported standard library names
- Only includes picklable objects (verified before saving)

This script is used by the execute_python operation when persist_state=True.
State is stored in persistent storage (Docker volumes or NFS) for durability across container restarts.

Note:
    The filtering ensures that only user-created data variables persist,
    not functions, classes, or imported modules.
"""

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

# Determine state directory based on persistent storage availability and workflow_id
import os
_workflow_id = os.getenv('WORKFLOW_ID', 'default')
_persistent_base = f'/persistent-storage/{_workflow_id}/state'

# Check if persistent storage mount is available
if os.path.exists('/persistent-storage') and os.path.ismount('/persistent-storage'):
    _state_dir = _persistent_base
    # Ensure workflow-specific subdirectory exists
    os.makedirs(_state_dir, exist_ok=True)
else:
    # Fall back to local storage
    _state_dir = '/tmp/sandbox_state'

_state_file = os.path.join(_state_dir, 'globals.pkl')

with open(_state_file, 'wb') as f:
    pickle.dump(_state_to_save, f)
