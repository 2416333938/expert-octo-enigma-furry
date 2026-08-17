#include<bits/stdc++.h>
using namespace std;
int i,n[3000+1][3000+1],x,y,d=1;
int main(){
	cin>>i;
	x=0;y=i-1;
	n[x][y]=1;
	for(;d<i*i;){
		while(x+1<i&&!n[x+1][y]){n[++x][y]=++d;}
		while(y-1>=0&&!n[x][y-1]){n[x][--y]=++d;}
		while(x-1>=0&&!n[x-1][y]){n[--x][y]=++d;}
		while(y+1<i&&!n[x][y+1]){n[x][++y]=++d;}
	}
	for(int e=0;e<i;e++){
		for(int o=0;o<i;o++){
			cout<<n[e][o]<<" ";
		}
		cout<<"\n";
	}
}
