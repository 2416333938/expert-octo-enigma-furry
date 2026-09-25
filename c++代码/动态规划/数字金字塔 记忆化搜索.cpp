#include <iostream>  // 包含输入输出流库，用于读写数据
#include <algorithm> // 包含max函数，用于比较两个数的大小
using namespace std; // 使用标准命名空间，避免重复写std::

const int MAXN = 505; // 定义最大行数（505>1000，保证足够大，实际最多1000行）
int A[MAXN][MAXN], F[MAXN][MAXN], N; // A:金字塔数据, F:记忆化数组, N:行数

int Dfs(int x, int y) // 递归函数：计算从(x,y)出发到终点的最大路径和
{
    if (F[x][y] == -1) // 如果F[x][y]未计算过（初始值-1表示未计算）
    {
        if (x == N) // 当前在最后一行（无法再向下走）
            F[x][y] = A[x][y]; // 直接返回当前点的值（终点值）
        else 
            F[x][y] = A[x][y] + max(Dfs(x+1, y), Dfs(x+1, y+1)); // 选择左下或右下路径的最大值
    }
    return F[x][y]; // 返回已计算的F[x][y]（已记忆化）
}

int main()
{
    cin >> N; // 读入金字塔的行数R
    for (int i = 1; i <= N; i++) // 从第1行遍历到第N行
        for (int j = 1; j <= i; j++) // 第i行有i个数，列号1~i
            cin >> A[i][j]; // 读入金字塔数据（A[1][1]是顶部，A[N][N]是底部）
    for (int i = 1; i <= N; i++) // 初始化记忆数组F
        for (int j = 1; j <= i; j++)
            F[i][j] = -1; // 将所有位置标记为未计算（-1表示未计算）
    Dfs(1, 1); // 从顶部(1,1)开始计算
    cout << F[1][1] << endl; // 输出从顶部出发的最大路径和
    return 0;
}
