import ctypes
import unittest
from pathlib import Path


# Load the compiled C library.
LIB_PATH = Path(__file__).resolve().parents[1] / "libbanker.so"
lib = ctypes.CDLL(str(LIB_PATH))

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


REQ_INVALID = -2
REQ_UNSAFE = -1
REQ_WAIT = 0
REQ_GRANTED = 1

IntArray = ctypes.c_int * MAX_R

lib.is_safe.argtypes = [
    ctypes.POINTER(BankState),
    ctypes.POINTER(ctypes.c_int),
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


def make_state():
    """Create the standard five-process, three-resource example."""
    state = BankState()
    state.n = 5
    state.m = 3

    state.available[:] = [3, 3, 2, 0, 0]

    allocation = [
        [0, 1, 0],
        [2, 0, 0],
        [3, 0, 2],
        [2, 1, 1],
        [0, 0, 2],
    ]

    maximum = [
        [7, 5, 3],
        [3, 2, 2],
        [9, 0, 2],
        [2, 2, 2],
        [4, 3, 3],
    ]

    for i in range(state.n):
        for j in range(state.m):
            state.alloc[i][j] = allocation[i][j]
            state.max[i][j] = maximum[i][j]
            state.need[i][j] = maximum[i][j] - allocation[i][j]

    return state


def request(state, pid, values):
    """Call the C resource-request function."""
    resources = IntArray(*values)
    reason = ctypes.create_string_buffer(256)

    result = lib.request_resources(
        ctypes.byref(state),
        pid,
        resources,
        reason,
        len(reason),
    )

    return result, reason.value.decode()


class BankerTests(unittest.TestCase):

    def test_initial_state_is_safe(self):
        state = make_state()
        sequence = (ctypes.c_int * MAX_P)()

        result = lib.is_safe(ctypes.byref(state), sequence)

        self.assertEqual(result, 1)
        self.assertEqual(sorted(sequence[:state.n]), list(range(state.n)))

    def test_safe_request_is_granted(self):
        state = make_state()

        result, reason = request(state, 1, [1, 0, 2])

        self.assertEqual(result, REQ_GRANTED)
        self.assertEqual(list(state.available[:3]), [2, 3, 0])
        self.assertEqual(list(state.alloc[1][:3]), [3, 0, 2])
        self.assertEqual(list(state.need[1][:3]), [0, 2, 0])
        self.assertIn("granted", reason)

    def test_request_exceeding_need_is_rejected(self):
        state = make_state()
        original_available = list(state.available)
        original_allocation = list(state.alloc[1])
        original_need = list(state.need[1])

        # P1 needs only one more unit of R0.
        result, _ = request(state, 1, [2, 0, 0])

        self.assertEqual(result, REQ_INVALID)
        self.assertEqual(list(state.available), original_available)
        self.assertEqual(list(state.alloc[1]), original_allocation)
        self.assertEqual(list(state.need[1]), original_need)

    def test_insufficient_resources_must_wait(self):
        state = make_state()
        original_available = list(state.available)
        original_allocation = list(state.alloc[0])

        # P0 needs R0, but no R0 is available in this test.
        state.available[0] = 0

        result, _ = request(state, 0, [1, 0, 0])

        self.assertEqual(result, REQ_WAIT)
        self.assertEqual(state.available[0], 0)
        self.assertEqual(list(state.alloc[0]), original_allocation)

    def test_unsafe_request_is_rejected_without_changes(self):
        state = make_state()
        original_available = list(state.available)
        original_allocation = list(state.alloc[4])
        original_need = list(state.need[4])

        # This request is within P4's need and available resources,
        # but should make the system unsafe.
        result, _ = request(state, 4, [3, 3, 0])

        self.assertEqual(result, REQ_UNSAFE)
        self.assertEqual(list(state.available), original_available)
        self.assertEqual(list(state.alloc[4]), original_allocation)
        self.assertEqual(list(state.need[4]), original_need)

    def test_negative_request_is_rejected(self):
        state = make_state()

        result, _ = request(state, 0, [-1, 0, 0])

        self.assertEqual(result, REQ_INVALID)

    def test_invalid_process_id_is_rejected(self):
        state = make_state()

        result, _ = request(state, 5, [0, 0, 0])

        self.assertEqual(result, REQ_INVALID)


if __name__ == "__main__":
    unittest.main(verbosity=2)
