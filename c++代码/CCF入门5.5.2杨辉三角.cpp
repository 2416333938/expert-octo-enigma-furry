#include<bits/stdc++.h>
using namespace std;
int a,n[5000+1][5000+1]={0};
int main(){
	cin>>a;
	n[0][0]=1;n[1][0]=1;n[1][1]=1;
	cout<<"1 \n1 1 \n";
	for(int i=2;i<a;i++){
		n[i][0]=1;
		cout<<"1 ";
		for(int g=1;g<=i;g++){
			n[i][g]=n[i-1][g-1]+n[i-1][g];
			cout<<n[i][g]<<" ";
		}
		cout<<"\n";
	}
	
}
