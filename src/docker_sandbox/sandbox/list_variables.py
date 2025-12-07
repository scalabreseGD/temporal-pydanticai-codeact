import pickle

try:
    with open('/tmp/sandbox_state/globals.pkl', 'rb') as f:
        state = pickle.load(f)

    # Create dict of variable names and their types
    var_info = {name: type(value).__name__ for name, value in state.items()}

    import json
    print(json.dumps(var_info))
except Exception as e:
    import json
    print(json.dumps({"error": str(e)}))
