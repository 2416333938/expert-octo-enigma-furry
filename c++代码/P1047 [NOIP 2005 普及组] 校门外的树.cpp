#include<bits/stdc++.h>
using namespace std;
int u[10005],v[10005];
bool b[10005]={0};
int main(){
	int l,m;
	cin>>l>>m;
	
	for(int i=0;i<m;i++){
		cin>>u[i]>>v[i];
	}
	for(int i=0;i<m;i++){
		for(int t=u[i];t<=v[i];t++){
			b[t]=1;
		}
	}
	int n=0;
	for(int i=0;i<=l;i++){
		if(b[i]==0){
			n++;
		}
	}
	cout<<n;
	return 0;
	
}
