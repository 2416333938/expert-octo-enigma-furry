#include<bits/stdc++.h>
using namespace std;
double a=0;
int n=0,k;
int main(){
	cin>>k;
	while(a<=k){
		n++;
		a+=1.0/n;
		
	}
	cout<<n;
}
