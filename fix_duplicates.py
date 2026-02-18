with open('src/main.py', 'r') as f:
    lines = f.readlines()

with open('src/main.py', 'w') as f:
    f.writelines(lines[:1606])

print(f"Removed {len(lines) - 1606} duplicate lines")
