#include<bits/stdc++.h>
using namespace std;
int n,m,M[1000001]
int main() {
	cin>>n>>m;
	for(int i=1; i<n; i++) {
		cin>>a[i];
	}
	for(int i=1; i<n; i++) {
		a[i]+=a[i-1];
	}
	long long ans=0;
	for(int i=1; i<n; i++) {
		if(binary_search(a,a+N,a[i]-M))
			ans++;
	}
	cout<<ans<<"\n";

}
