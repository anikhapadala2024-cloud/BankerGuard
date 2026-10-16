#ifndef BANKER_H
#define BANKER_H

#define MAX_P 10
#define MAX_R 5

typedef enum {
    REQ_INVALID = -2,
    REQ_UNSAFE  = -1,
    REQ_WAIT    =  0,
    REQ_GRANTED =  1
} ReqResult;

typedef struct {
    int n, m;
    int available[MAX_R];
    int max[MAX_P][MAX_R];
    int alloc[MAX_P][MAX_R];
    int need[MAX_P][MAX_R];
} BankState;

void bank_init(BankState *s, int n, int m);
int  is_safe(const BankState *s, int seq[]);
ReqResult request_resources(BankState *s, int pid, const int req[],
                            char *reason, int len);
void release_resources(BankState *s, int pid);
void print_state(const BankState *s);

#endif
