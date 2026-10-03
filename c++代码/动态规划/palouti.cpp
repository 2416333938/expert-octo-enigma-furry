#include <bits/stdc++.h>
using namespace std;
long long int n,a[9999]={0,1,2};
int main(){
	cin>>n;
	for(int i=3;i<=n;i++)a[i]=a[i-1]+a[i-2];
	cout<<a[n];
}
