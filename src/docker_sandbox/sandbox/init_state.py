import pickle
import os

# Create state directory
os.makedirs('/tmp/sandbox_state', exist_ok=True)

# Initialize empty state
state = {}
with open('/tmp/sandbox_state/globals.pkl', 'wb') as f:
    pickle.dump(state, f)
