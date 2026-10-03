#include <bits/stdc++.h>
using namespace std;

string s;
long long dp[12][12][2];

long long dfs(int pos, int last, bool lead, bool limit) {
    if (pos == (int)s.size()) {
        return lead ? 0 : 1; // 全 0 不算
    }

    if (!limit && dp[pos][last + 1][lead] != -1) {
        return dp[pos][last + 1][lead];
    }

    int up = limit ? s[pos] - '0' : 9;
    long long res = 0;

    for (int d = 0; d <= up; ++d) {
        if (lead) {
            if (d == 0) {
                res += dfs(pos + 1, -1, true, limit && d == up);
            } else {
                res += dfs(pos + 1, d, false, limit && d == up);
            }
        } else {
            if (abs(d - last) >= 2) {
                res += dfs(pos + 1, d, false, limit && d == up);
            }
        }
    }

    if (!limit) {
        dp[pos][last + 1][lead] = res;
    }
    return res;
}

long long calc(int n) {
    if (n <= 0) return 0;
    s = to_string(n);
    memset(dp, -1, sizeof(dp));
    return dfs(0, -1, true, true);
}

int main() {
    int a, b;
    cin >> a >> b;
    cout << calc(b) - calc(a - 1) ;
}
