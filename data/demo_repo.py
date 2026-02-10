DEMO_FILES = {
    "simulation.py": """
import numpy as np

def compute_gradient(x, y):
    # O(n^2) implementation
    grad = np.zeros_like(x)
    for i in range(len(x)):
        for j in range(len(y)):
            grad[i] += (x[i] - y[j]) ** 2
    return grad

data_x = np.random.rand(100)
data_y = np.random.rand(100)
result = compute_gradient(data_x, data_y)
print(f"Computed result: {result[:5]}...")
""",
    "web_service.py": """
def process_request(user_id, data):
    # GENERAL_LOGIC profile
    print(f"Loading user {user_id} profile...")
    result = {"status": "success", "payload": data}
    return result
"""
}

DEMO_PDF_CONTENT = """
ALETHEIA RESEARCH PAPER
ABSTRACT:
We propose a new method for repo analysis and PDF auditing.
CLAIM 1: JAX optimization provides 100x speedup for gradient descent. (Citation: Google 2024)
CLAIM 2: Neuro-symbolic validation eliminates hallucinations. (Citation: DeepMind 2025)

MATH SECTION:
f(x) = x^2 + 2x + 1
Implementation code:
def f(x):
    return x**2 + 2*x + 1
Result for x=2 should be 9.
"""
