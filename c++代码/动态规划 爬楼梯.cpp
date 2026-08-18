#include <bits/stdc++.h>
using namespace std;
int n,a[9999];
int main(){
	cin>>n;
	a[1]=1;
	a[2]=2;
	for(int i=3;i<=n;i++){
		a[i]=a[i-1]+a[i-2];
	}cout<<a[n];
}
