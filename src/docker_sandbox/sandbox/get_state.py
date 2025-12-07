import pickle
try:
    with open('/tmp/sandbox_state/globals.pkl', 'rb') as f:
        state = pickle.load(f)
    print(state)
except Exception as e:
    print({})
