#include <iostream>
#include <cstdio>
using namespace std;
struct node {
	int t;
	int apple;
	int next;
};
node tree[2 * 101];
int dp[101][101];
int head[101], n, q, to = 0;
void add(int x, int y, int z) {
	tree[++to].t = y;
	tree[to].apple = z;
	tree[to].next = head[x];
	head[x] = to;
}
void dfs(int f, int fa, int apple) {
	int son[101] = {0}, cnt = 0;
	bool flag = false;
	for (int xun = head[f]; xun; xun = tree[xun].next) {
		if (tree[xun].t != fa) {
			flag = true;
			son[++cnt] = xun;
			dfs(tree[xun].t, f, tree[xun].apple);
		}
	}
	if (!flag) {
		return;
	}
	for (int i = 1; i <= q; i++) {
		for (int j = 0; j <= i; j++) {
			int t1 = 0;
			if (j - 1 >= 0) t1 += tree[son[1]].apple;
			if (i - j - 1 >= 0) t1 += tree[son[2]].apple;
			if (j != 0)
				dp[f][i] = max(dp[f][i], dp[tree[son[1]].t][j - 1] + t1 + dp[tree[son[2]].t][i - j - 1]);
			else
				dp[f][i] = max(dp[f][i], dp[tree[son[2]].t][i - j - 1] + t1);
		}
	}
}
int main() {
	cin >> n >> q;
	for (int i = 1; i <= n - 1; i++) {
		int x, y, z;
		cin >> x >> y >> z;
		add(x, y, z);
		add(y, x, z);
	}
	dfs(1, 0, 0);
	cout << dp[1][q];
	return 0;
}
