#include <bits/stdc++.h>
using namespace std;
const int MAX = 20000;
int N, A[MAX], F[MAX], ANS = INT_MAX + 1;
vector <int> G[MAX];
void dfs(int u, int fa) {
	F[u] = A[u];
	for (int i = 0; i < G[u].size(); i++) {
		int v = G[u][i];
		if (v == fa) continue;
		dfs(v, u);
		if (F[v] >= 1) F[u] += F[v];
	}
}
int main() {
	cin >> N;
	for (int i = 1; i <= N; i++) scanf("%d", &A[i]);
	for (int i = 1; i < N; i++) {
		int u, v;
		cin >> u >> v;
		G[u].push_back(v);
		G[v].push_back(u);
	}
	dfs(1, 0);
	for (int i = 1; i <= N; i++) ANS = max(ANS, F[i]);

	cout << ANS;
}
