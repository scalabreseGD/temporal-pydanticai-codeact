import pickle

state = {}
with open('/tmp/sandbox_state/globals.pkl', 'wb') as f:
    pickle.dump(state, f)
print("State cleared")
