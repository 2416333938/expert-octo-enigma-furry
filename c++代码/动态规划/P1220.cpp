#include<bits/stdc++.h>
using namespace std;
int N, C, N1[101], N2[101], SUM[101];   // N1=位置, N2=功率, SUM=功率前缀和
long long DP[101][101][2];              // 第三维: 0=站左端, 1=站右端

int main() {
    cin >> N >> C;
    for (int I = 1; I <= N; I++) {      // 注意: 从 1 开始, 不要 0
        cin >> N1[I] >> N2[I];
        SUM[I] = SUM[I - 1] + N2[I];
    }
    int S = SUM[N];                     // 所有灯的总功率

    memset(DP, 0x3f, sizeof(DP));       // 初值设成"无穷大"
    DP[C][C][0] = DP[C][C][1] = 0;      // 起点: 只关了 C 号灯, 耗电 0

    for (int len = 2; len <= N; len++) {        // 区间长度从小到大
        for (int i = 1; i + len - 1 <= N; i++) {
            int j = i + len - 1;

            // 扩到左端 i: 灯 i 此刻还亮着, 所以剩余功率要把它算进去
            long long rest1 = S - (SUM[j] - SUM[i]);
            DP[i][j][0] = min(DP[i+1][j][0] + 1LL*(N1[i+1]-N1[i])*rest1,
                              DP[i+1][j][1] + 1LL*(N1[j]-N1[i])*rest1);

            // 扩到右端 j: 灯 j 此刻还亮着
            long long rest2 = S - (SUM[j-1] - SUM[i-1]);
            DP[i][j][1] = min(DP[i][j-1][0] + 1LL*(N1[j]-N1[i])*rest2,
                              DP[i][j-1][1] + 1LL*(N1[j]-N1[j-1])*rest2);
        }
    }

    cout << min(DP[1][N][0], DP[1][N][1]);
    return 0;
}
