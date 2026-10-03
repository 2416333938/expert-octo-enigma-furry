#include <bits/stdc++.h>
#define fi first
#define se second
#define max(a,b)((a)>(b)?(a):(b))
#define min(a,b)((a)<(b)?(a):(b))
using namespace std;
const int MAX = 2010;
int N, M;
int S[MAX];
long long dp[MAX][MAX];
vector<pair<int, int>>v[MAX];
void dfs(int x, int fa) {
	S[x] = 1;
	for (auto i : v[x]) {
		int y = i.fi;
		int w = i.se;
		if (y == fa) {
			continue;
			//TODO
		}
		dfs(y, x);
		S[x] += S[y];
		for (int j = max(M, S[x]); j >= 0; j--) {
			for (int k = max(j - S[x] + S[y], 0); k <= min(j, S[y]); k++) {
				long long edge_contrid = 1ll * k * (M - k) * (M - k) * w + 1ll * (S[y] - k) * (N - M - S[y] + k) * w;
				dp[x][j] = max(dp[x][j], dp[x][j - k] + dp[y][k] + edge_contrid);


			}
		}
	}
}
int main() {
	cin >> N >> M;
	M = min(M, N - M);
	for (int i = 1; i < N; i++) {
		int x, y, z;
		cin >> x >> y >> z;
		v[x].emplace_back(y, z);
		v[y].emplace_back(x, z);
	}
	dfs(1, 0);
	cout << dp[1][M];
}
