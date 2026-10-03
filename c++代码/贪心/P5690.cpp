#include <bits/stdc++.h>
using namespace std;

int main() {
    char s[8];
    scanf("%s", s);

    int days[13] = {0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    int ans = 5;

    for (int m = 1; m <= 12; m++) {
        for (int d = 1; d <= days[m]; d++) {
            char buf[8];
            sprintf(buf, "%02d-%02d", m, d);   
            int cnt = 0;
            for (int i = 0; i < 5; i++)
                if (buf[i] != s[i]) cnt++;
            ans = min(ans, cnt);
        }
    }

    printf("%d\n", ans);
    return 0;
}
