#include <iostream>
using namespace std;

// 检查三个三位数是否恰好用完 1~9 每个数字一次
bool check(int a, int b, int c) {
    int cnt[10] = {0};
    int nums[3] = {a, b, c};
    for (int i = 0; i < 3; i++) {
        int x = nums[i];
        while (x > 0) {
            cnt[x % 10]++;
            x /= 10;
        }
    }
    for (int d = 1; d <= 9; d++) {
        if (cnt[d] != 1) return false;
    }
    return true;
}

int main() {
    // a 的取值范围：123 ~ 329
    for (int a = 123; a <= 329; a++) {
        int b = 2 * a;
        int c = 3 * a;
        if (check(a, b, c)) {
            cout << a << " " << b << " " << c << endl;
        }
    }
    return 0;
}