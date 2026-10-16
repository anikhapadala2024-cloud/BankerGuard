#include <stdio.h>
#include "banker.h"

static void try(BankState *s, int pid, int a, int b, int c) {
    int req[MAX_R] = {a, b, c};
    char reason[200];
    ReqResult r = request_resources(s, pid, req, reason, sizeof(reason));
    printf("P%d requests (%d,%d,%d) -> %s | %s\n", pid, a, b, c,
           r == REQ_GRANTED ? "GRANTED" : r == REQ_WAIT ? "WAIT" :
           r == REQ_UNSAFE ? "DENIED(UNSAFE)" : "INVALID", reason);
}

int main(void) {
    BankState s;
    bank_init(&s, 5, 3);

    int alloc[5][3] = {{0,1,0},{2,0,0},{3,0,2},{2,1,1},{0,0,2}};
    int max[5][3]   = {{7,5,3},{3,2,2},{9,0,2},{2,2,2},{4,3,3}};
    int avail[3]    = {3,3,2};

    for (int i = 0; i < 5; i++)
        for (int j = 0; j < 3; j++) {
            s.alloc[i][j] = alloc[i][j];
            s.max[i][j]   = max[i][j];
            s.need[i][j]  = max[i][j] - alloc[i][j];
        }
    for (int j = 0; j < 3; j++) s.available[j] = avail[j];

    print_state(&s);

    int seq[MAX_P];
    if (is_safe(&s, seq)) {
        printf("\nSAFE. Sequence: ");
        for (int i = 0; i < s.n; i++) printf("P%d ", seq[i]);
        printf("\n\n");
    } else printf("\nUNSAFE\n\n");

    try(&s, 1, 1, 0, 2);
    try(&s, 4, 3, 3, 0);
    try(&s, 0, 0, 2, 0);
    return 0;
}
