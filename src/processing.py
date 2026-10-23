from collections import defaultdict

def build_children(folders):
    children = defaultdict(list)
    for f in folders:
        for p in f.get("parents", []):
            children[p].append(f)
    return children