#include <bits/stdc++.h>
using namespace std;

struct node {
    int data; // 统一使用 data 字段名
    node *next;
};

int main() {
    // 1. 正确创建链表节点并建立 next 指针链
    node *n1 = new node, *n2 = new node, *n3 = new node;
    node *n4 = new node, *n5 = new node, *n6 = new node;
    node *n7 = new node;

    // 正确顺序：每个节点指向下一个，最后一个指向 nullptr
    n1->next = n2;
    n2->next = n3;
    n3->next = n4;
    n4->next = n5;
    n5->next = n6;
    n6->next = n7;
    n7->next = nullptr; // 链表必须设置尾节点为 nullptr

    // 2. 初始化数据（统一使用 data 字段）
    n1->data = 10;
    n2->data = 20;
    n3->data = 30;
    n4->data = 40;
    n5->data = 25;
    n6->data = 5;

    // 3. 输入数据（如果只需要读 n7，可改为 cin >> n7->data;）
    cout << "请输入 n7 的数据：";
    cin >> n7->data;

    // 4. 测试遍历输出链表内容
    cout << "链表内容: ";
    node *curr = n1;
    while (curr != nullptr) {
        cout << curr->data << (curr->next ? " -> " : "");
        curr = curr->next;
    }
    cout << endl;


    return 0;
}
