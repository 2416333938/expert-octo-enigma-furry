#include<bits/stdc++.h>
using namespace std;
int u,t,g=0,f=0;
int main(){
	for(int i=0;i<7;i++){
		cin>>u>>t;
		u+=t;
		if (u>g&&u>8){
			g=u;
			f=i+1;
		}
	}
	cout<<f;
	
}
