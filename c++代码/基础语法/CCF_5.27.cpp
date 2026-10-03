#include<bits/stdc++.h>
using namespace std;
long long int n[1000][1000], jia[1000][1000];
int main() {
	int q;
	cin >> q;
	for (int i = 1; i <= q; i++) {
		for (int a = 1; a <= i; a++) {
			cin >> n[i][a];
		}
	}
	jia[1][1] = n[1][1];
	for (int i = 2; i <= q; i++) {
		for (int a = 1; a <= i; a++) {
			if (a == i) {
				jia[i][a] = jia[i - 1][a - 1] + n[i][a];
			} else {
				jia[i][a] = jia[i - 1][a] + n[i][a];
			}

		}
	}
	int x;
	for (int i = 1; i <= q; i++) {
		if (x > jia[q][i]) {
			x = jia[q][i];
		}
	}
	cout << x;
}
