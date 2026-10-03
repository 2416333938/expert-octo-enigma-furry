#include <bits/stdc++.h>
using namespace std;
const int MAXN = 6005;
vector<int> fas[MAXN];
int n, root, happy[MAXN], dp[MAXN][2];
bool head[MAXN];

void dg(int x) {
	dp[x][0] = 0;
	dp[x][1] = happy[x];
	for (int i = 0; i < fas[x].size(); i++) {
		int y = fas[x][i];
		dg(y);
		dp[x][0] += max(dp[y][0], dp[y][1]);
		dp[x][1] += dp[y][0];
	}
}
int main() {
	ios::sync_with_stdio(false);
	cin.tie(0);
	cin >> n;
	for (int i = 1; i <= n; i++) {
		cin >> happy[i];
	}
	for (int i = 1; i <= n - 1; i++) {
		int son, father;              // 输入格式 "L K"：K 是 L 的直接上司
		cin >> son >> father;
		fas[father].push_back(son);
		head[son] = 1;
	}
	for (int i = 1; i <= n; i++) {
		if (head[i] == 0) {
			root = i;
			break;
		}
	}
	dg(root);
	cout << max(dp[root][1], dp[root][0]) << endl;

}
