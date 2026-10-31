import ctypes
import os
from flask import Flask, jsonify, request

app = Flask(
    __name__,
    static_folder="../web",
    static_url_path=""
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY_PATH = os.path.join(BASE_DIR, "libbanker.so")

MAX_P = 10
MAX_R = 5

class BankState(ctypes.Structure):
    _fields_ = [
        ("n", ctypes.c_int),
        ("m", ctypes.c_int),
        ("available", ctypes.c_int * MAX_R),
        ("max", (ctypes.c_int * MAX_R) * MAX_P),
        ("alloc", (ctypes.c_int * MAX_R) * MAX_P),
        ("need", (ctypes.c_int * MAX_R) * MAX_P),
    ]

lib = ctypes.CDLL(LIBRARY_PATH)

lib.bank_init.argtypes = [
    ctypes.POINTER(BankState), ctypes.c_int, ctypes.c_int
]
lib.bank_init.restype = None

lib.is_safe.argtypes = [
    ctypes.POINTER(BankState),
    ctypes.POINTER(ctypes.c_int)
]
lib.is_safe.restype = ctypes.c_int

lib.request_resources.argtypes = [
    ctypes.POINTER(BankState),
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_int),
    ctypes.c_char_p,
    ctypes.c_int,
]
lib.request_resources.restype = ctypes.c_int

lib.release_resources.argtypes = [ctypes.POINTER(BankState), ctypes.c_int]
lib.release_resources.restype = None


def create_state(data):
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object.")

    n = data.get("n")
    m = data.get("m")
    available = data.get("available")
    maximum = data.get("max")
    allocation = data.get("alloc")

    if type(n) is not int or not 1 <= n <= MAX_P:
        raise ValueError(f"n must be an integer from 1 to {MAX_P}.")
    if type(m) is not int or not 1 <= m <= MAX_R:
        raise ValueError(f"m must be an integer from 1 to {MAX_R}.")

    def validate_matrix(matrix, rows, cols, name):
        if not isinstance(matrix, list) or len(matrix) != rows:
            raise ValueError(f"{name} must have {rows} rows.")
        result = []
        for row in matrix:
            if not isinstance(row, list) or len(row) != cols:
                raise ValueError(f"Each row of {name} must have {cols} values.")
            if any(type(x) is not int or x < 0 for x in row):
                raise ValueError(f"{name} values must be non-negative integers.")
            result.append(row)
        return result

    if not isinstance(available, list) or len(available) != m:
        raise ValueError(f"available must contain {m} values.")
    if any(type(x) is not int or x < 0 for x in available):
        raise ValueError("available values must be non-negative integers.")

    maximum = validate_matrix(maximum, n, m, "max")
    allocation = validate_matrix(allocation, n, m, "alloc")

    for i in range(n):
        for j in range(m):
            if allocation[i][j] > maximum[i][j]:
                raise ValueError(
                    f"Allocation for P{i}, R{j} exceeds its maximum claim."
                )

    state = BankState()
    lib.bank_init(ctypes.byref(state), n, m)

    for j in range(m):
        state.available[j] = available[j]

    for i in range(n):
        for j in range(m):
            state.max[i][j] = maximum[i][j]
            state.alloc[i][j] = allocation[i][j]
            state.need[i][j] = maximum[i][j] - allocation[i][j]

    return state


def state_to_dict(state):
    n, m = state.n, state.m
    sequence = (ctypes.c_int * MAX_P)()
    safe = bool(lib.is_safe(ctypes.byref(state), sequence))

    return {
        "n": n,
        "m": m,
        "available": [state.available[j] for j in range(m)],
        "max": [
            [state.max[i][j] for j in range(m)] for i in range(n)
        ],
        "alloc": [
            [state.alloc[i][j] for j in range(m)] for i in range(n)
        ],
        "need": [
            [state.need[i][j] for j in range(m)] for i in range(n)
        ],
        "safe": safe,
        "safe_sequence": (
            [int(sequence[i]) for i in range(n)] if safe else []
        ),
    }


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "engine": "C Banker’s Algorithm"})


@app.post("/api/check")
def check_state():
    try:
        state = create_state(request.get_json(silent=True))
        return jsonify(state_to_dict(state))
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/request")
def request_resource():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")

        state = create_state(data)
        pid = data.get("pid")
        req = data.get("request")

        if type(pid) is not int or not 0 <= pid < state.n:
            raise ValueError("pid must identify a valid process.")
        if not isinstance(req, list) or len(req) != state.m:
            raise ValueError(f"request must contain {state.m} values.")
        if any(type(x) is not int or x < 0 for x in req):
            raise ValueError("Request values must be non-negative integers.")

        request_array = (ctypes.c_int * MAX_R)()
        for j, value in enumerate(req):
            request_array[j] = value

        reason = ctypes.create_string_buffer(256)
        result = lib.request_resources(
            ctypes.byref(state),
            pid,
            request_array,
            reason,
            len(reason),
        )

        labels = {
            1: "GRANTED",
            0: "WAIT",
            -1: "UNSAFE",
            -2: "INVALID",
        }

        return jsonify({
            "result": labels.get(result, "ERROR"),
            "reason": reason.value.decode("utf-8", errors="replace"),
            "state": state_to_dict(state),
        })
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/release")
def release_process():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")

        state = create_state(data)
        pid = data.get("pid")

        if type(pid) is not int or not 0 <= pid < state.n:
            raise ValueError("pid must identify a valid process.")

        released = [state.alloc[pid][j] for j in range(state.m)]
        lib.release_resources(ctypes.byref(state), pid)

        return jsonify({
            "released": released,
            "state": state_to_dict(state),
        })
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
