import pickle

# Load previous state
try:
    with open('/tmp/sandbox_state/globals.pkl', 'rb') as f:
        _state = pickle.load(f)
    globals().update(_state)
except FileNotFoundError:
    _state = {}
