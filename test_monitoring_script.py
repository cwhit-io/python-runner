"""
Test script for monitoring WebSocket functionality.
This script will run for approximately 2 minutes, doing some CPU and memory work.
"""

import time
import math

print("Starting monitoring test script...")
print("This will run for approximately 2 minutes")
print("-" * 50)

# Create some data to use memory
data = []

for i in range(1, 121):  # Count from 1 to 120
    # Do some CPU work (calculate factorials)
    result = math.factorial(1000)

    # Use some memory (append to list)
    data.append([i] * 1000)

    # Print progress
    if i % 10 == 0:
        print(f"Progress: {i}/120 ({i / 120 * 100:.1f}%)")
        print(f"Memory items: {len(data)}")

    # Sleep for 1 second
    time.sleep(1)

print("-" * 50)
print(f"Completed! Final count: {i}")
print(f"Total memory items: {len(data)}")
print("Script finished successfully!")
