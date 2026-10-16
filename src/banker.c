#include <stdio.h>
#include <string.h>
#include "banker.h"

void bank_init(BankState *s, int n, int m) {
    if (s == NULL) return;

    memset(s, 0, sizeof(*s));

    if (n < 1 || n > MAX_P || m < 1 || m > MAX_R) return;

    s->n = n;
    s->m = m;
}

int is_safe(const BankState *s, int seq[]) {
    if (s == NULL || s->n < 1 || s->n > MAX_P ||
        s->m < 1 || s->m > MAX_R) return 0;

    int work[MAX_R], finish[MAX_P] = {0}, count = 0;

    for (int j = 0; j < s->m; j++)
        work[j] = s->available[j];

    while (count < s->n) {
        int found = 0;

        for (int i = 0; i < s->n; i++) {
            if (finish[i]) continue;

            int ok = 1;
            for (int j = 0; j < s->m; j++) {
                if (s->need[i][j] > work[j]) {
                    ok = 0;
                    break;
                }
            }

            if (ok) {
                for (int j = 0; j < s->m; j++)
                    work[j] += s->alloc[i][j];

                if (seq) seq[count] = i;

                finish[i] = 1;
                count++;
                found = 1;
            }
        }

        if (!found) return 0;
    }

    return 1;
}

ReqResult request_resources(BankState *s, int pid, const int req[],
                            char *reason, int len) {
    if (s == NULL || req == NULL || reason == NULL || len <= 0 ||
        s->n < 1 || s->n > MAX_P ||
        s->m < 1 || s->m > MAX_R ||
        pid < 0 || pid >= s->n) {
        if (reason != NULL && len > 0)
            snprintf(reason, len, "invalid input or process ID");
        return REQ_INVALID;
    }

    for (int j = 0; j < s->m; j++) {
        if (req[j] < 0) {
            snprintf(reason, len, "resource requests cannot be negative");
            return REQ_INVALID;
        }

        if (req[j] > s->need[pid][j]) {
            snprintf(reason, len,
                     "P%d asked for %d of R%d but its remaining need is only %d",
                     pid, req[j], j, s->need[pid][j]);
            return REQ_INVALID;
        }
    }

    for (int j = 0; j < s->m; j++) {
        if (req[j] > s->available[j]) {
            snprintf(reason, len,
                     "only %d of R%d free, P%d asked for %d (must wait)",
                     s->available[j], j, pid, req[j]);
            return REQ_WAIT;
        }
    }

    BankState tmp = *s;

    for (int j = 0; j < s->m; j++) {
        tmp.available[j] -= req[j];
        tmp.alloc[pid][j] += req[j];
        tmp.need[pid][j] -= req[j];
    }

    if (!is_safe(&tmp, NULL)) {
        snprintf(reason, len,
                 "granting would leave the system UNSAFE: no process could finish");
        return REQ_UNSAFE;
    }

    *s = tmp;
    snprintf(reason, len, "granted, system remains safe");
    return REQ_GRANTED;
}

void release_resources(BankState *s, int pid) {
    if (s == NULL || s->n < 1 || s->n > MAX_P ||
        s->m < 1 || s->m > MAX_R ||
        pid < 0 || pid >= s->n) return;

    for (int j = 0; j < s->m; j++) {
        s->available[j] += s->alloc[pid][j];
        s->alloc[pid][j] = 0;
        s->need[pid][j] = 0;
        s->max[pid][j] = 0;
    }
}

void print_state(const BankState *s) {
    if (s == NULL || s->n < 1 || s->n > MAX_P ||
        s->m < 1 || s->m > MAX_R) return;

    printf("Available: ");
    for (int j = 0; j < s->m; j++)
        printf("%d ", s->available[j]);

    printf("\nProc  Alloc     Max       Need\n");

    for (int i = 0; i < s->n; i++) {
        printf("P%-4d ", i);

        for (int j = 0; j < s->m; j++)
            printf("%d ", s->alloc[i][j]);

        printf("    ");

        for (int j = 0; j < s->m; j++)
            printf("%d ", s->max[i][j]);

        printf("    ");

        for (int j = 0; j < s->m; j++)
            printf("%d ", s->need[i][j]);

        printf("\n");
    }
}
