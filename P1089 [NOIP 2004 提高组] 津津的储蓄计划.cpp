#include<bits/stdc++.h>
using namespace std;
int u, t = 0, m = 0;
int main() {
	for (int i = 0; i < 12; i++) {
		t += 300;
		cin >> u;
		t -= u;
		if (t < 0) {
			cout << "-"<<i + 1;
			return 0;
		}
		while (1) {
			if (t >= 100) {
				t -= 100;
				m += 100;
			} else {
				break;
			}
		}

	}
	t += m * 12 / 10;
	cout << t;
}
