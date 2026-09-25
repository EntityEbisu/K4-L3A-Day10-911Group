# Lazy imports to avoid circular dependency issues
def run_phase1():
    from .phase1 import main
    return main()

def run_corruption_flow():
    from .corruption_flow import main
    return main()
