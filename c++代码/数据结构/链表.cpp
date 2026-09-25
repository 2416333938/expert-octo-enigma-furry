#include <bits/stdc++.h>
using namespace std;

struct node {
	int data;
	node *next;
};

int main() {
	node *n1 = new node, *n2 = new node, *n3 = new node, *n4 = new node, *n5 = new node, *n6 = new node, *n7 = new node;

	n1->next = n2;
	n2->next = n3;
	n3->next = n4;
	n4->next = n5;
	n5->next = n6;
	n6->next = n7;
	n7->next =nullptr;

	n1->data = 10;
	n2->data = 20;
	n3->data = 30;
	n4->data = 40;
	n5->data = 25;
	n6->data = 5;
	n7->data = 0;
	cin >> n7->data;

	node *curr = n1;
	while (curr != nullptr) {
		cout << curr->data << (curr->next ? " -> " : "");
		curr = curr->next;
	}


}
