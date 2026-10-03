#include<bits/stdc++.h>
using namespace std;
int k;
bool OK;
bool jianc(int k,string u){
	int a,b,c;
	a=stoi(u.substr(0, 3));
	b=stoi(u.substr(1, 3));
	c=stoi(u.substr(2, 3));
	return a%k+b%k+c%k==0;
	
}
int main(){
	cin>>k;
	for(int i=10000;i<=30000;i++){
		if(jianc(k,to_string(i))){
			cout<<i<<"\n";
			OK=1;
		}
	}
	if(OK!=1) cout<<"No";
	}
	
